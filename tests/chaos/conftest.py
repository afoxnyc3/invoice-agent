"""
Pytest fixtures for chaos engineering and fault injection tests.

Provides reusable fixtures for simulating transient failures, circuit breaker
scenarios, throttling, timeouts, and rate limiting across Azure services and
external APIs.
"""

import pytest
from unittest.mock import MagicMock
from azure.core.exceptions import ServiceRequestError, HttpResponseError
from shared.circuit_breaker import reset_all_circuits


# =============================================================================
# CIRCUIT BREAKER TEST FIXTURES
# =============================================================================


@pytest.fixture(autouse=True)
def circuit_breaker_test_setup():
    """
    Reset all circuit breakers before and after each chaos test.

    This ensures circuit breakers don't interfere with other tests
    and each test starts with a clean state.

    This fixture is autouse=True, so it applies to all tests in the
    chaos test suite automatically.
    """
    reset_all_circuits()
    yield
    reset_all_circuits()


# =============================================================================
# GRAPH API FAILURE FIXTURES
# =============================================================================


@pytest.fixture
def failing_graph_client():
    """
    Mock Graph API client that fails N times, then succeeds.

    Use this to test retry logic and circuit breaker behavior.

    Args can be customized using parametrize:
        @pytest.mark.parametrize("fail_count", [3, 5, 10])
        def test_something(failing_graph_client):
            ...

    Default: Fails 3 times (503 Service Unavailable), then succeeds.
    """

    def _make_failing_client(fail_count: int = 3, exception_type=ServiceRequestError):
        """Factory function to create a failing client with custom settings."""
        client = MagicMock()
        call_count = {"count": 0}

        def side_effect(*args, **kwargs):
            call_count["count"] += 1
            if call_count["count"] <= fail_count:
                raise exception_type("Simulated transient failure")
            # After failing N times, succeed
            return {
                "value": [
                    {
                        "id": "msg123",
                        "subject": "Invoice #12345",
                        "sender": {"emailAddress": {"address": "test@example.com"}},
                        "hasAttachments": True,
                        "receivedDateTime": "2024-12-05T10:00:00Z",
                    }
                ]
            }

        client.get.side_effect = side_effect
        client.call_count = call_count  # Expose for assertions
        return client

    return _make_failing_client


@pytest.fixture
def graph_503_client(failing_graph_client):
    """
    Graph API client that returns 503 Service Unavailable.

    Simulates temporary overload or maintenance window.
    """

    def _make_503_client(fail_count: int = 3):
        error = HttpResponseError(message="Service Unavailable")
        error.status_code = 503
        return failing_graph_client(fail_count=fail_count, exception_type=lambda msg: error)

    return _make_503_client


# =============================================================================
# TABLE STORAGE THROTTLING FIXTURES
# =============================================================================


@pytest.fixture
def throttled_table_client():
    """
    Mock Table Storage client that returns 429 Too Many Requests.

    Simulates rate limiting and throttling scenarios.

    Default: Returns 429 for first 2 calls, then succeeds.
    """

    def _make_throttled_client(fail_count: int = 2):
        client = MagicMock()
        call_count = {"count": 0}

        def side_effect(*args, **kwargs):
            call_count["count"] += 1
            if call_count["count"] <= fail_count:
                error = HttpResponseError(message="Rate limit exceeded")
                error.status_code = 429
                raise error
            # After throttling, succeed
            return {
                "PartitionKey": "Vendor",
                "RowKey": "test_com",
                "VendorName": "Test Vendor",
                "GLCode": "6100",
            }

        client.get_entity.side_effect = side_effect
        client.call_count = call_count
        return client

    return _make_throttled_client


# =============================================================================
# BLOB STORAGE TIMEOUT FIXTURES
# =============================================================================


@pytest.fixture
def timeout_blob_client():
    """
    Mock Blob Storage client that times out.

    Simulates network latency or connectivity issues.

    Default: Times out for first 2 calls, then succeeds.
    """

    def _make_timeout_client(fail_count: int = 2):
        client = MagicMock()
        call_count = {"count": 0}

        def side_effect(*args, **kwargs):
            call_count["count"] += 1
            if call_count["count"] <= fail_count:
                raise ServiceRequestError("Connection timeout after 30 seconds")
            # After timeout failures, succeed
            blob_mock = MagicMock()
            blob_mock.readall.return_value = b"PDF content data"
            return blob_mock

        client.download_blob.side_effect = side_effect
        client.call_count = call_count
        return client

    return _make_timeout_client


# =============================================================================
# OPENAI RATE LIMIT FIXTURES
# =============================================================================


@pytest.fixture
def rate_limited_openai_client():
    """
    Mock Azure OpenAI client that hits rate limits.

    Simulates quota exhaustion or high load scenarios.

    Default: Returns 429 for first 2 calls, then succeeds.
    """

    def _make_rate_limited_client(fail_count: int = 2):
        client = MagicMock()
        call_count = {"count": 0}

        def side_effect(*args, **kwargs):
            call_count["count"] += 1
            if call_count["count"] <= fail_count:
                # OpenAI SDK raises RateLimitError (subclass of APIError)
                from openai import RateLimitError

                raise RateLimitError(
                    message="Rate limit exceeded. Retry after 60 seconds.",
                    response=MagicMock(status_code=429),
                    body={"error": {"message": "Rate limit exceeded"}},
                )
            # After rate limits, succeed
            response_mock = MagicMock()
            response_mock.choices = [MagicMock()]
            response_mock.choices[0].message.content = "Adobe Inc"
            return response_mock

        # OpenAI client uses chat.completions.create
        client.chat.completions.create.side_effect = side_effect
        client.call_count = call_count
        return client

    return _make_rate_limited_client


# =============================================================================
# CIRCUIT BREAKER STATE FIXTURES
# =============================================================================


@pytest.fixture
def force_circuit_open():
    """
    Force a circuit breaker to OPEN state for testing.

    Usage:
        def test_circuit_open(force_circuit_open):
            force_circuit_open(graph_breaker, fail_count=5)
            # Circuit is now OPEN
    """

    def _force_open(breaker, fail_count: int = None):
        """Force circuit breaker to open by triggering failures."""
        if fail_count is None:
            fail_count = breaker.fail_max

        # Trigger failures to open the circuit
        for _ in range(fail_count):
            try:
                breaker.call(lambda: (_ for _ in ()).throw(Exception("Forced failure")))
            except Exception:
                pass  # Expected

        # Verify circuit is open
        assert breaker.current_state == "open"
        return breaker

    return _force_open
