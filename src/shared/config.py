"""
Centralized configuration module for Invoice Agent.

Provides:
- Type-safe access to all environment variables
- Singleton storage client factory for connection pooling
- Configuration validation at startup
"""

import os
import logging
from typing import Optional
from azure.data.tables import TableServiceClient, TableClient
from azure.storage.blob import BlobServiceClient, ContainerClient
from azure.storage.queue import QueueServiceClient, QueueClient
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)


class Config:
    """
    Centralized configuration with lazy loading and validation.

    Usage:
        from shared.config import config
        mailbox = config.invoice_mailbox
        table_client = config.get_table_client("VendorMaster")
    """

    _instance: Optional["Config"] = None
    _initialized: bool = False

    def __new__(cls) -> "Config":
        """Singleton pattern - only one Config instance per process."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialize config (only runs once due to singleton)."""
        if self._initialized:
            return

        self._initialized = True
        self._table_service: Optional[TableServiceClient] = None
        self._blob_service: Optional[BlobServiceClient] = None
        self._queue_service: Optional[QueueServiceClient] = None

        logger.debug("Config singleton initialized")

    # =========================================================================
    # AZURE STORAGE
    # =========================================================================

    @property
    def storage_connection_string(self) -> Optional[str]:
        """
        Azure Storage connection string.

        Returns None if not available (e.g., during slot swap transitions).
        Callers should handle None gracefully.
        """
        conn_str = os.environ.get("AzureWebJobsStorage")
        if not conn_str:
            logger.warning("AzureWebJobsStorage not available - may be during slot swap or misconfiguration")
        return conn_str

    @property
    def is_storage_available(self) -> bool:
        """Check if storage is available (connection string or MSI format)."""
        # Support both connection string and Managed Identity formats
        has_conn_str = bool(os.environ.get("AzureWebJobsStorage"))
        has_msi_config = bool(os.environ.get("AzureWebJobsStorage__accountName"))
        return has_conn_str or has_msi_config

    @property
    def table_service(self) -> Optional[TableServiceClient]:
        """Lazy-loaded Table Service client with connection pooling."""
        if self._table_service is None:
            # Try MSI format first (AzureWebJobsStorage__tableServiceUri)
            table_uri = os.environ.get("AzureWebJobsStorage__tableServiceUri")
            if table_uri:
                credential = DefaultAzureCredential()
                self._table_service = TableServiceClient(table_uri, credential=credential)
            else:
                # Fall back to connection string
                conn_str = self.storage_connection_string
                if not conn_str:
                    return None
                self._table_service = TableServiceClient.from_connection_string(conn_str)
        return self._table_service

    @property
    def blob_service(self) -> Optional[BlobServiceClient]:
        """Lazy-loaded Blob Service client with connection pooling."""
        if self._blob_service is None:
            # Try MSI format first (AzureWebJobsStorage__blobServiceUri)
            blob_uri = os.environ.get("AzureWebJobsStorage__blobServiceUri")
            if blob_uri:
                credential = DefaultAzureCredential()
                self._blob_service = BlobServiceClient(blob_uri, credential=credential)
            else:
                # Fall back to connection string
                conn_str = self.storage_connection_string
                if not conn_str:
                    return None
                self._blob_service = BlobServiceClient.from_connection_string(conn_str)
        return self._blob_service

    @property
    def queue_service(self) -> Optional[QueueServiceClient]:
        """Lazy-loaded Queue Service client with connection pooling."""
        if self._queue_service is None:
            # Try MSI format first (AzureWebJobsStorage__queueServiceUri)
            queue_uri = os.environ.get("AzureWebJobsStorage__queueServiceUri")
            if queue_uri:
                credential = DefaultAzureCredential()
                self._queue_service = QueueServiceClient(queue_uri, credential=credential)
            else:
                # Fall back to connection string
                conn_str = self.storage_connection_string
                if not conn_str:
                    return None
                self._queue_service = QueueServiceClient.from_connection_string(conn_str)
        return self._queue_service

    def get_table_client(self, table_name: str) -> Optional[TableClient]:
        """Get a table client for the specified table."""
        service = self.table_service
        if not service:
            return None
        return service.get_table_client(table_name)

    def get_container_client(self, container_name: str) -> Optional[ContainerClient]:
        """Get a blob container client for the specified container."""
        service = self.blob_service
        if not service:
            return None
        return service.get_container_client(container_name)

    def get_queue_client(self, queue_name: str) -> Optional[QueueClient]:
        """Get a queue client for the specified queue."""
        service = self.queue_service
        if not service:
            return None
        return service.get_queue_client(queue_name)

    # =========================================================================
    # MICROSOFT GRAPH API
    # =========================================================================

    @property
    def graph_tenant_id(self) -> str:
        """Azure AD tenant ID for Graph API."""
        return os.environ["GRAPH_TENANT_ID"]

    @property
    def graph_client_id(self) -> str:
        """App registration client ID for Graph API."""
        return os.environ["GRAPH_CLIENT_ID"]

    @property
    def graph_client_secret(self) -> str:
        """App registration client secret for Graph API."""
        return os.environ["GRAPH_CLIENT_SECRET"]

    @property
    def graph_client_state(self) -> str:
        """Client state for webhook validation."""
        return os.environ.get("GRAPH_CLIENT_STATE", "")

    # =========================================================================
    # AZURE OPENAI
    # =========================================================================

    @property
    def openai_endpoint(self) -> str:
        """Azure OpenAI endpoint URL."""
        return os.environ["AZURE_OPENAI_ENDPOINT"]

    @property
    def openai_api_key(self) -> str:
        """Azure OpenAI API key."""
        return os.environ["AZURE_OPENAI_API_KEY"]

    @property
    def openai_deployment(self) -> str:
        """Azure OpenAI deployment name."""
        return os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")

    @property
    def openai_api_version(self) -> str:
        """Azure OpenAI API version."""
        return os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-01")

    # =========================================================================
    # EMAIL CONFIGURATION
    # =========================================================================

    @property
    def invoice_mailbox(self) -> str:
        """Shared mailbox for invoice ingestion."""
        return os.environ["INVOICE_MAILBOX"]

    @property
    def ap_email_address(self) -> str:
        """AP mailbox for sending enriched invoices."""
        return os.environ["AP_EMAIL_ADDRESS"]

    @property
    def allowed_ap_emails(self) -> list[str]:
        """List of allowed AP email recipients (for loop prevention)."""
        raw = os.environ.get("ALLOWED_AP_EMAILS", "").strip()
        if not raw:
            return []
        return [email.strip().lower() for email in raw.split(",")]

    # =========================================================================
    # NOTIFICATIONS
    # =========================================================================

    @property
    def teams_webhook_url(self) -> Optional[str]:
        """Teams webhook URL for notifications."""
        return os.environ.get("TEAMS_WEBHOOK_URL")

    # =========================================================================
    # BUSINESS CONFIGURATION
    # =========================================================================

    @property
    def default_billing_party(self) -> str:
        """Default billing party for unknown vendors."""
        return os.environ.get("DEFAULT_BILLING_PARTY", "Chelsea Piers")

    @property
    def function_app_url(self) -> str:
        """Function App base URL for API calls."""
        return os.environ.get("FUNCTION_APP_URL", "https://func-invoice-agent.azurewebsites.net")

    # =========================================================================
    # ENVIRONMENT
    # =========================================================================

    @property
    def environment(self) -> str:
        """Current environment (local, dev, staging, prod)."""
        return os.environ.get("ENVIRONMENT", "local")

    @property
    def log_level(self) -> str:
        """Logging level."""
        return os.environ.get("LOG_LEVEL", "INFO")

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == "prod"

    # =========================================================================
    # VALIDATION
    # =========================================================================

    def validate_required(self) -> list[str]:
        """
        Validate that all required configuration is present.

        Returns:
            List of missing configuration keys (empty if all present)
        """
        missing = []

        # Check storage availability (supports both connection string and MSI formats)
        if not self.is_storage_available:
            missing.append("AzureWebJobsStorage (or MSI config)")

        # Check required email settings
        required_settings = [
            "INVOICE_MAILBOX",
            "AP_EMAIL_ADDRESS",
        ]
        for env_key in required_settings:
            if not os.environ.get(env_key):
                missing.append(env_key)

        if missing:
            logger.error(f"Missing required configuration: {missing}")

        return missing


# Global singleton instance
config = Config()
