"""
PostToAP queue function - Send enriched invoices to AP mailbox.

Composes email with all enriched metadata, attaches invoice PDF,
sends to AP, logs transaction, and queues notification.
"""

import os
import logging
import base64
from datetime import datetime
import azure.functions as func
from azure.storage.blob import BlobServiceClient
from azure.data.tables import TableServiceClient
from shared.models import EnrichedInvoice, NotificationMessage, InvoiceTransaction
from shared.graph_client import GraphAPIClient

logger = logging.getLogger(__name__)


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


def _log_transaction(enriched: EnrichedInvoice):
    """Log transaction to InvoiceTransactions table."""
    table_client = TableServiceClient.from_connection_string(os.environ["AzureWebJobsStorage"]).get_table_client(
        "InvoiceTransactions"
    )
    transaction = InvoiceTransaction(
        PartitionKey=datetime.utcnow().strftime("%Y%m"),
        RowKey=enriched.id,
        VendorName=enriched.vendor_name,
        SenderEmail="system@invoice-agent.com",
        ExpenseDept=enriched.expense_dept,
        GLCode=enriched.gl_code,
        Status="processed",
        BlobUrl=enriched.blob_url,
        ProcessedAt=datetime.utcnow().isoformat() + "Z",
    )
    table_client.upsert_entity(transaction.model_dump())


def main(msg: func.QueueMessage, notify: func.Out[str]):
    """Send enriched invoice to AP and log transaction."""
    try:
        enriched = EnrichedInvoice.model_validate_json(msg.get_body().decode())
        blob_service = BlobServiceClient.from_connection_string(os.environ["AzureWebJobsStorage"])
        blob_client = blob_service.get_blob_client(container="invoices", blob=enriched.blob_url.split("/invoices/")[-1])
        pdf_content = blob_client.download_blob().readall()
        subject, body = _compose_ap_email(enriched)

        graph = GraphAPIClient()
        graph.send_email(
            from_address=os.environ["INVOICE_MAILBOX"],
            to_address=os.environ["AP_EMAIL_ADDRESS"],
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
        _log_transaction(enriched)

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
