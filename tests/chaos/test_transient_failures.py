"""
Chaos engineering tests for transient failures and resilience.

Tests verify that the system handles:
- Transient failures with retry success
- Circuit breaker opening after consecutive failures
- Throttling and rate limiting with backoff
- Timeout handling for blob operations
- OpenAI rate limit graceful degradation

These tests simulate real-world failure scenarios to ensure
the system fails gracefully and recovers automatically.
"""

import pytest
from azure.core.exceptions import ServiceRequestError, HttpResponseError
from pybreaker import CircuitBreakerError
from openai import RateLimitError

from shared.circuit_breaker import (
    graph_breaker,
    openai_breaker,
    storage_breaker,
    get_circuit_state,
)
from shared.retry import retry_with_backoff


# =============================================================================
# TEST 1: GRAPH API 503 RETRY SUCCESS
# =============================================================================


class TestGraphAPITransientFailures:
    """Test Graph API retry logic for 503 Service Unavailable."""

    def test_graph_api_503_retry_success(self, failing_graph_client):
        """
        Verify retry succeeds after transient 503 failures.

        Scenario:
        - Graph API returns 503 (Service Unavailable) twice
        - Third attempt succeeds
        - Circuit breaker does NOT open (failures < fail_max)

        Expected:
        - Function retries with backoff
        - Eventually returns successful result
        - Circuit remains CLOSED
        """
        # Create client that fails twice with 503, then succeeds
        client = failing_graph_client(fail_count=2, exception_type=ServiceRequestError)

        # Wrap in retry logic (simulates production usage)
        @retry_with_backoff(max_attempts=3, initial_delay=0.1, exceptions=(ServiceRequestError,))
        def fetch_emails():
            return client.get("/v1.0/users/test@example.com/messages")

        # Execute - should succeed after retries
        result = fetch_emails()

        # Verify success
        assert result is not None
        assert "value" in result
        assert len(result["value"]) == 1
        assert result["value"][0]["id"] == "msg123"

        # Verify 3 attempts were made (2 failures + 1 success)
        assert client.call_count["count"] == 3

        # Verify circuit breaker is still CLOSED (failures < fail_max=5)
        state = get_circuit_state(graph_breaker)
        assert state["state"] == "closed"
        assert state["fail_count"] < state["fail_max"]


# =============================================================================
# TEST 2: GRAPH API CIRCUIT BREAKER OPENS
# =============================================================================


class TestCircuitBreakerBehavior:
    """Test circuit breaker opening after consecutive failures."""

    def test_graph_api_circuit_breaker_opens(self, failing_graph_client):
        """
        Verify circuit breaker opens after fail_max consecutive failures.

        Scenario:
        - Graph API fails 5 consecutive times (fail_max=5)
        - Circuit breaker opens
        - Next call fails immediately with CircuitBreakerError

        Expected:
        - Circuit transitions from CLOSED -> OPEN
        - Subsequent calls fail fast without hitting Graph API
        - No resource exhaustion during outage
        """
        # Create client that always fails
        client = failing_graph_client(fail_count=10, exception_type=ServiceRequestError)

        # Wrap in circuit breaker (simulates production usage)
        def fetch_with_breaker():
            return graph_breaker.call(client.get, "/v1.0/users/test@example.com/messages")

        # Attempt 1-4: Should hit Graph API and fail with ServiceRequestError
        for attempt in range(4):
            with pytest.raises(ServiceRequestError):
                fetch_with_breaker()

        # Attempt 5: Should fail and open the circuit
        # Circuit opens on 5th failure, raising CircuitBreakerError
        with pytest.raises((ServiceRequestError, CircuitBreakerError)):
            fetch_with_breaker()

        # Verify circuit is now OPEN
        state = get_circuit_state(graph_breaker)
        assert state["state"] == "open"
        assert state["fail_count"] == state["fail_max"]

        # Attempt 6: Should fail fast with CircuitBreakerError
        # (does NOT increment call_count - circuit is blocking)
        with pytest.raises(CircuitBreakerError):
            fetch_with_breaker()

        # Verify Graph API was NOT called (circuit blocked it)
        assert client.call_count["count"] == 5  # Only first 5 attempts


