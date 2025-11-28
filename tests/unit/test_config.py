"""
Unit tests for shared/config.py module.

Tests cover:
- Singleton pattern behavior
- Lazy loading of Azure service clients
- Environment variable reading
- Default values for optional config
- Validation of required configuration
"""

import pytest
from unittest.mock import patch, MagicMock


# =============================================================================
# SINGLETON PATTERN TESTS
# =============================================================================


class TestConfigSingleton:
    """Test Config singleton pattern."""

    def test_singleton_returns_same_instance(self):
        """Test that Config returns the same instance on multiple calls."""
        # Need to reset singleton for clean test - reimport after clearing
        import importlib
        import shared.config as config_module

        # Clear existing singleton
        config_module.Config._instance = None

        # Create two instances
        config1 = config_module.Config()
        config2 = config_module.Config()

        # Should be exact same object
        assert config1 is config2

    def test_singleton_init_runs_once(self):
        """Test that __init__ only runs once for singleton."""
        import importlib
        import shared.config as config_module

        # Clear existing singleton
        config_module.Config._instance = None

        config1 = config_module.Config()
        assert config1._initialized is True

        # Second call should not re-initialize
        config2 = config_module.Config()
        assert config2._initialized is True
        assert config1 is config2


# =============================================================================
# ENVIRONMENT VARIABLE TESTS
# =============================================================================


class TestConfigEnvironmentVariables:
    """Test environment variable reading."""

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "test-connection-string",
            "INVOICE_MAILBOX": "invoices@test.com",
            "AP_EMAIL_ADDRESS": "ap@test.com",
            "GRAPH_TENANT_ID": "test-tenant",
            "GRAPH_CLIENT_ID": "test-client-id",
            "GRAPH_CLIENT_SECRET": "test-secret",
        },
        clear=True,
    )
    def test_required_env_vars_read(self):
        """Test reading required environment variables."""
        from shared.config import Config

        Config._instance = None
        cfg = Config()

        assert cfg.storage_connection_string == "test-connection-string"
        assert cfg.invoice_mailbox == "invoices@test.com"
        assert cfg.ap_email_address == "ap@test.com"
        assert cfg.graph_tenant_id == "test-tenant"
        assert cfg.graph_client_id == "test-client-id"
        assert cfg.graph_client_secret == "test-secret"

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "conn",
            "INVOICE_MAILBOX": "inv@test.com",
            "AP_EMAIL_ADDRESS": "ap@test.com",
            "GRAPH_CLIENT_STATE": "my-state-token",
        },
        clear=True,
    )
    def test_graph_client_state_read(self):
        """Test GRAPH_CLIENT_STATE is read when present."""
        from shared.config import Config

        Config._instance = None
        cfg = Config()

        assert cfg.graph_client_state == "my-state-token"

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "conn",
            "INVOICE_MAILBOX": "inv@test.com",
            "AP_EMAIL_ADDRESS": "ap@test.com",
        },
        clear=True,
    )
    def test_graph_client_state_default_empty(self):
        """Test GRAPH_CLIENT_STATE defaults to empty string."""
        from shared.config import Config

        Config._instance = None
        cfg = Config()

        assert cfg.graph_client_state == ""


# =============================================================================
# DEFAULT VALUES TESTS
# =============================================================================


