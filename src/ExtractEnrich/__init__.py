"""
ExtractEnrich queue function - Extract vendor and enrich with GL codes.

Looks up vendor in VendorMaster table by vendor name. Implements:
- Case-insensitive vendor name matching using "contains" logic
- Special handling for reseller vendors (e.g., Myriad360) that require product extraction
- Venue extraction from invoice metadata
- Unknown vendor handling with registration email
"""

import logging
from datetime import datetime, timezone
from typing import Any, Literal
import azure.functions as func
from azure.core.exceptions import ResourceExistsError
from azure.data.tables import TableClient
from shared.config import config
from shared.models import RawMail, EnrichedInvoice, InvoiceTransaction
from shared.graph_client import GraphAPIClient
from shared.email_composer import compose_unknown_vendor_email
from shared.email_parser import extract_domain
from shared.deduplication import is_message_already_processed, generate_invoice_hash
from shared.pdf_extractor import extract_invoice_fields_from_pdf
from shared.ulid_generator import utc_now_iso

logger = logging.getLogger(__name__)


def _find_vendor_by_name(vendor_name: str, table_client: TableClient) -> dict[str, Any] | None:
    """
    Find vendor in VendorMaster table using case-insensitive contains matching.

    Returns the vendor entity if found, None otherwise.
    """
    if not vendor_name or not vendor_name.strip():
        return None

    vendor_lower = vendor_name.lower().strip()

    try:
        # Query all vendors and do case-insensitive contains matching
        vendors = list(table_client.query_entities("PartitionKey eq 'Vendor' and Active eq true"))

        for vendor in vendors:
            # Exact match on normalized RowKey
            if vendor["RowKey"] == vendor_lower.replace(" ", "_").replace("-", "_"):
                return vendor
            # Contains match on VendorName (case-insensitive)
            if vendor_lower in vendor["VendorName"].lower():
                return vendor

        return None
    except Exception as e:
        logger.error(f"Error querying vendors: {str(e)}")
        return None


def _send_vendor_registration_email(vendor_name: str, transaction_id: str, sender: str) -> None:
    """Send vendor registration instructions to requestor."""
    subject, body = compose_unknown_vendor_email(vendor_name, transaction_id, config.function_app_url)
    graph = GraphAPIClient()
    graph.send_email(
        from_address=config.invoice_mailbox,
        to_address=sender,
        subject=subject,
        body=body,
        is_html=True,
    )
    sender_domain = sender.split("@")[1] if "@" in sender else "unknown"
    logger.warning(f"Unknown vendor: {vendor_name} - sent registration email to domain {sender_domain}")


def _get_existing_transaction(original_message_id: str | None, table_client: TableClient) -> dict[str, Any] | None:
    """Return existing unknown vendor transaction for the original message if present."""
    if not original_message_id:
        return None

    try:
        safe_message_id = original_message_id.replace("'", "''")
        # Only check for unknown vendor transactions to prevent duplicate registration emails
        filter_query = f"OriginalMessageId eq '{safe_message_id}' and Status eq 'unknown'"
        results = list(table_client.query_entities(filter_query))
        # Filter out non-transaction entities (like vendors) that don't have Status field
        transactions = [r for r in results if r.get("Status") == "unknown"]
        return transactions[0] if transactions else None
    except Exception as exc:  # pragma: no cover - defensive logging only
        logger.warning(f"Transaction lookup failed: {exc}")
        return None


def _try_claim_transaction(raw_mail: RawMail, vendor_name: str, table_client: TableClient) -> bool:
    """
    Attempt to claim a transaction by inserting it atomically.

    Uses create_entity to atomically check-and-set. Returns True if this
    instance successfully claimed the transaction, False if another instance
    already claimed it (preventing duplicate emails).

    This solves the race condition where multiple concurrent function instances
    might process the same message and send duplicate registration emails.
    """
    now = utc_now_iso()
    transaction = InvoiceTransaction(
        PartitionKey=datetime.now(timezone.utc).strftime("%Y%m"),
        RowKey=raw_mail.id,
        VendorName=vendor_name,
        SenderEmail=raw_mail.sender,
        RecipientEmail=raw_mail.sender,  # Registration email sent to requestor
        ExpenseDept="Unknown",
        GLCode="0000",
        Status="unknown",
        BlobUrl=raw_mail.blob_url,
        ProcessedAt=now,
        ErrorMessage=None,
        EmailsSentCount=1,  # Will be set to 1 if email sent successfully
        OriginalMessageId=raw_mail.original_message_id,
        LastEmailSentAt=now,  # Timestamp when registration email sent
    )
    try:
        table_client.create_entity(transaction.model_dump())
        return True  # Successfully claimed - this instance should send the email
    except ResourceExistsError:
        logger.info(f"Transaction {raw_mail.id} already claimed by another instance, skipping email")
        return False  # Another instance already claimed - don't send duplicate email


