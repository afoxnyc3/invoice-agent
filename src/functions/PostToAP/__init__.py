"""
PostToAP queue function - Send enriched invoices to AP mailbox.

Composes email with all enriched metadata, attaches invoice PDF,
sends to AP, logs transaction, and queues notification.

Implements email loop prevention by:
- Checking if transaction already processed (deduplication)
- Validating recipient is not the invoice ingest mailbox
- Tracking email sent count and timestamp
"""

import os
import logging
import base64
from datetime import datetime
import azure.functions as func
from azure.storage.blob import BlobServiceClient
from azure.data.tables import TableServiceClient
from azure.core.exceptions import ResourceNotFoundError
from shared.models import EnrichedInvoice, NotificationMessage, InvoiceTransaction
from shared.graph_client import GraphAPIClient

logger = logging.getLogger(__name__)


def _validate_recipient(recipient: str, invoice_mailbox: str) -> None:
    """
    Validate that recipient is safe for email delivery (loop prevention).

    Raises ValueError if recipient is invalid for email delivery.
    """
    # Validate recipient is not the ingest mailbox (critical loop prevention)
    if recipient.lower() == invoice_mailbox.lower():
        raise ValueError(f"Cannot send to INVOICE_MAILBOX ({recipient}) - would create email loop")

    # Validate recipient is in allowed list (if configured)
    allowed_recipients = os.environ.get("ALLOWED_AP_EMAILS", "").strip()
    if allowed_recipients:
        allowed_list = [email.strip().lower() for email in allowed_recipients.split(",")]
        if recipient.lower() not in allowed_list:
            raise ValueError(f"Recipient {recipient} not in allowed AP email list (ALLOWED_AP_EMAILS)")

    logger.info(f"Recipient validation passed: {recipient}")


def _check_already_processed(raw_mail: dict) -> bool:
    """
    Check if transaction has already been processed (deduplication by message ID).

    Uses Graph API message ID (stable across re-ingestion) instead of ULID
    to detect duplicate processing of the same email.

    Returns: True if already processed, False otherwise
    """
    table_client = TableServiceClient.from_connection_string(os.environ["AzureWebJobsStorage"]).get_table_client(
        "InvoiceTransactions"
    )

    message_id = raw_mail.get("original_message_id")
    if not message_id:
        return False  # No message ID to check, proceed with processing

    try:
        # Query for any existing transaction with this message ID
        filter_query = f"OriginalMessageId eq '{message_id}' and Status eq 'processed'"
        results = list(table_client.query_entities(filter_query))

        if results:
            existing = results[0]
            logger.warning(
                f"Message {message_id} already processed at {existing.get('ProcessedAt')} "
                f"(Transaction {existing.get('RowKey')})"
            )
            return True

    except Exception as e:
        logger.warning(f"Deduplication check failed: {str(e)} - proceeding with processing")
        return False

    return False


def _compose_ap_email(enriched: EnrichedInvoice) -> tuple[str, str]:
    """Compose email body for AP with invoice metadata."""
    subject = f"Invoice: {enriched.vendor_name} - GL {enriched.gl_code}"
    body = f"""
<html>
<body style="font-family: Arial, sans-serif;">
    <h2>Invoice Ready for Processing</h2>
    <table border="1" cellpadding="8" style="border-collapse: collapse;">
        <tr><td><strong>Transaction ID</strong></td><td>{enriched.id}</td></tr>
        <tr><td><strong>Vendor</strong></td><td>{enriched.vendor_name}</td></tr>
        <tr><td><strong>GL Code</strong></td><td>{enriched.gl_code}</td></tr>
        <tr><td><strong>Department</strong></td><td>{enriched.expense_dept}</td></tr>
        <tr><td><strong>Allocation Schedule</strong></td><td>{enriched.allocation_schedule}</td></tr>
        <tr><td><strong>Billing Party</strong></td><td>{enriched.billing_party}</td></tr>
    </table>
    <p>Invoice attachment included.</p>
</body>
</html>
"""
    return subject, body


def _log_transaction(enriched: EnrichedInvoice, recipient_email: str):
    """Log transaction to InvoiceTransactions table with email tracking."""
    table_client = TableServiceClient.from_connection_string(os.environ["AzureWebJobsStorage"]).get_table_client(
        "InvoiceTransactions"
    )
    now = datetime.utcnow().isoformat() + "Z"
    transaction = InvoiceTransaction(
        PartitionKey=datetime.utcnow().strftime("%Y%m"),
        RowKey=enriched.id,
        VendorName=enriched.vendor_name,
        SenderEmail="system@invoice-agent.com",
        RecipientEmail=recipient_email,
        ExpenseDept=enriched.expense_dept,
        GLCode=enriched.gl_code,
        Status="processed",
        BlobUrl=enriched.blob_url,
        ProcessedAt=now,
        EmailsSentCount=1,
        LastEmailSentAt=now,
        OriginalMessageId=enriched.original_message_id,
    )
    table_client.upsert_entity(transaction.model_dump())


def main(msg: func.QueueMessage, notify: func.Out[str]):
    """Send enriched invoice to AP and log transaction."""
    try:
        enriched = EnrichedInvoice.model_validate_json(msg.get_body().decode())

        # Check if transaction already processed (deduplication by message ID)
        if _check_already_processed(enriched.model_dump()):
            logger.info(f"Skipping duplicate transaction {enriched.id}")
            return

        blob_service = BlobServiceClient.from_connection_string(os.environ["AzureWebJobsStorage"])
        blob_client = blob_service.get_blob_client(container="invoices", blob=enriched.blob_url.split("/invoices/")[-1])
        pdf_content = blob_client.download_blob().readall()
        subject, body = _compose_ap_email(enriched)

        graph = GraphAPIClient()
        ap_email = os.environ["AP_EMAIL_ADDRESS"]
        invoice_mailbox = os.environ["INVOICE_MAILBOX"]

        # Validate recipient before sending (loop prevention)
        _validate_recipient(ap_email, invoice_mailbox)

        graph.send_email(
            from_address=os.environ["INVOICE_MAILBOX"],
            to_address=ap_email,
            subject=subject,
            body=body,
            is_html=True,
            attachments=[
                {
                    "name": f"invoice_{enriched.id}.pdf",
                    "contentBytes": base64.b64encode(pdf_content).decode(),
                    "contentType": "application/pdf",
                }
            ],
        )
        _log_transaction(enriched, ap_email)

        notification = NotificationMessage(
            type="success",
            message=f"Processed: {enriched.vendor_name} - GL {enriched.gl_code}",
            details={
                "vendor": enriched.vendor_name,
                "gl_code": enriched.gl_code,
                "transaction_id": enriched.id,
            },
        )
        notify.set(notification.model_dump_json())
        logger.info(f"Posted to AP: {enriched.id} - {enriched.vendor_name}")
    except Exception as e:
        logger.error(f"PostToAP failed: {str(e)}")
        raise
