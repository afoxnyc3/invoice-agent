"""
Unit tests for shared utilities.

Tests ULID generation, email parsing, and retry logic.
"""

import pytest
import time
from shared.ulid_generator import generate_ulid
from shared.email_parser import extract_domain
from shared.retry import retry_with_backoff


# =============================================================================
# ULID GENERATOR TESTS
# =============================================================================


class TestULIDGenerator:
    """Test ULID generation utilities."""

    def test_generate_ulid_format(self):
        """Test that generated ULID has correct format."""
        ulid = generate_ulid()

        assert isinstance(ulid, str)
        assert len(ulid) == 26
        assert ulid.isupper()  # ULID uses uppercase
        assert ulid.isalnum()  # ULID is alphanumeric

    def test_generate_ulid_uniqueness(self):
        """Test that generated ULIDs are unique."""
        ulids = [generate_ulid() for _ in range(100)]

        # All ULIDs should be unique
        assert len(set(ulids)) == 100

    def test_generate_ulid_sortable(self):
        """Test that ULIDs are lexicographically sortable by time."""
        ulid1 = generate_ulid()
        time.sleep(0.01)  # Small delay
        ulid2 = generate_ulid()

        # Second ULID should be greater (later in time)
        assert ulid2 > ulid1


# =============================================================================
# EMAIL PARSER TESTS
# =============================================================================


class TestEmailParser:
    """Test email parsing utilities."""

    def test_extract_domain_simple(self):
        """Test extracting domain from simple email."""
        domain = extract_domain("billing@adobe.com")
        assert domain == "adobe_com"

    def test_extract_domain_with_subdomain(self):
        """Test extracting domain removes subdomain."""
        domain = extract_domain("invoices@accounts.microsoft.com")
        assert domain == "microsoft_com"

    def test_extract_domain_normalizes_case(self):
        """Test domain extraction normalizes to lowercase."""
        domain = extract_domain("BILLING@ADOBE.COM")
        assert domain == "adobe_com"

    def test_extract_domain_invalid_email(self):
        """Test invalid email raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            extract_domain("not-an-email")

        assert "Invalid email format" in str(exc_info.value)

    def test_extract_domain_empty_email(self):
        """Test empty email raises ValueError."""
        with pytest.raises(ValueError):
            extract_domain("")


# =============================================================================
# RETRY LOGIC TESTS
# =============================================================================


class TestRetryLogic:
    """Test retry and backoff utilities."""

    def test_retry_decorator_success_first_attempt(self):
        """Test retry decorator on successful first attempt."""
        call_count = 0

        @retry_with_backoff(max_attempts=3)
        def successful_function():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_function()

        assert result == "success"
        assert call_count == 1  # Only called once

    def test_retry_decorator_success_after_retries(self):
        """Test retry decorator succeeds after failures."""
        call_count = 0

        @retry_with_backoff(max_attempts=3, initial_delay=0.01)
        def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary failure")
            return "success"

        result = flaky_function()

        assert result == "success"
        assert call_count == 3  # Called 3 times before success

    def test_retry_decorator_all_attempts_fail(self):
        """Test retry decorator raises after all attempts fail."""
        call_count = 0

        @retry_with_backoff(max_attempts=3, initial_delay=0.01)
        def failing_function():
            nonlocal call_count
            call_count += 1
            raise ValueError("Permanent failure")

        with pytest.raises(ValueError) as exc_info:
            failing_function()

        assert "Permanent failure" in str(exc_info.value)
        assert call_count == 3  # All 3 attempts made