def _create_enriched_invoice(
    raw_mail: RawMail,
    vendor_name: str,
    expense_dept: str,
    gl_code: str,
    allocation_schedule: str,
    status: Literal["enriched", "unknown"],
    invoice_fields: dict[str, Any],
) -> EnrichedInvoice:
    """Create EnrichedInvoice with common fields populated."""
    invoice_hash = generate_invoice_hash(vendor_name, raw_mail.sender, raw_mail.received_at)
    return EnrichedInvoice(
        id=raw_mail.id,
        vendor_name=vendor_name,
        expense_dept=expense_dept,
        gl_code=gl_code,
        allocation_schedule=allocation_schedule,
        billing_party=config.default_billing_party,
        blob_url=raw_mail.blob_url,
        original_message_id=raw_mail.original_message_id,
        status=status,
        sender_email=raw_mail.sender,
        received_at=raw_mail.received_at,
        invoice_hash=invoice_hash,
        invoice_amount=invoice_fields.get("invoice_amount"),
        currency=invoice_fields.get("currency", "USD"),
        due_date=invoice_fields.get("due_date"),
        payment_terms=invoice_fields.get("payment_terms", "Net 30"),
    )


def main(msg: func.QueueMessage, toPost: func.Out[str]) -> None:
    """Extract vendor and enrich invoice data."""
    try:
        raw_mail = RawMail.model_validate_json(msg.get_body().decode())

        # Deduplication: Skip if already processed (prevents duplicate registration emails)
        if is_message_already_processed(raw_mail.original_message_id):
            logger.info(f"Skipping duplicate message {raw_mail.id}")
            return

        # Extract invoice fields from PDF (amount, currency, due date, payment terms)
        invoice_fields = extract_invoice_fields_from_pdf(raw_mail.blob_url, raw_mail.received_at)
        logger.info(f"Invoice field extraction confidence: {invoice_fields.get('confidence', {})}")

        # Use centralized config for table clients (connection pooling)
        table_client = config.get_table_client("VendorMaster")
        tx_table = config.get_table_client("InvoiceTransactions")
        existing_tx = _get_existing_transaction(raw_mail.original_message_id, tx_table)
        if existing_tx:
            logger.info(
                "Skipping processing for already handled message %s (status: %s)",
                raw_mail.original_message_id,
                existing_tx.get("Status", "unknown"),
            )
            return

        # Try vendor name first (from PDF extraction, future phase)
        vendor_name = raw_mail.vendor_name
        vendor = None

        if vendor_name:
            vendor = _find_vendor_by_name(vendor_name, table_client)

        # Fallback to email domain extraction (MVP phase)
        if not vendor and raw_mail.sender:
            try:
                domain = extract_domain(raw_mail.sender)
                # Extract company name from domain (e.g., "adobe_com" -> "adobe")
                company_name = domain.split("_")[0]
                vendor = _find_vendor_by_name(company_name, table_client)
                if vendor:
                    logger.info(f"Vendor matched via email domain: {company_name} -> {vendor['VendorName']}")
                    vendor_name = company_name
            except (ValueError, IndexError):
                sender_domain = raw_mail.sender.split("@")[1] if "@" in raw_mail.sender else "unknown"
                logger.warning(f"Could not extract domain from sender domain: {sender_domain}")

        # If still no vendor found, mark as unknown
        if not vendor:
            if not vendor_name:
                vendor_name = extract_domain(raw_mail.sender).split("_")[0]
            logger.warning(f"Vendor not found: {vendor_name} ({raw_mail.id})")

            # Try to claim transaction first (atomic operation prevents race condition)
            # Only send email if this instance successfully claims the transaction
            if _try_claim_transaction(raw_mail, vendor_name, tx_table):
                _send_vendor_registration_email(vendor_name, raw_mail.id, raw_mail.sender)

            # Queue with unknown status for downstream processing (always queue)
            enriched = _create_enriched_invoice(
                raw_mail, vendor_name, "Unknown", "0000", "Unknown", "unknown", invoice_fields
            )
            toPost.set(enriched.model_dump_json())
            return

        # Special handling for resellers (e.g., Myriad360) - flag for manual review
        if vendor.get("ProductCategory") == "Reseller":
            logger.warning(
                f"Reseller vendor detected: {vendor['VendorName']} ({raw_mail.id}) - flagging for manual review"
            )
            enriched = _create_enriched_invoice(
                raw_mail, vendor["VendorName"], "Unknown", "0000", "Unknown", "unknown", invoice_fields
            )
            toPost.set(enriched.model_dump_json())
            return

        # Vendor found - enrich with GL codes and metadata
        enriched = _create_enriched_invoice(
            raw_mail,
            vendor["VendorName"],
            vendor["ExpenseDept"],
            vendor["GLCode"],
            vendor["AllocationSchedule"],
            "enriched",
            invoice_fields,
        )
        toPost.set(enriched.model_dump_json())
        logger.info(f"Enriched: {raw_mail.id} - {vendor['VendorName']} (GL: {vendor['GLCode']})")

    except Exception as e:
        logger.error(f"ExtractEnrich failed: {str(e)}")
        raise