class TestConfigDefaultValues:
    """Test default values for optional configuration."""

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "conn",
            "INVOICE_MAILBOX": "inv@test.com",
            "AP_EMAIL_ADDRESS": "ap@test.com",
        },
        clear=True,
    )
    def test_default_billing_party(self):
        """Test DEFAULT_BILLING_PARTY has default value."""
        from shared.config import Config

        Config._instance = None
        cfg = Config()

        assert cfg.default_billing_party == "Chelsea Piers"

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "conn",
            "INVOICE_MAILBOX": "inv@test.com",
            "AP_EMAIL_ADDRESS": "ap@test.com",
            "DEFAULT_BILLING_PARTY": "Custom Billing Party",
        },
        clear=True,
    )
    def test_custom_billing_party(self):
        """Test DEFAULT_BILLING_PARTY can be overridden."""
        from shared.config import Config

        Config._instance = None
        cfg = Config()

        assert cfg.default_billing_party == "Custom Billing Party"

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "conn",
            "INVOICE_MAILBOX": "inv@test.com",
            "AP_EMAIL_ADDRESS": "ap@test.com",
        },
        clear=True,
    )
    def test_default_environment(self):
        """Test ENVIRONMENT defaults to 'local'."""
        from shared.config import Config

        Config._instance = None
        cfg = Config()

        assert cfg.environment == "local"
        assert cfg.is_production is False

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "conn",
            "INVOICE_MAILBOX": "inv@test.com",
            "AP_EMAIL_ADDRESS": "ap@test.com",
            "ENVIRONMENT": "prod",
        },
        clear=True,
    )
    def test_production_environment(self):
        """Test is_production returns True when ENVIRONMENT=prod."""
        from shared.config import Config

        Config._instance = None
        cfg = Config()

        assert cfg.environment == "prod"
        assert cfg.is_production is True

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "conn",
            "INVOICE_MAILBOX": "inv@test.com",
            "AP_EMAIL_ADDRESS": "ap@test.com",
        },
        clear=True,
    )
    def test_default_log_level(self):
        """Test LOG_LEVEL defaults to 'INFO'."""
        from shared.config import Config

        Config._instance = None
        cfg = Config()

        assert cfg.log_level == "INFO"

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "conn",
            "INVOICE_MAILBOX": "inv@test.com",
            "AP_EMAIL_ADDRESS": "ap@test.com",
        },
        clear=True,
    )
    def test_default_openai_deployment(self):
        """Test AZURE_OPENAI_DEPLOYMENT has default value."""
        from shared.config import Config

        Config._instance = None
        cfg = Config()

        assert cfg.openai_deployment == "gpt-4o-mini"

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "conn",
            "INVOICE_MAILBOX": "inv@test.com",
            "AP_EMAIL_ADDRESS": "ap@test.com",
        },
        clear=True,
    )
    def test_default_openai_api_version(self):
        """Test AZURE_OPENAI_API_VERSION has default value."""
        from shared.config import Config

        Config._instance = None
        cfg = Config()

        assert cfg.openai_api_version == "2024-02-01"

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "conn",
            "INVOICE_MAILBOX": "inv@test.com",
            "AP_EMAIL_ADDRESS": "ap@test.com",
        },
        clear=True,
    )
    def test_default_function_app_url(self):
        """Test FUNCTION_APP_URL has default value."""
        from shared.config import Config

        Config._instance = None
        cfg = Config()

        assert cfg.function_app_url == "https://func-invoice-agent.azurewebsites.net"

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "conn",
            "INVOICE_MAILBOX": "inv@test.com",
            "AP_EMAIL_ADDRESS": "ap@test.com",
        },
        clear=True,
    )
    def test_teams_webhook_url_none_by_default(self):
        """Test TEAMS_WEBHOOK_URL is None when not set."""
        from shared.config import Config

        Config._instance = None
        cfg = Config()

        assert cfg.teams_webhook_url is None


# =============================================================================
# ALLOWED AP EMAILS PARSING TESTS
# =============================================================================


