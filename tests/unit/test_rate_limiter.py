"""
Unit tests for rate limiting module.
"""

import pytest
from unittest.mock import MagicMock, patch
import azure.functions as func
from azure.core.exceptions import ResourceNotFoundError


class TestGetClientIP:
    """Tests for get_client_ip function."""

    def test_extracts_ip_from_x_forwarded_for(self):
        """Should extract first IP from X-Forwarded-For header."""
        from shared.rate_limiter import get_client_ip

        req = MagicMock(spec=func.HttpRequest)
        req.headers = {"X-Forwarded-For": "192.168.1.100, 10.0.0.1, 172.16.0.1"}

        ip = get_client_ip(req)

        assert ip == "192.168.1.100"

    def test_extracts_single_ip_from_x_forwarded_for(self):
        """Should handle single IP in X-Forwarded-For."""
        from shared.rate_limiter import get_client_ip

        req = MagicMock(spec=func.HttpRequest)
        req.headers = {"X-Forwarded-For": "192.168.1.100"}

        ip = get_client_ip(req)

        assert ip == "192.168.1.100"

    def test_falls_back_to_x_real_ip(self):
        """Should use X-Real-IP if X-Forwarded-For not present."""
        from shared.rate_limiter import get_client_ip

        req = MagicMock(spec=func.HttpRequest)
        req.headers = {"X-Real-IP": "10.0.0.50"}

        ip = get_client_ip(req)

        assert ip == "10.0.0.50"

    def test_returns_unknown_when_no_headers(self):
        """Should return 'unknown' if no IP headers present."""
        from shared.rate_limiter import get_client_ip

        req = MagicMock(spec=func.HttpRequest)
        req.headers = {}

        ip = get_client_ip(req)

        assert ip == "unknown"


class TestGetRateLimitKey:
    """Tests for get_rate_limit_key function."""

    def test_normalizes_ipv4_address(self):
        """Should replace dots with underscores in IPv4."""
        from shared.rate_limiter import get_rate_limit_key

        partition_key, row_key = get_rate_limit_key("192.168.1.100")

        assert partition_key == "RateLimit"
        assert row_key.startswith("192_168_1_100_")

    def test_normalizes_ipv6_address(self):
        """Should replace colons with underscores in IPv6."""
        from shared.rate_limiter import get_rate_limit_key

        partition_key, row_key = get_rate_limit_key("2001:db8::1")

        assert partition_key == "RateLimit"
        assert "2001_db8__1" in row_key

    def test_includes_minute_window(self):
        """Should include minute-based timestamp in row key."""
        from shared.rate_limiter import get_rate_limit_key

        partition_key, row_key = get_rate_limit_key("127.0.0.1")

        # Row key format: {IP}_{YYYYMMDD_HHMM}
        parts = row_key.split("_")
        assert len(parts) >= 4  # IP parts + date + time


class TestCheckRateLimit:
    """Tests for check_rate_limit function."""

    def test_allows_first_request(self):
        """Should allow first request and create entity."""
        from shared.rate_limiter import check_rate_limit

        mock_table = MagicMock()
        mock_table.get_entity.side_effect = ResourceNotFoundError("Not found")

        is_allowed, count = check_rate_limit(mock_table, "192.168.1.1", 10)

        assert is_allowed is True
        assert count == 1
        mock_table.create_entity.assert_called_once()

    def test_allows_request_under_limit(self):
        """Should allow request when under limit."""
        from shared.rate_limiter import check_rate_limit

        mock_table = MagicMock()
        mock_table.get_entity.return_value = {
            "RequestCount": 5,
            "PartitionKey": "RateLimit",
            "RowKey": "test_key",
        }

        is_allowed, count = check_rate_limit(mock_table, "192.168.1.1", 10)

        assert is_allowed is True
        assert count == 6
        mock_table.update_entity.assert_called_once()

    def test_blocks_request_at_limit(self):
        """Should block request when at limit."""
        from shared.rate_limiter import check_rate_limit

        mock_table = MagicMock()
        mock_table.get_entity.return_value = {
            "RequestCount": 10,
            "PartitionKey": "RateLimit",
            "RowKey": "test_key",
        }

        is_allowed, count = check_rate_limit(mock_table, "192.168.1.1", 10)

        assert is_allowed is False
        assert count == 10
        mock_table.update_entity.assert_not_called()

    def test_blocks_request_over_limit(self):
        """Should block request when over limit."""
        from shared.rate_limiter import check_rate_limit

        mock_table = MagicMock()
        mock_table.get_entity.return_value = {
            "RequestCount": 15,
            "PartitionKey": "RateLimit",
            "RowKey": "test_key",
        }

        is_allowed, count = check_rate_limit(mock_table, "192.168.1.1", 10)

        assert is_allowed is False
        assert count == 15


