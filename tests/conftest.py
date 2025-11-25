"""
Pytest configuration and shared fixtures for Invoice Agent tests
"""

import pytest
import json
from unittest.mock import MagicMock
from typing import Dict, Any


# Configure pytest
pytest_plugins = []


@pytest.fixture
def mock_graph_client():
    """Mock Microsoft Graph API client."""
    client = MagicMock()

    # Mock email data
    client.get_unread_emails.return_value = [
        {
            "id": "msg123",
            "sender": {"emailAddress": {"address": "billing@adobe.com"}},
            "subject": "Invoice #12345 - November 2024",
            "hasAttachments": True,
            "attachments": [
                {
                    "id": "att123",
                    "name": "invoice.pdf",
                    "contentType": "application/pdf",
                    "contentBytes": "base64encodeddata",
                    "size": 102400,
                }
            ],
            "receivedDateTime": "2024-11-09T10:00:00Z",
        }
    ]

    client.mark_as_read.return_value = True
    client.send_email.return_value = {"id": "sent123", "status": "sent"}

    return client


@pytest.fixture
def mock_table_client():
    """Mock Azure Table Storage client."""
    client = MagicMock()

    # Mock vendor data
    client.get_entity.return_value = {
        "PartitionKey": "Vendor",
        "RowKey": "adobe_com",
        "VendorName": "Adobe Inc",
        "ExpenseDept": "IT",
        "AllocationScheduleNumber": "MONTHLY",
        "GLCode": "6100",
        "BillingParty": "Company HQ",
        "Active": True,
    }

    client.create_entity.return_value = None
    client.update_entity.return_value = None
    client.query_entities.return_value = []

    return client


@pytest.fixture
def mock_queue_client():
    """Mock Azure Queue Storage client."""
    client = MagicMock()

    client.send_message.return_value = None
    client.receive_messages.return_value = []
    client.get_queue_properties.return_value = {"approximate_message_count": 0}

    return client


@pytest.fixture
def mock_blob_client():
    """Mock Azure Blob Storage client."""
    client = MagicMock()

    client.upload_blob.return_value = None
    client.download_blob.return_value = MagicMock(readall=lambda: b"invoice content")

    return client


@pytest.fixture
def sample_email() -> Dict[str, Any]:
    """Sample email data for testing."""
    return {
        "id": "test-email-001",
        "sender": {"emailAddress": {"address": "billing@adobe.com"}},
        "subject": "Invoice #12345 - November 2024",
        "body": {"contentType": "HTML", "content": "<html>Invoice attached</html>"},
        "hasAttachments": True,
        "attachments": [
            {
                "id": "att001",
                "name": "invoice_12345.pdf",
                "contentType": "application/pdf",
                "contentBytes": "JVBERi0xLjQKJeLjz9M=",  # Sample base64 PDF header
                "size": 245632,
            }
        ],
        "receivedDateTime": "2024-11-09T14:30:00Z",
    }


@pytest.fixture
def sample_vendor() -> Dict[str, Any]:
    """Sample vendor data for testing."""
    return {
        "PartitionKey": "Vendor",
        "RowKey": "adobe_com",
        "VendorName": "Adobe Inc",
        "ExpenseDept": "IT",
        "AllocationScheduleNumber": "MONTHLY",
        "GLCode": "6100",
        "BillingParty": "Company HQ",
        "Active": True,
        "UpdatedAt": "2024-11-09T12:00:00Z",
    }


@pytest.fixture
def raw_mail_message() -> str:
    """Sample raw-mail queue message."""
    return json.dumps(
        {
            "id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
            "sender": "billing@adobe.com",
            "subject": "Invoice #12345",
            "blob_url": "https://storage.blob.core.windows.net/invoices/raw/invoice_12345.pdf",
            "received_at": "2024-11-09T14:30:00Z",
        }
    )


@pytest.fixture
def enriched_message() -> str:
    """Sample enriched queue message."""
    return json.dumps(
        {
            "id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
            "vendor_name": "Adobe Inc",
            "expense_dept": "IT",
            "allocation_schedule": "MONTHLY",
            "gl_code": "6100",
            "billing_party": "Company HQ",
            "blob_url": "https://storage.blob.core.windows.net/invoices/raw/invoice_12345.pdf",
            "status": "enriched",
        }
    )


@pytest.fixture
def notify_message() -> str:
    """Sample notify queue message."""
    return json.dumps(
        {
            "type": "success",
            "message": "Processed: Adobe Inc - GL 6100",
            "details": {
                "vendor": "Adobe Inc",
                "gl_code": "6100",
                "department": "IT",
                "transaction_id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
            },
        }
    )


@pytest.fixture
def mock_environment(monkeypatch):
    """Mock environment variables for testing."""
    env_vars = {
        "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test;",
        "GRAPH_TENANT_ID": "test-tenant-id",
        "GRAPH_CLIENT_ID": "test-client-id",
        "GRAPH_CLIENT_SECRET": "test-client-secret",
        "AP_EMAIL_ADDRESS": "accountspayable@test.com",
        "TEAMS_WEBHOOK_URL": "https://test.webhook.url",
        "KEY_VAULT_URL": "https://test-keyvault.vault.azure.net/",
        "AZURE_OPENAI_ENDPOINT": "https://test-openai.openai.azure.com/",
        "AZURE_OPENAI_API_KEY": "test-openai-key",
        "AZURE_OPENAI_DEPLOYMENT": "gpt-4o-mini",
        "AZURE_OPENAI_API_VERSION": "2024-02-01",
    }

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    return env_vars


@pytest.fixture
def mock_ulid():
    """Mock ULID generator for consistent test IDs."""
    mock = MagicMock()
    mock.return_value = "01JCK3Q7H8ZVXN3BARC9GWAEZM"
    return mock


@pytest.fixture
def mock_requests(monkeypatch):
    """Mock requests library for Teams webhook."""
    mock_post = MagicMock()
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"success": True}

    monkeypatch.setattr("requests.post", mock_post)
    return mock_post


# Markers for test categorization
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests that don't require external resources")
    config.addinivalue_line("markers", "integration: Integration tests that may require external resources")
    config.addinivalue_line("markers", "slow: Tests that take more than 1 second")
    config.addinivalue_line("markers", "requires_azure: Tests that require Azure connection")