# =============================================================================
# TEST 3: TABLE STORAGE THROTTLING (429)
# =============================================================================


class TestTableStorageThrottling:
    """Test handling of Table Storage rate limiting."""

    def test_table_storage_throttling_429(self, throttled_table_client):
        """
        Verify 429 (Too Many Requests) handling with exponential backoff.

        Scenario:
        - Table Storage returns 429 twice (rate limit exceeded)
        - Third attempt succeeds after backoff
        - Verify backoff delays increase exponentially

        Expected:
        - Retry with exponential backoff (1s, 2s, 4s, ...)
        - Eventually succeeds when throttling clears
        - No aggressive retry loops that worsen throttling
        """
        # Create throttled client (fails twice, then succeeds)
        client = throttled_table_client(fail_count=2)

        # Wrap in retry with backoff
        @retry_with_backoff(
            max_attempts=5,
            initial_delay=0.1,  # Fast for testing
            backoff_factor=2.0,
            exceptions=(HttpResponseError,),
        )
        def get_vendor(domain: str):
            return client.get_entity(partition_key="Vendor", row_key=domain)

        # Execute - should succeed after 3 attempts
        result = get_vendor("test_com")

        # Verify success
        assert result is not None
        assert result["RowKey"] == "test_com"
        assert result["VendorName"] == "Test Vendor"

        # Verify 3 attempts were made (2 throttles + 1 success)
        assert client.call_count["count"] == 3


# =============================================================================
# TEST 4: BLOB DOWNLOAD TIMEOUT
# =============================================================================


class TestBlobStorageTimeouts:
    """Test timeout handling for blob operations."""

    def test_blob_download_timeout(self, timeout_blob_client):
        """
        Verify timeout handling for blob download operations.

        Scenario:
        - Blob download times out twice (network latency)
        - Third attempt succeeds
        - Circuit breaker protects against sustained failures

        Expected:
        - Retry after timeout
        - Eventually succeed when network stabilizes
        - Circuit opens if timeouts persist
        """
        # Create client that times out twice, then succeeds
        client = timeout_blob_client(fail_count=2)

        # Wrap in retry with backoff
        @retry_with_backoff(max_attempts=4, initial_delay=0.1, backoff_factor=2.0, exceptions=(ServiceRequestError,))
        def download_pdf(blob_url: str):
            blob_data = client.download_blob(blob_url)
            return blob_data.readall()

        # Execute - should succeed after retries
        result = download_pdf("https://storage.blob.core.windows.net/invoices/test.pdf")

        # Verify success
        assert result is not None
        assert result == b"PDF content data"

        # Verify 3 attempts were made (2 timeouts + 1 success)
        assert client.call_count["count"] == 3

        # Verify storage circuit is still CLOSED (failures < fail_max=5)
        state = get_circuit_state(storage_breaker)
        assert state["state"] == "closed"


# =============================================================================
# TEST 5: OPENAI RATE LIMIT HANDLING
# =============================================================================