class TestConfigAllowedAPEmails:
    """Test ALLOWED_AP_EMAILS parsing."""

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "conn",
            "INVOICE_MAILBOX": "inv@test.com",
            "AP_EMAIL_ADDRESS": "ap@test.com",
        },
        clear=True,
    )
    def test_allowed_ap_emails_empty_by_default(self):
        """Test ALLOWED_AP_EMAILS returns empty list when not set."""
        from shared.config import Config

        Config._instance = None
        cfg = Config()

        assert cfg.allowed_ap_emails == []

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "conn",
            "INVOICE_MAILBOX": "inv@test.com",
            "AP_EMAIL_ADDRESS": "ap@test.com",
            "ALLOWED_AP_EMAILS": "ap1@test.com,ap2@test.com,ap3@test.com",
        },
        clear=True,
    )
    def test_allowed_ap_emails_parsed_correctly(self):
        """Test ALLOWED_AP_EMAILS is parsed as comma-separated list."""
        from shared.config import Config

        Config._instance = None
        cfg = Config()

        assert cfg.allowed_ap_emails == ["ap1@test.com", "ap2@test.com", "ap3@test.com"]

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "conn",
            "INVOICE_MAILBOX": "inv@test.com",
            "AP_EMAIL_ADDRESS": "ap@test.com",
            "ALLOWED_AP_EMAILS": "AP@Test.COM, Other@Example.ORG ",
        },
        clear=True,
    )
    def test_allowed_ap_emails_normalized_lowercase(self):
        """Test ALLOWED_AP_EMAILS are normalized to lowercase and trimmed."""
        from shared.config import Config

        Config._instance = None
        cfg = Config()

        assert cfg.allowed_ap_emails == ["ap@test.com", "other@example.org"]


# =============================================================================
# VALIDATION TESTS
# =============================================================================


class TestConfigValidation:
    """Test configuration validation."""

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "conn",
            "INVOICE_MAILBOX": "inv@test.com",
            "AP_EMAIL_ADDRESS": "ap@test.com",
        },
        clear=True,
    )
    def test_validate_required_all_present(self):
        """Test validation passes when all required vars are present."""
        from shared.config import Config

        Config._instance = None
        cfg = Config()

        missing = cfg.validate_required()
        assert missing == []

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "conn",
        },
        clear=True,
    )
    def test_validate_required_missing_vars(self):
        """Test validation returns missing required vars."""
        from shared.config import Config

        Config._instance = None
        cfg = Config()

        missing = cfg.validate_required()
        assert "INVOICE_MAILBOX" in missing
        assert "AP_EMAIL_ADDRESS" in missing
        assert "AzureWebJobsStorage" not in missing

    @patch.dict(
        "os.environ",
        {},
        clear=True,
    )
    def test_validate_required_all_missing(self):
        """Test validation returns all missing vars when none set."""
        from shared.config import Config

        Config._instance = None
        cfg = Config()

        missing = cfg.validate_required()
        assert "AzureWebJobsStorage" in missing
        assert "INVOICE_MAILBOX" in missing
        assert "AP_EMAIL_ADDRESS" in missing


# =============================================================================
# LAZY LOADING TESTS
# =============================================================================


