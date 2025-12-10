"""
Pytest configuration and fixtures for integration tests.

Provides fixtures for Azurite storage, mock Graph API, and test data.
Each test gets isolated storage resources that are cleaned up after execution.
"""

import pytest
import json
import csv
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
from unittest.mock import MagicMock

from shared.ulid_generator import generate_ulid
from .utils.storage_helper import StorageTestHelper
from .utils.mock_graph_api import MockGraphAPIClient


# Connection string for Azurite (local Azure Storage emulator)
# Note: Python SDK doesn't support "UseDevelopmentStorage=true" shorthand
AZURITE_CONNECTION = (
    "DefaultEndpointsProtocol=http;"
    "AccountName=devstoreaccount1;"
    "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;"
    "BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"
    "QueueEndpoint=http://127.0.0.1:10001/devstoreaccount1;"
    "TableEndpoint=http://127.0.0.1:10002/devstoreaccount1;"
)

# Test data directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def azurite_available():
    """Check if Azurite is running with quick connection test."""
    import socket

    # Quick socket test first to avoid Azure SDK retry delays
    test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    test_socket.settimeout(2)
    try:
        result = test_socket.connect_ex(("127.0.0.1", 10001))
        test_socket.close()
        if result != 0:
            pytest.skip("Azurite not available: cannot connect to port 10001")
    except Exception as e:
        test_socket.close()
        pytest.skip(f"Azurite not available: {e}")

    # If socket connects, verify Azure SDK connectivity
    try:
        helper = StorageTestHelper(AZURITE_CONNECTION)
        list(helper.queue_service.list_queues(results_per_page=1))
        return True
    except Exception as e:
        pytest.skip(f"Azurite not available: {e}")


@pytest.fixture
def storage_helper(azurite_available):
    """Provide storage helper with automatic cleanup."""
    helper = StorageTestHelper(AZURITE_CONNECTION)
    created_queues = []
    created_containers = []
    created_tables = []

    # Track created resources
    original_create_queue = helper.create_queue
    original_create_container = helper.create_container
    original_create_table = helper.create_table

    def track_queue(name):
        created_queues.append(name)
        return original_create_queue(name)

    def track_container(name):
        created_containers.append(name)
        return original_create_container(name)

    def track_table(name):
        created_tables.append(name)
        return original_create_table(name)

    helper.create_queue = track_queue
    helper.create_container = track_container
    helper.create_table = track_table

    yield helper

    # Cleanup after test
    helper.cleanup_all(created_queues, created_containers, created_tables)


@pytest.fixture
def test_queues(storage_helper):
    """Create test queues for invoice processing."""
    queues = ["raw-mail", "to-post", "notify"]
    for queue_name in queues:
        storage_helper.create_queue(queue_name)
    return queues


@pytest.fixture
def test_tables(storage_helper):
    """Create test tables for vendor and transaction data."""
    tables = ["VendorMaster", "InvoiceTransactions"]
    for table_name in tables:
        storage_helper.create_table(table_name)
    return tables


@pytest.fixture
def test_blobs(storage_helper):
    """Create test blob container for invoices."""
    container_name = "invoices"
    storage_helper.create_container(container_name)
    return container_name


