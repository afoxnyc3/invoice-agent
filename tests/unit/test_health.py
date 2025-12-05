"""
Unit tests for Health/__init__.py module.

Tests cover:
- Healthy state (all dependencies OK)
- Storage connectivity failures
- Configuration validation failures
- Response format validation
- Exception handling
"""

import json
from unittest.mock import patch, MagicMock
import azure.functions as func


# =============================================================================
# HEALTHY STATE TESTS
# =============================================================================


class TestHealthEndpointHealthy:
    """Test Health endpoint when all dependencies are healthy."""

    @patch("Health.config")
    def test_health_all_dependencies_healthy(self, mock_config):
        """Test returns 200 when storage and config are healthy."""
        # Mock healthy storage
        mock_config.table_service.list_tables.return_value = [
            MagicMock(),
            MagicMock(),
        ]
        mock_config.validate_required.return_value = []
        mock_config.environment = "test"

        from Health import main

        req = func.HttpRequest(
            method="GET",
            body=b"",
            url="/api/health",
        )

        response = main(req)

        assert response.status_code == 200
        body = json.loads(response.get_body())
        assert body["status"] == "healthy"
        assert body["checks"]["storage"]["status"] == "healthy"
        assert body["checks"]["config"]["status"] == "healthy"
        assert body["environment"] == "test"
        assert "timestamp" in body

    @patch("Health.config")
    def test_health_response_format(self, mock_config):
        """Test response format matches expected JSON structure."""
        mock_config.table_service.list_tables.return_value = []
        mock_config.validate_required.return_value = []
        mock_config.environment = "prod"

        from Health import main

        req = func.HttpRequest(
            method="GET",
            body=b"",
            url="/api/health",
        )

        response = main(req)

        assert response.mimetype == "application/json"
        body = json.loads(response.get_body())

        # Verify structure
        assert "status" in body
        assert "timestamp" in body
        assert "environment" in body
        assert "checks" in body
        assert "storage" in body["checks"]
        assert "config" in body["checks"]


# =============================================================================
# STORAGE FAILURE TESTS
# =============================================================================


class TestHealthStorageFailures:
    """Test Health endpoint when storage is unavailable."""

    @patch("Health.config")
    def test_health_storage_unavailable(self, mock_config):
        """Test returns 503 when Table Storage is unavailable."""
        # Mock storage failure
        mock_config.table_service.list_tables.side_effect = Exception("Connection refused")
        mock_config.validate_required.return_value = []
        mock_config.environment = "test"

        from Health import main

        req = func.HttpRequest(
            method="GET",
            body=b"",
            url="/api/health",
        )

        response = main(req)

        assert response.status_code == 503
        body = json.loads(response.get_body())
        assert body["status"] == "degraded"
        assert body["checks"]["storage"]["status"] == "unhealthy"
        assert "Connection refused" in body["checks"]["storage"]["error"]

    @patch("Health.config")
    def test_health_storage_timeout(self, mock_config):
        """Test returns 503 when storage times out."""
        mock_config.table_service.list_tables.side_effect = Exception("Connection timeout")
        mock_config.validate_required.return_value = []
        mock_config.environment = "test"

        from Health import main

        req = func.HttpRequest(
            method="GET",
            body=b"",
            url="/api/health",
        )

        response = main(req)

        assert response.status_code == 503
        body = json.loads(response.get_body())
        assert body["checks"]["storage"]["status"] == "unhealthy"


# =============================================================================
# CONFIGURATION FAILURE TESTS
# =============================================================================


class TestHealthConfigFailures:
    """Test Health endpoint when configuration is invalid."""

    @patch("Health.config")
    def test_health_config_missing_required(self, mock_config):
        """Test returns 503 when required config is missing."""
        mock_config.table_service.list_tables.return_value = []
        mock_config.validate_required.return_value = [
            "INVOICE_MAILBOX",
            "AP_EMAIL_ADDRESS",
        ]
        mock_config.environment = "test"

        from Health import main

        req = func.HttpRequest(
            method="GET",
            body=b"",
            url="/api/health",
        )

        response = main(req)

        assert response.status_code == 503
        body = json.loads(response.get_body())
        assert body["status"] == "degraded"
        assert body["checks"]["config"]["status"] == "unhealthy"
        assert "INVOICE_MAILBOX" in body["checks"]["config"]["missing_config"]
        assert "AP_EMAIL_ADDRESS" in body["checks"]["config"]["missing_config"]


# =============================================================================
# EXCEPTION HANDLING TESTS
# =============================================================================


class TestHealthExceptionHandling:
    """Test Health endpoint exception handling."""

    @patch("Health.config")
    def test_health_unhandled_exception(self, mock_config):
        """Test returns 503 with error message on unhandled exception."""
        # Force an exception during main processing
        mock_config.table_service.list_tables.return_value = []
        mock_config.validate_required.side_effect = Exception("Unexpected error")
        mock_config.environment = "test"

        from Health import main

        req = func.HttpRequest(
            method="GET",
            body=b"",
            url="/api/health",
        )

        response = main(req)

        assert response.status_code == 503
        body = json.loads(response.get_body())
        assert body["status"] == "unhealthy"
        assert "Unexpected error" in body["error"]
        assert "timestamp" in body


# =============================================================================
# TABLES COUNT TESTS
# =============================================================================


class TestHealthStorageTablesCount:
    """Test storage check returns table count."""

    @patch("Health.config")
    def test_health_storage_tables_counted(self, mock_config):
        """Test storage check includes table count."""
        # Mock 5 tables
        mock_config.table_service.list_tables.return_value = [
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
        ]
        mock_config.validate_required.return_value = []
        mock_config.environment = "test"

        from Health import main

        req = func.HttpRequest(
            method="GET",
            body=b"",
            url="/api/health",
        )

        response = main(req)

        body = json.loads(response.get_body())
        assert body["checks"]["storage"]["tables_count"] == 5
