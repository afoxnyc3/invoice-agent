"""
Unit tests for Health/__init__.py module.

Tests cover:
- Healthy state (all dependencies OK)
- Storage connectivity failures
- Configuration validation failures
- Response format validation (minimal info, no sensitive data)
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
        assert "timestamp" in body
        # Verify no sensitive info is exposed
        assert "environment" not in body
        assert "checks" not in body
        assert "error" not in body

    @patch("Health.config")
    def test_health_response_format_minimal(self, mock_config):
        """Test response contains only status and timestamp (no sensitive data)."""
        mock_config.table_service.list_tables.return_value = []
        mock_config.validate_required.return_value = []

        from Health import main

        req = func.HttpRequest(
            method="GET",
            body=b"",
            url="/api/health",
        )

        response = main(req)

        assert response.mimetype == "application/json"
        body = json.loads(response.get_body())

        # Verify minimal structure - only status and timestamp
        assert set(body.keys()) == {"status", "timestamp"}
        assert body["status"] in ["healthy", "degraded", "unhealthy"]


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
        # Verify error details are NOT exposed
        assert "error" not in body
        assert "Connection refused" not in json.dumps(body)

    @patch("Health.config")
    def test_health_storage_timeout(self, mock_config):
        """Test returns 503 when storage times out."""
        mock_config.table_service.list_tables.side_effect = Exception("Connection timeout")
        mock_config.validate_required.return_value = []

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
        # Verify missing config names are NOT exposed
        assert "missing_config" not in body
        assert "INVOICE_MAILBOX" not in json.dumps(body)


# =============================================================================
# EXCEPTION HANDLING TESTS
# =============================================================================


class TestHealthExceptionHandling:
    """Test Health endpoint exception handling."""

    @patch("Health.config")
    def test_health_unhandled_exception(self, mock_config):
        """Test returns 503 without exposing error message on exception."""
        # Force an exception during main processing
        mock_config.table_service.list_tables.return_value = []
        mock_config.validate_required.side_effect = Exception("Unexpected error")

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
        assert "timestamp" in body
        # Verify error message is NOT exposed
        assert "error" not in body
        assert "Unexpected error" not in json.dumps(body)


# =============================================================================
# INFORMATION DISCLOSURE TESTS
# =============================================================================


class TestHealthNoInformationDisclosure:
    """Test that Health endpoint doesn't expose sensitive information."""

    @patch("Health.config")
    def test_health_no_environment_exposed(self, mock_config):
        """Test environment name is not exposed in response."""
        mock_config.table_service.list_tables.return_value = []
        mock_config.validate_required.return_value = []
        mock_config.environment = "production"

        from Health import main

        req = func.HttpRequest(
            method="GET",
            body=b"",
            url="/api/health",
        )

        response = main(req)
        body = json.loads(response.get_body())

        assert "environment" not in body
        assert "production" not in json.dumps(body)

    @patch("Health.config")
    def test_health_no_table_count_exposed(self, mock_config):
        """Test table count is not exposed in response."""
        mock_config.table_service.list_tables.return_value = [
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
        ]
        mock_config.validate_required.return_value = []

        from Health import main

        req = func.HttpRequest(
            method="GET",
            body=b"",
            url="/api/health",
        )

        response = main(req)
        body = json.loads(response.get_body())

        # Verify no table count fields in response
        assert "tables_count" not in body
        assert "tables" not in body
        assert "count" not in str(body).lower()


# =============================================================================
# DETAILED HEALTH CHECK TESTS
# =============================================================================