@pytest.fixture
def sample_vendors(storage_helper, test_tables) -> List[Dict[str, Any]]:
    """Load sample vendors into VendorMaster table."""
    vendors_file = FIXTURES_DIR / "sample_vendors.csv"
    vendors = []

    with open(vendors_file, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            vendor_entity = {
                "PartitionKey": "Vendor",
                "RowKey": row["vendor_domain"],
                "VendorName": row["vendor_name"],
                "ExpenseDept": row["expense_dept"],
                "AllocationScheduleNumber": row["allocation_schedule"],
                "GLCode": row["gl_code"],
                "BillingParty": row["billing_party"],
                "Active": True,
                "UpdatedAt": datetime.utcnow().isoformat() + "Z",
            }
            storage_helper.insert_entity("VendorMaster", vendor_entity)
            vendors.append(vendor_entity)

    return vendors


@pytest.fixture
def sample_emails() -> Dict[str, Dict[str, Any]]:
    """Load sample email templates."""
    emails_file = FIXTURES_DIR / "sample_emails.json"
    with open(emails_file, "r") as f:
        return json.load(f)


@pytest.fixture
def sample_pdf() -> bytes:
    """Load sample PDF for testing."""
    pdf_file = FIXTURES_DIR / "sample_pdfs" / "sample_invoice.pdf"
    with open(pdf_file, "rb") as f:
        return f.read()


@pytest.fixture
def mock_graph_client(sample_emails) -> MockGraphAPIClient:
    """Provide mock Graph API client."""
    client = MockGraphAPIClient()
    # Pre-load known vendor email
    client.add_test_email(sample_emails["known_vendor"])
    return client


@pytest.fixture
def mock_environment(monkeypatch):
    """Mock environment variables for integration tests."""
    env_vars = {
        "AzureWebJobsStorage": AZURITE_CONNECTION,
        "INVOICE_MAILBOX": "invoices@test.com",
        "AP_EMAIL_ADDRESS": "ap@test.com",
        "TEAMS_WEBHOOK_URL": "https://test.webhook.office.com/webhookb2/test",
        "FUNCTION_APP_URL": "https://func-invoice-agent-dev.azurewebsites.net",
        "GRAPH_TENANT_ID": "test-tenant-id",
        "GRAPH_CLIENT_ID": "test-client-id",
        "GRAPH_CLIENT_SECRET": "test-secret",
        "KEY_VAULT_URL": "https://kv-test.vault.azure.net/",
    }

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    return env_vars


@pytest.fixture
def mock_teams_webhook(monkeypatch):
    """Mock Teams webhook requests."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "success"}

    mock_post = MagicMock(return_value=mock_response)
    monkeypatch.setattr("requests.post", mock_post)

    return mock_post


@pytest.fixture
def transaction_id() -> str:
    """Generate unique transaction ID for test."""
    return generate_ulid()


@pytest.fixture
def raw_mail_message(transaction_id) -> Dict[str, Any]:
    """Create RawMail message for testing."""
    return {
        "id": transaction_id,
        "sender": "billing@adobe.com",
        "subject": "Invoice #12345",
        "blob_url": "https://127.0.0.1:10000/devstoreaccount1/invoices/test/invoice.pdf",
        "received_at": datetime.utcnow().isoformat() + "Z",
    }


@pytest.fixture
def enriched_invoice_message(transaction_id) -> Dict[str, Any]:
    """Create EnrichedInvoice message for testing."""
    return {
        "id": transaction_id,
        "vendor_name": "Adobe Inc",
        "expense_dept": "IT",
        "gl_code": "6100",
        "allocation_schedule": "MONTHLY",
        "billing_party": "Company HQ",
        "blob_url": "https://127.0.0.1:10000/devstoreaccount1/invoices/test/invoice.pdf",
        "status": "enriched",
    }


@pytest.fixture
def notification_message(transaction_id) -> Dict[str, Any]:
    """Create NotificationMessage for testing."""
    return {
        "type": "success",
        "message": "Processed: Adobe Inc - GL 6100",
        "details": {
            "vendor": "Adobe Inc",
            "gl_code": "6100",
            "department": "IT",
            "transaction_id": transaction_id,
        },
    }


# Integration test markers
def pytest_configure(config):
    """Register integration test markers."""
    config.addinivalue_line(
        "markers",
        "integration: Integration tests requiring Azurite (deselect with '-m \"not integration\"')",
    )
    config.addinivalue_line("markers", "slow: Slow tests (>5 seconds)")
    config.addinivalue_line("markers", "e2e: End-to-end flow tests")
