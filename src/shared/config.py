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
    def storage_connection_string(self) -> str:
        """Azure Storage connection string."""
        return os.environ["AzureWebJobsStorage"]

    @property
    def table_service(self) -> TableServiceClient:
        """Lazy-loaded Table Service client with connection pooling."""
        if self._table_service is None:
            self._table_service = TableServiceClient.from_connection_string(self.storage_connection_string)
        return self._table_service

    @property
    def blob_service(self) -> BlobServiceClient:
        """Lazy-loaded Blob Service client with connection pooling."""
        if self._blob_service is None:
            self._blob_service = BlobServiceClient.from_connection_string(self.storage_connection_string)
        return self._blob_service

    @property
    def queue_service(self) -> QueueServiceClient:
        """Lazy-loaded Queue Service client with connection pooling."""
        if self._queue_service is None:
            self._queue_service = QueueServiceClient.from_connection_string(self.storage_connection_string)
        return self._queue_service

    def get_table_client(self, table_name: str) -> TableClient:
        """Get a table client for the specified table."""
        return self.table_service.get_table_client(table_name)

    def get_container_client(self, container_name: str) -> ContainerClient:
        """Get a blob container client for the specified container."""
        return self.blob_service.get_container_client(container_name)

    def get_queue_client(self, queue_name: str) -> QueueClient:
        """Get a queue client for the specified queue."""
        return self.queue_service.get_queue_client(queue_name)

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
        required = [
            ("AzureWebJobsStorage", "storage_connection_string"),
            ("INVOICE_MAILBOX", "invoice_mailbox"),
            ("AP_EMAIL_ADDRESS", "ap_email_address"),
        ]

        missing = []
        for env_key, _ in required:
            if not os.environ.get(env_key):
                missing.append(env_key)

        if missing:
            logger.error(f"Missing required configuration: {missing}")

        return missing


# Global singleton instance
config = Config()
