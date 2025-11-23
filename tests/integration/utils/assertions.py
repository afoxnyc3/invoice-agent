"""
Custom test assertions for integration tests.

Provides specialized assertion functions for validating Azure Storage
data structures and queue message schemas.
"""

from typing import Dict, Any
from shared.models import RawMail, EnrichedInvoice, NotificationMessage, InvoiceTransaction


def assert_raw_mail_valid(message_json: str) -> RawMail:
    """Assert queue message is valid RawMail schema."""
    raw_mail = RawMail.model_validate_json(message_json)
    assert raw_mail.id, "Transaction ID must not be empty"
    assert raw_mail.sender, "Sender email must not be empty"
    assert raw_mail.blob_url.startswith("https://"), "Blob URL must be HTTPS"
    return raw_mail


def assert_enriched_invoice_valid(message_json: str) -> EnrichedInvoice:
    """Assert queue message is valid EnrichedInvoice schema."""
    enriched = EnrichedInvoice.model_validate_json(message_json)
    assert enriched.id, "Transaction ID must not be empty"
    assert enriched.vendor_name, "Vendor name must not be empty"
    assert len(enriched.gl_code) == 4, "GL code must be 4 digits"
    assert enriched.gl_code.isdigit(), "GL code must be numeric"
    assert enriched.status in ["enriched", "unknown"], "Status must be valid"
    return enriched


def assert_notification_message_valid(message_json: str) -> NotificationMessage:
    """Assert queue message is valid NotificationMessage schema."""
    notification = NotificationMessage.model_validate_json(message_json)
    assert notification.type in ["success", "unknown", "error"], "Type must be valid"
    assert notification.message, "Message must not be empty"
    assert notification.details, "Details must be present"
    if notification.type in ["success", "unknown"]:
        assert "transaction_id" in notification.details, "Transaction ID required in details"
    return notification


def assert_invoice_transaction_valid(entity: Dict[str, Any]) -> None:
    """Assert table entity is valid InvoiceTransaction."""
    transaction = InvoiceTransaction(**entity)
    assert len(transaction.PartitionKey) == 6, "PartitionKey must be YYYYMM format"
    assert transaction.PartitionKey.isdigit(), "PartitionKey must be numeric"
    assert transaction.RowKey, "RowKey (transaction ID) must not be empty"
    assert transaction.Status in ["processed", "unknown", "error"], "Status must be valid"
    if transaction.Status == "error":
        assert transaction.ErrorMessage, "ErrorMessage required when status is error"


def assert_blob_exists(blob_client, container_name: str, blob_name: str) -> bytes:
    """Assert blob exists and return its content."""
    blob = blob_client.get_blob_client(container_name, blob_name)
    content = blob.download_blob().readall()
    assert content, f"Blob {blob_name} must have content"
    return content


def assert_queue_has_messages(queue_client, queue_name: str, expected_count: int = None) -> int:
    """Assert queue has messages (optionally exact count)."""
    queue = queue_client.get_queue_client(queue_name)
    properties = queue.get_queue_properties()
    count = properties.approximate_message_count
    if expected_count is not None:
        assert count == expected_count, f"Expected {expected_count} messages, found {count}"
    else:
        assert count > 0, f"Queue {queue_name} should have messages"
    return count


def assert_table_has_entity(table_client, table_name: str, partition_key: str, row_key: str) -> Dict[str, Any]:
    """Assert table has specific entity."""
    table = table_client.get_table_client(table_name)
    entity = table.get_entity(partition_key, row_key)
    assert entity, f"Entity {partition_key}/{row_key} must exist in {table_name}"
    return entity


def assert_end_to_end_flow_complete(
    storage_helper,
    transaction_id: str,
    vendor_name: str,
    gl_code: str,
) -> None:
    """Assert complete end-to-end flow completed successfully."""
    # Check InvoiceTransactions table
    entity = storage_helper.get_entity("InvoiceTransactions", transaction_id[:6], transaction_id)
    assert entity, f"Transaction {transaction_id} must be logged"
    assert entity["VendorName"] == vendor_name, "Vendor name must match"
    assert entity["GLCode"] == gl_code, "GL code must match"
    assert entity["Status"] == "processed", "Status must be processed"

    # Check blob storage
    blobs = storage_helper.list_blobs("invoices")
    assert any(transaction_id in blob for blob in blobs), f"Invoice blob for {transaction_id} must exist"