class TestHealthDetailedEndpoint:
    """Test Health endpoint with ?detailed=true parameter."""

    @patch.dict(
        "os.environ",
        {
            "GRAPH_TENANT_ID": "test-tenant",
            "GRAPH_CLIENT_ID": "test-client",
            "GRAPH_CLIENT_SECRET": "test-secret",
            "GIT_SHA": "abc123",
            "DEPLOYMENT_TIMESTAMP": "2025-12-08T10:00:00Z",
        },
    )
    @patch("Health.get_all_circuit_states")
    @patch("Health.config")
    def test_detailed_returns_all_checks(self, mock_config, mock_circuits):
        """Test detailed=true returns all health check information."""
        mock_config.table_service.list_tables.return_value = []
        mock_config.validate_required.return_value = []
        mock_config.environment = "prod"
        mock_circuits.return_value = {
            "graph_api": {"name": "graph_api", "state": "closed", "fail_count": 0},
            "azure_openai": {"name": "azure_openai", "state": "closed", "fail_count": 0},
            "azure_storage": {"name": "azure_storage", "state": "closed", "fail_count": 0},
        }

        from Health import main

        req = func.HttpRequest(
            method="GET",
            body=b"",
            url="/api/health",
            params={"detailed": "true"},
        )

        response = main(req)

        assert response.status_code == 200
        body = json.loads(response.get_body())
        assert body["status"] == "healthy"
        assert "checks" in body
        assert "deployment" in body
        assert body["checks"]["storage"]["healthy"] is True
        assert body["checks"]["config"]["healthy"] is True
        assert body["checks"]["graph_credentials"]["healthy"] is True
        assert body["checks"]["circuits"]["healthy"] is True

    @patch.dict(
        "os.environ",
        {
            "GRAPH_TENANT_ID": "test-tenant",
            "GRAPH_CLIENT_ID": "test-client",
            "GRAPH_CLIENT_SECRET": "test-secret",
            "GIT_SHA": "abc123",
            "DEPLOYMENT_TIMESTAMP": "2025-12-08T10:00:00Z",
        },
    )
    @patch("Health.get_all_circuit_states")
    @patch("Health.config")
    def test_detailed_includes_circuit_states(self, mock_config, mock_circuits):
        """Test detailed response includes circuit breaker states."""
        mock_config.table_service.list_tables.return_value = []
        mock_config.validate_required.return_value = []
        mock_config.environment = "prod"
        mock_circuits.return_value = {
            "graph_api": {"name": "graph_api", "state": "closed", "fail_count": 0, "fail_max": 5},
            "azure_openai": {"name": "azure_openai", "state": "closed", "fail_count": 0, "fail_max": 3},
            "azure_storage": {"name": "azure_storage", "state": "closed", "fail_count": 0, "fail_max": 5},
        }

        from Health import main

        req = func.HttpRequest(
            method="GET",
            body=b"",
            url="/api/health",
            params={"detailed": "true"},
        )

        response = main(req)
        body = json.loads(response.get_body())

        assert "circuits" in body["checks"]
        assert "states" in body["checks"]["circuits"]
        states = body["checks"]["circuits"]["states"]
        assert "graph_api" in states
        assert "azure_openai" in states
        assert "azure_storage" in states
        assert states["graph_api"]["state"] == "closed"

    @patch.dict(
        "os.environ",
        {
            "GRAPH_TENANT_ID": "test-tenant",
            "GRAPH_CLIENT_ID": "test-client",
            "GRAPH_CLIENT_SECRET": "test-secret",
            "GIT_SHA": "abc123",
            "DEPLOYMENT_TIMESTAMP": "2025-12-08T10:00:00Z",
        },
    )
    @patch("Health.get_all_circuit_states")
    @patch("Health.config")
    def test_detailed_includes_deployment_info(self, mock_config, mock_circuits):
        """Test detailed response includes deployment information."""
        mock_config.table_service.list_tables.return_value = []
        mock_config.validate_required.return_value = []
        mock_config.environment = "prod"
        mock_circuits.return_value = {
            "graph_api": {"name": "graph_api", "state": "closed", "fail_count": 0},
            "azure_openai": {"name": "azure_openai", "state": "closed", "fail_count": 0},
            "azure_storage": {"name": "azure_storage", "state": "closed", "fail_count": 0},
        }

        from Health import main

        req = func.HttpRequest(
            method="GET",
            body=b"",
            url="/api/health",
            params={"detailed": "true"},
        )

        response = main(req)
        body = json.loads(response.get_body())

        assert "deployment" in body
        assert body["deployment"]["git_sha"] == "abc123"
        assert body["deployment"]["deployment_timestamp"] == "2025-12-08T10:00:00Z"
        assert body["deployment"]["environment"] == "prod"
        assert body["deployment"]["function_count"] == 9

    @patch.dict(
        "os.environ",
        {
            "GRAPH_TENANT_ID": "test-tenant",
            "GRAPH_CLIENT_ID": "test-client",
            "GRAPH_CLIENT_SECRET": "test-secret",
        },
    )
    @patch("Health.get_all_circuit_states")
    @patch("Health.config")
    def test_detailed_circuit_open_shows_degraded(self, mock_config, mock_circuits):
        """Test open circuit results in degraded status."""
        mock_config.table_service.list_tables.return_value = []
        mock_config.validate_required.return_value = []
        mock_config.environment = "prod"
        mock_circuits.return_value = {
            "graph_api": {"name": "graph_api", "state": "open", "fail_count": 5},
            "azure_openai": {"name": "azure_openai", "state": "closed", "fail_count": 0},
            "azure_storage": {"name": "azure_storage", "state": "closed", "fail_count": 0},
        }

        from Health import main

        req = func.HttpRequest(
            method="GET",
            body=b"",
            url="/api/health",
            params={"detailed": "true"},
        )

        response = main(req)

        assert response.status_code == 503
        body = json.loads(response.get_body())
        assert body["status"] == "degraded"
        assert body["checks"]["circuits"]["healthy"] is False

    @patch.dict("os.environ", {}, clear=True)
    @patch("Health.get_all_circuit_states")
    @patch("Health.config")
    def test_detailed_missing_graph_credentials_shows_degraded(self, mock_config, mock_circuits):
        """Test missing Graph credentials results in degraded status."""
        mock_config.table_service.list_tables.return_value = []
        mock_config.validate_required.return_value = []
        mock_config.environment = "prod"
        mock_circuits.return_value = {
            "graph_api": {"name": "graph_api", "state": "closed", "fail_count": 0},
            "azure_openai": {"name": "azure_openai", "state": "closed", "fail_count": 0},
            "azure_storage": {"name": "azure_storage", "state": "closed", "fail_count": 0},
        }

        from Health import main

        req = func.HttpRequest(
            method="GET",
            body=b"",
            url="/api/health",
            params={"detailed": "true"},
        )

        response = main(req)

        assert response.status_code == 503
        body = json.loads(response.get_body())
        assert body["status"] == "degraded"
        assert body["checks"]["graph_credentials"]["healthy"] is False
        assert "Missing" in body["checks"]["graph_credentials"]["error"]

    @patch("Health.config")
    def test_default_still_minimal_without_detailed(self, mock_config):
        """Test default response without detailed param is still minimal."""
        mock_config.table_service.list_tables.return_value = []
        mock_config.validate_required.return_value = []

        from Health import main

        req = func.HttpRequest(
            method="GET",
            body=b"",
            url="/api/health",
        )

        response = main(req)
        body = json.loads(response.get_body())

        # Verify minimal structure - only status and timestamp
        assert set(body.keys()) == {"status", "timestamp"}
        assert "checks" not in body
        assert "deployment" not in body
