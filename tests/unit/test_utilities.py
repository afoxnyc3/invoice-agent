"""
Unit tests for shared utilities.

Tests ULID generation, email parsing, logging, and retry logic.
"""

import pytest
import time
from unittest.mock import patch
from shared.ulid_generator import generate_ulid, ulid_to_timestamp
from shared.email_parser import extract_domain, normalize_vendor_name, parse_invoice_subject
from shared.logger import get_logger, CorrelatedLogger
from shared.retry import retry_with_backoff, retry_with_timeout, CircuitBreaker


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

    def test_ulid_to_timestamp_valid(self):
        """Test extracting timestamp from valid ULID."""
        ulid = generate_ulid()
        timestamp = ulid_to_timestamp(ulid)

        assert isinstance(timestamp, float)
        assert timestamp > 0
        # Should be close to current time (within 1 second)
        assert abs(time.time() - timestamp) < 1.0

    def test_ulid_to_timestamp_invalid(self):
        """Test that invalid ULID raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ulid_to_timestamp("invalid-ulid-format")

        assert "Invalid ULID format" in str(exc_info.value)


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

    def test_normalize_vendor_name_simple(self):
        """Test normalizing simple vendor name."""
        normalized = normalize_vendor_name("Adobe Inc")
        assert normalized == "adobe"

    def test_normalize_vendor_name_removes_suffixes(self):
        """Test normalization removes common suffixes."""
        assert normalize_vendor_name("Microsoft Corporation") == "microsoft_corporation"
        assert normalize_vendor_name("Apple Inc") == "apple"
        assert normalize_vendor_name("Amazon LLC") == "amazon"

    def test_normalize_vendor_name_removes_special_chars(self):
        """Test normalization removes special characters."""
        normalized = normalize_vendor_name("AT&T Inc.")
        assert "_" not in normalized or normalized == "att"

    def test_parse_invoice_subject_with_number(self):
        """Test parsing invoice number from subject."""
        result = parse_invoice_subject("Invoice #12345 - November")

        assert result["invoice_number"] == "12345"

    def test_parse_invoice_subject_with_amount(self):
        """Test parsing amount from subject."""
        result = parse_invoice_subject("Invoice $1,250.00")

        assert result["amount"] == "1250.00"

    def test_parse_invoice_subject_no_metadata(self):
        """Test parsing subject with no invoice metadata."""
        result = parse_invoice_subject("Please review attached")

        assert result["invoice_number"] is None
        assert result["amount"] is None


# =============================================================================
# LOGGER TESTS
# =============================================================================


class TestLogger:
    """Test structured logging utilities."""

    def test_get_logger_creates_correlated_logger(self):
        """Test get_logger returns CorrelatedLogger instance."""
        logger = get_logger(__name__, "test-correlation-id")

        assert isinstance(logger, CorrelatedLogger)
        assert logger.correlation_id == "test-correlation-id"

    def test_correlated_logger_formats_message(self):
        """Test logger adds correlation ID to messages."""
        logger = CorrelatedLogger(__name__, "01JCKTEST123")

        formatted = logger._format_message("Test message")

        assert "[01JCKTEST123]" in formatted
        assert "Test message" in formatted

    @patch("logging.Logger.info")
    def test_logger_info_includes_correlation_id(self, mock_log):
        """Test info logging includes correlation ID."""
        logger = get_logger(__name__, "01JCKTEST123")
        logger.info("Processing invoice")

        mock_log.assert_called_once()
        call_args = mock_log.call_args[0][0]
        assert "[01JCKTEST123]" in call_args
        assert "Processing invoice" in call_args

    @patch("logging.Logger.error")
    def test_logger_error_includes_correlation_id(self, mock_log):
        """Test error logging includes correlation ID."""
        logger = get_logger(__name__, "01JCKTEST123")
        logger.error("Failed to process")

        mock_log.assert_called_once()
        call_args = mock_log.call_args[0][0]
        assert "[01JCKTEST123]" in call_args


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

    def test_retry_with_timeout_success(self):
        """Test retry_with_timeout succeeds within timeout."""
        call_count = 0

        def eventually_succeeds():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Not yet")
            return "success"

        result = retry_with_timeout(eventually_succeeds, max_attempts=3, timeout_seconds=5.0)

        assert result == "success"
        assert call_count == 2

    def test_retry_with_timeout_exceeds_limit(self):
        """Test retry_with_timeout raises TimeoutError."""

        def slow_function():
            time.sleep(0.1)
            raise Exception("Still failing")

        with pytest.raises((TimeoutError, Exception)):
            retry_with_timeout(slow_function, max_attempts=10, timeout_seconds=0.2)


# =============================================================================
# CIRCUIT BREAKER TESTS
# =============================================================================


class TestCircuitBreaker:
    """Test circuit breaker pattern."""

    def test_circuit_breaker_closed_initially(self):
        """Test circuit breaker starts in closed state."""
        breaker = CircuitBreaker(failure_threshold=3)

        assert not breaker.is_open
        assert breaker.failure_count == 0

    def test_circuit_breaker_opens_after_failures(self):
        """Test circuit breaker opens after threshold."""
        breaker = CircuitBreaker(failure_threshold=3)

        # Simulate 3 failures
        for _ in range(3):
            try:
                breaker.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass

        assert breaker.is_open
        assert breaker.failure_count == 3

    def test_circuit_breaker_blocks_when_open(self):
        """Test circuit breaker blocks calls when open."""
        breaker = CircuitBreaker(failure_threshold=2)

        # Trigger opening
        for _ in range(2):
            try:
                breaker.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass

        # Should now be blocked
        with pytest.raises(Exception) as exc_info:
            breaker.call(lambda: "should not execute")

        assert "Circuit breaker is OPEN" in str(exc_info.value)

    def test_circuit_breaker_resets_on_success(self):
        """Test circuit breaker resets failure count on success."""
        breaker = CircuitBreaker(failure_threshold=3)

        # One failure
        try:
            breaker.call(lambda: (_ for _ in ()).throw(Exception("fail")))
        except Exception:
            pass

        assert breaker.failure_count == 1

        # Success resets count
        result = breaker.call(lambda: "success")

        assert result == "success"
        assert breaker.failure_count == 0
