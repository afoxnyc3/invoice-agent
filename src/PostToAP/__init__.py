"""
PostToAP queue function - Send enriched invoices to AP mailbox.

Composes email with all enriched metadata, attaches invoice PDF,
sends to AP, logs transaction, and queues notification.

Implements email loop prevention by:
- Checking if transaction already processed (deduplication)
- Validating recipient is not the invoice ingest mailbox
- Tracking email sent count and timestamp
"""

import logging
import base64
from datetime import datetime, timezone
import azure.functions as func
from shared.config import config
from shared.models import EnrichedInvoice, NotificationMessage, InvoiceTransaction
from shared.graph_client import GraphAPIClient
from shared.deduplication import is_message_already_processed, check_duplicate_invoice

logger = logging.getLogger(__name__)


def _validate_recipient(recipient: str) -> None:
    """
    Validate that recipient is safe for email delivery (loop prevention).

    Raises ValueError if recipient is invalid for email delivery.
    """
    # Validate recipient is not the ingest mailbox (critical loop prevention)
    if recipient.lower() == config.invoice_mailbox.lower():
        raise ValueError(f"Cannot send to INVOICE_MAILBOX ({recipient}) - would create email loop")

    # Validate recipient is in allowed list (if configured)
    allowed_list = config.allowed_ap_emails
    if allowed_list and recipient.lower() not in allowed_list:
        msg = f"Recipient {recipient} not in allowed AP email list (ALLOWED_AP_EMAILS)"
        raise ValueError(msg)

    logger.info(f"Recipient validation passed: {recipient}")


def _compose_ap_email(enriched: EnrichedInvoice) -> tuple[str, str]:
    """Compose email body for AP with invoice metadata."""
    subject = f"Invoice: {enriched.vendor_name} - GL {enriched.gl_code}"
    alloc_label = "Allocation Schedule"

    # Format invoice amount if available
    amount_display = "N/A"
    if enriched.invoice_amount:
        currency = enriched.currency or "USD"
        amount_display = f"{currency} {enriched.invoice_amount:,.2f}"

    # Format due date if available
    due_date_display = enriched.due_date[:10] if enriched.due_date else "N/A"

    body = f"""
<html>
<body style="font-family: Arial, sans-serif;">
    <h2>Invoice Ready for Processing</h2>
    <table border="1" cellpadding="8" style="border-collapse: collapse;">
        <tr><td><strong>Transaction ID</strong></td><td>{enriched.id}</td></tr>
        <tr><td><strong>Vendor</strong></td><td>{enriched.vendor_name}</td></tr>
        <tr><td><strong>Invoice Amount</strong></td><td>{amount_display}</td></tr>
        <tr><td><strong>Due Date</strong></td><td>{due_date_display}</td></tr>
        <tr><td><strong>Payment Terms</strong></td><td>{enriched.payment_terms or 'Net 30'}</td></tr>
        <tr><td><strong>GL Code</strong></td><td>{enriched.gl_code}</td></tr>
        <tr><td><strong>Department</strong></td><td>{enriched.expense_dept}</td></tr>
        <tr><td><strong>{alloc_label}</strong></td><td>{enriched.allocation_schedule}\
</td></tr>
        <tr><td><strong>Billing Party</strong></td><td>{enriched.billing_party}</td></tr>
    </table>
    <p>Invoice attachment included.</p>
</body>
</html>
"""
    return subject, body


def _log_transaction(enriched: EnrichedInvoice, recipient_email: str):
    """Log transaction to InvoiceTransactions table with email tracking."""
    table_client = config.get_table_client("InvoiceTransactions")
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    transaction = InvoiceTransaction(
        PartitionKey=datetime.now(timezone.utc).strftime("%Y%m"),
        RowKey=enriched.id,
        VendorName=enriched.vendor_name,
        SenderEmail=enriched.sender_email or "system@invoice-agent.com",
        RecipientEmail=recipient_email,
        ExpenseDept=enriched.expense_dept,
        GLCode=enriched.gl_code,
        Status="processed",
        BlobUrl=enriched.blob_url,
        ProcessedAt=now,
        EmailsSentCount=1,
        LastEmailSentAt=now,
        OriginalMessageId=enriched.original_message_id,
        InvoiceHash=enriched.invoice_hash,
    )
    table_client.upsert_entity(transaction.model_dump())


def main(msg: func.QueueMessage, notify: func.Out[str]):
    """Send enriched invoice to AP and log transaction."""
    try:
        enriched = EnrichedInvoice.model_validate_json(msg.get_body().decode())

        # Check if transaction already processed (deduplication by message ID)
        if is_message_already_processed(enriched.original_message_id):
            logger.info(f"Skipping duplicate transaction {enriched.id}")
            return

        # Check for duplicate invoice (same vendor + sender + date)
        if enriched.invoice_hash:
            existing = check_duplicate_invoice(enriched.invoice_hash)
            if existing:
                logger.warning(f"Duplicate invoice detected for {enriched.vendor_name} ({enriched.id})")
                notification = NotificationMessage(
                    type="duplicate",
                    message=f"Duplicate Invoice: {enriched.vendor_name}",
                    details={
                        "vendor": enriched.vendor_name,
                        "transaction_id": enriched.id,
                        "original_transaction": existing.get("RowKey", "unknown"),
                        "original_date": existing.get("ProcessedAt", "unknown"),
                    },
                )
                notify.set(notification.model_dump_json())
                return

        # Download invoice PDF from blob storage
        blob_name = enriched.blob_url.split("/invoices/")[-1]
        blob_client = config.blob_service.get_blob_client(container="invoices", blob=blob_name)
        pdf_content = blob_client.download_blob().readall()
        subject, body = _compose_ap_email(enriched)

        # Validate recipient before sending (loop prevention)
        ap_email = config.ap_email_address
        _validate_recipient(ap_email)

        # Send email to AP with invoice attachment
        graph = GraphAPIClient()
        graph.send_email(
            from_address=config.invoice_mailbox,
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