class TestRateLimitResponse:
    """Tests for rate_limit_response function."""

    def test_returns_429_status(self):
        """Should return 429 status code."""
        from shared.rate_limiter import rate_limit_response

        response = rate_limit_response()

        assert response.status_code == 429

    def test_includes_retry_after_header(self):
        """Should include Retry-After header."""
        from shared.rate_limiter import rate_limit_response

        response = rate_limit_response(retry_after=120)

        assert response.headers.get("Retry-After") == "120"

    def test_returns_json_error_body(self):
        """Should return JSON error body."""
        import json
        from shared.rate_limiter import rate_limit_response

        response = rate_limit_response()
        body = json.loads(response.get_body())

        assert body["error"] == "Too Many Requests"
        assert "retry_after" in body


class TestRateLimitDecorator:
    """Tests for rate_limit decorator."""

    def test_allows_request_when_under_limit(self):
        """Should allow request and call wrapped function."""
        from shared.rate_limiter import rate_limit

        mock_table = MagicMock()
        mock_table.get_entity.side_effect = ResourceNotFoundError("Not found")

        mock_config = MagicMock()
        mock_config.get_table_client.return_value = mock_table

        @rate_limit(max_requests=10)
        def handler(req):
            return func.HttpResponse("OK", status_code=200)

        req = MagicMock(spec=func.HttpRequest)
        req.headers = {"X-Forwarded-For": "192.168.1.1"}

        with patch("shared.config.config", mock_config):
            with patch.dict("os.environ", {"RATE_LIMIT_DISABLED": ""}):
                response = handler(req)

        assert response.status_code == 200

    def test_blocks_request_when_over_limit(self):
        """Should return 429 when over limit."""
        from shared.rate_limiter import rate_limit

        mock_table = MagicMock()
        mock_table.get_entity.return_value = {"RequestCount": 100}

        mock_config = MagicMock()
        mock_config.get_table_client.return_value = mock_table

        @rate_limit(max_requests=10)
        def handler(req):
            return func.HttpResponse("OK", status_code=200)

        req = MagicMock(spec=func.HttpRequest)
        req.headers = {"X-Forwarded-For": "192.168.1.1"}

        with patch("shared.config.config", mock_config):
            with patch.dict("os.environ", {"RATE_LIMIT_DISABLED": ""}):
                response = handler(req)

        assert response.status_code == 429

    def test_bypasses_when_disabled(self):
        """Should bypass rate limiting when RATE_LIMIT_DISABLED is true."""
        from shared.rate_limiter import rate_limit

        @rate_limit(max_requests=1)
        def handler(req):
            return func.HttpResponse("OK", status_code=200)

        req = MagicMock(spec=func.HttpRequest)
        req.headers = {}

        with patch.dict("os.environ", {"RATE_LIMIT_DISABLED": "true"}):
            response = handler(req)

        assert response.status_code == 200

    def test_allows_on_error(self):
        """Should allow request when rate limit check fails (fail open)."""
        from shared.rate_limiter import rate_limit

        mock_config = MagicMock()
        mock_config.get_table_client.side_effect = Exception("Storage error")

        @rate_limit(max_requests=10)
        def handler(req):
            return func.HttpResponse("OK", status_code=200)

        req = MagicMock(spec=func.HttpRequest)
        req.headers = {"X-Forwarded-For": "192.168.1.1"}

        with patch("shared.config.config", mock_config):
            with patch.dict("os.environ", {"RATE_LIMIT_DISABLED": ""}):
                response = handler(req)

        # Should allow request (fail open)
        assert response.status_code == 200


class TestDifferentIPsIndependent:
    """Tests that different IPs have independent rate limits."""

    def test_different_ips_have_independent_limits(self):
        """Different IPs should not share rate limits."""
        from shared.rate_limiter import check_rate_limit

        # Track created entities
        created_entities = {}

        def mock_get_entity(pk, rk):
            if rk in created_entities:
                return created_entities[rk]
            raise ResourceNotFoundError("Not found")

        def mock_create_entity(entity):
            created_entities[entity["RowKey"]] = entity

        mock_table = MagicMock()
        mock_table.get_entity.side_effect = mock_get_entity
        mock_table.create_entity.side_effect = mock_create_entity

        # First request from IP 1
        is_allowed1, count1 = check_rate_limit(mock_table, "192.168.1.1", 10)
        assert is_allowed1 is True
        assert count1 == 1

        # First request from IP 2
        is_allowed2, count2 = check_rate_limit(mock_table, "192.168.1.2", 10)
        assert is_allowed2 is True
        assert count2 == 1

        # Both should have created separate entities
        assert len(created_entities) == 2