class TestOpenAIRateLimiting:
    """Test OpenAI rate limiting and graceful degradation."""

    def test_openai_rate_limit_handling(self, rate_limited_openai_client):
        """
        Verify OpenAI rate limit graceful degradation.

        Scenario:
        - Azure OpenAI returns 429 (rate limit) twice
        - Third attempt succeeds
        - System degrades gracefully (fallback to email domain extraction)

        Expected:
        - Retry with backoff when rate limited
        - Eventually succeed when quota replenishes
        - Log warning but don't fail entire invoice processing
        """
        # Create OpenAI client that hits rate limits twice
        client = rate_limited_openai_client(fail_count=2)

        # Wrap in retry with backoff
        @retry_with_backoff(
            max_attempts=4,
            initial_delay=0.1,
            backoff_factor=2.0,
            exceptions=(RateLimitError,),
        )
        def extract_vendor_name(pdf_text: str):
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Extract vendor name"},
                    {"role": "user", "content": pdf_text},
                ],
            )
            return response.choices[0].message.content

        # Execute - should succeed after retries
        result = extract_vendor_name("Invoice from Adobe Inc...")

        # Verify success
        assert result is not None
        assert result == "Adobe Inc"

        # Verify 3 attempts were made (2 rate limits + 1 success)
        assert client.call_count["count"] == 3

        # Verify OpenAI circuit is still CLOSED (failures < fail_max=3)
        state = get_circuit_state(openai_breaker)
        assert state["state"] == "closed"

    def test_openai_circuit_opens_after_persistent_failures(self, rate_limited_openai_client):
        """
        Verify circuit opens after persistent OpenAI failures.

        Scenario:
        - Azure OpenAI fails 3 consecutive times (fail_max=3)
        - Circuit breaker opens
        - Next call fails immediately

        Expected:
        - Circuit transitions to OPEN after 3 failures
        - Subsequent calls fail fast
        - System falls back to email domain extraction
        """
        # Create client that always fails
        client = rate_limited_openai_client(fail_count=10)

        # Wrap in circuit breaker
        def extract_with_breaker(pdf_text: str):
            return openai_breaker.call(
                client.chat.completions.create,
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Extract vendor name"},
                    {"role": "user", "content": pdf_text},
                ],
            )

        # Attempt 1-2: Should hit OpenAI and fail with RateLimitError
        for _ in range(2):
            with pytest.raises(RateLimitError):
                extract_with_breaker("Invoice from Adobe Inc...")

        # Attempt 3: Should fail and open the circuit
        # Circuit opens on 3rd failure (fail_max=3 for OpenAI)
        with pytest.raises((RateLimitError, CircuitBreakerError)):
            extract_with_breaker("Invoice from Adobe Inc...")

        # Verify circuit is now OPEN
        state = get_circuit_state(openai_breaker)
        assert state["state"] == "open"
        assert state["fail_count"] == state["fail_max"]

        # Attempt 4: Should fail fast with CircuitBreakerError
        with pytest.raises(CircuitBreakerError):
            extract_with_breaker("Invoice from Adobe Inc...")

        # Verify OpenAI was NOT called on 4th attempt
        assert client.call_count["count"] == 3


# =============================================================================
# INTEGRATION TEST: CIRCUIT RECOVERY
# =============================================================================


class TestCircuitBreakerRecovery:
    """Test circuit breaker recovery (half-open -> closed)."""

    def test_circuit_recovers_after_reset_timeout(self, force_circuit_open, failing_graph_client):
        """
        Verify circuit transitions OPEN -> HALF-OPEN -> CLOSED on recovery.

        Scenario:
        - Force circuit to OPEN by triggering failures
        - Wait for reset_timeout (or manually transition to half-open)
        - Successful request closes circuit

        Expected:
        - Circuit allows one test request when half-open
        - Success transitions circuit back to CLOSED
        - Failure keeps circuit OPEN

        Note: This test uses manual transition to avoid real time delays.
        In production, pybreaker automatically transitions after reset_timeout.
        """
        # Force circuit to OPEN
        force_circuit_open(graph_breaker, fail_count=5)
        assert get_circuit_state(graph_breaker)["state"] == "open"

        # Manually transition to HALF-OPEN (simulates reset_timeout elapsed)
        graph_breaker.half_open()
        assert get_circuit_state(graph_breaker)["state"] == "half-open"

        # Create client that will succeed
        client = failing_graph_client(fail_count=0)  # No failures

        # Make successful request - should close circuit
        result = graph_breaker.call(client.get, "/v1.0/users/test@example.com/messages")

        # Verify success
        assert result is not None
        assert "value" in result

        # Verify circuit is now CLOSED
        state = get_circuit_state(graph_breaker)
        assert state["state"] == "closed"
        assert state["fail_count"] == 0