class TestConfigLazyLoading:
    """Test lazy loading of Azure service clients."""

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key;EndpointSuffix=core.windows.net",
            "INVOICE_MAILBOX": "inv@test.com",
            "AP_EMAIL_ADDRESS": "ap@test.com",
        },
        clear=True,
    )
    @patch("shared.config.TableServiceClient")
    def test_table_service_lazy_loaded(self, mock_table_service):
        """Test TableServiceClient is lazy-loaded on first access."""
        from shared.config import Config

        Config._instance = None
        cfg = Config()

        # Not called yet
        mock_table_service.from_connection_string.assert_not_called()

        # Access table_service triggers creation
        _ = cfg.table_service

        # Now it should be called
        mock_table_service.from_connection_string.assert_called_once()

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key;EndpointSuffix=core.windows.net",
            "INVOICE_MAILBOX": "inv@test.com",
            "AP_EMAIL_ADDRESS": "ap@test.com",
        },
        clear=True,
    )
    @patch("shared.config.BlobServiceClient")
    def test_blob_service_lazy_loaded(self, mock_blob_service):
        """Test BlobServiceClient is lazy-loaded on first access."""
        from shared.config import Config

        Config._instance = None
        cfg = Config()

        # Not called yet
        mock_blob_service.from_connection_string.assert_not_called()

        # Access blob_service triggers creation
        _ = cfg.blob_service

        # Now it should be called
        mock_blob_service.from_connection_string.assert_called_once()

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key;EndpointSuffix=core.windows.net",
            "INVOICE_MAILBOX": "inv@test.com",
            "AP_EMAIL_ADDRESS": "ap@test.com",
        },
        clear=True,
    )
    @patch("shared.config.QueueServiceClient")
    def test_queue_service_lazy_loaded(self, mock_queue_service):
        """Test QueueServiceClient is lazy-loaded on first access."""
        from shared.config import Config

        Config._instance = None
        cfg = Config()

        # Not called yet
        mock_queue_service.from_connection_string.assert_not_called()

        # Access queue_service triggers creation
        _ = cfg.queue_service

        # Now it should be called
        mock_queue_service.from_connection_string.assert_called_once()

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key;EndpointSuffix=core.windows.net",
            "INVOICE_MAILBOX": "inv@test.com",
            "AP_EMAIL_ADDRESS": "ap@test.com",
        },
        clear=True,
    )
    @patch("shared.config.TableServiceClient")
    def test_table_service_cached(self, mock_table_service):
        """Test TableServiceClient is cached (only created once)."""
        mock_instance = MagicMock()
        mock_table_service.from_connection_string.return_value = mock_instance

        from shared.config import Config

        Config._instance = None
        cfg = Config()

        # Access multiple times
        service1 = cfg.table_service
        service2 = cfg.table_service
        service3 = cfg.table_service

        # Should only be created once
        assert mock_table_service.from_connection_string.call_count == 1
        assert service1 is service2 is service3


# =============================================================================
# CLIENT FACTORY TESTS
# =============================================================================


class TestConfigClientFactories:
    """Test get_*_client factory methods."""

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key;EndpointSuffix=core.windows.net",
            "INVOICE_MAILBOX": "inv@test.com",
            "AP_EMAIL_ADDRESS": "ap@test.com",
        },
        clear=True,
    )
    @patch("shared.config.TableServiceClient")
    def test_get_table_client(self, mock_table_service):
        """Test get_table_client returns client for specified table."""
        mock_service = MagicMock()
        mock_table_service.from_connection_string.return_value = mock_service

        from shared.config import Config

        Config._instance = None
        cfg = Config()

        cfg.get_table_client("VendorMaster")

        mock_service.get_table_client.assert_called_once_with("VendorMaster")

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key;EndpointSuffix=core.windows.net",
            "INVOICE_MAILBOX": "inv@test.com",
            "AP_EMAIL_ADDRESS": "ap@test.com",
        },
        clear=True,
    )
    @patch("shared.config.BlobServiceClient")
    def test_get_container_client(self, mock_blob_service):
        """Test get_container_client returns client for specified container."""
        mock_service = MagicMock()
        mock_blob_service.from_connection_string.return_value = mock_service

        from shared.config import Config

        Config._instance = None
        cfg = Config()

        cfg.get_container_client("invoices")

        mock_service.get_container_client.assert_called_once_with("invoices")

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key;EndpointSuffix=core.windows.net",
            "INVOICE_MAILBOX": "inv@test.com",
            "AP_EMAIL_ADDRESS": "ap@test.com",
        },
        clear=True,
    )
    @patch("shared.config.QueueServiceClient")
    def test_get_queue_client(self, mock_queue_service):
        """Test get_queue_client returns client for specified queue."""
        mock_service = MagicMock()
        mock_queue_service.from_connection_string.return_value = mock_service

        from shared.config import Config

        Config._instance = None
        cfg = Config()

        cfg.get_queue_client("raw-mail")

        mock_service.get_queue_client.assert_called_once_with("raw-mail")
