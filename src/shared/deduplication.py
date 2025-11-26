"""
Deduplication utilities for preventing duplicate email processing.

Provides reusable functions for checking if emails have already been
processed, used by ExtractEnrich and PostToAP to prevent duplicate
vendor registration emails and duplicate AP postings.

Also provides invoice-level duplicate detection to prevent duplicate
payments for the same invoice (same vendor, same day).
"""

import os
import logging
import hashlib
from datetime import datetime, timedelta
from azure.data.tables import TableServiceClient

logger = logging.getLogger(__name__)


def is_message_already_processed(original_message_id: str | None) -> bool:
    """
    Check if an email has already been processed (deduplication by message ID).

    Uses Graph API message ID (stable across re-ingestion) to detect
    duplicate processing of the same email. Checks InvoiceTransactions
    table for any existing record with matching OriginalMessageId.

    Args:
        original_message_id: Graph API message ID from the email

    Returns:
        True if message was already processed (any status), False otherwise
    """
    if not original_message_id:
        return False

    try:
        storage_conn = os.environ["AzureWebJobsStorage"]
        table_client = TableServiceClient.from_connection_string(storage_conn).get_table_client("InvoiceTransactions")

        # Query for ANY existing transaction with this message ID
        # (not just 'processed' - unknown vendor invoices have status='unknown')
        filter_query = f"OriginalMessageId eq '{original_message_id}'"
        results = list(table_client.query_entities(filter_query))

        if results:
            existing = results[0]
            logger.info(
                f"Duplicate detected: message {original_message_id[:30]}... "
                f"already processed at {existing.get('ProcessedAt')} "
                f"with status={existing.get('Status')}"
            )
            return True

    except Exception as e:
        # Fail open: if dedup check fails, proceed with processing
        logger.warning(f"Deduplication check failed: {str(e)} - proceeding")
        return False

    return False


def generate_invoice_hash(vendor_name: str, sender_email: str, received_at: str) -> str:
    """
    Generate MD5 hash for invoice duplicate detection.

    Uses vendor name (normalized) + sender email (normalized) + date portion
    of received_at timestamp. This detects if same vendor sends same invoice
    on the same day.

    Args:
        vendor_name: Vendor name (will be normalized to lowercase)
        sender_email: Sender email address (will be normalized to lowercase)
        received_at: ISO 8601 timestamp (only date portion used)

    Returns:
        32-character MD5 hash string
    """
    vendor_normalized = vendor_name.lower().strip().replace(" ", "_")
    sender_normalized = sender_email.lower().strip()
    date_portion = received_at[:10]  # Extract YYYY-MM-DD from ISO timestamp

    hash_input = f"{vendor_normalized}|{sender_normalized}|{date_portion}"
    return hashlib.md5(hash_input.encode()).hexdigest()


def check_duplicate_invoice(invoice_hash: str, lookback_days: int = 90) -> dict | None:
    """
    Check if an invoice with matching hash exists in the last N days.

    Queries InvoiceTransactions table for any record with matching
    InvoiceHash in the specified lookback period.

    Args:
        invoice_hash: MD5 hash from generate_invoice_hash()
        lookback_days: Number of days to look back (default 90)

    Returns:
        Existing transaction dict if duplicate found, None otherwise
    """
    try:
        storage_conn = os.environ["AzureWebJobsStorage"]
        table_client = TableServiceClient.from_connection_string(storage_conn).get_table_client("InvoiceTransactions")

        # Calculate partition key range for lookback period
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=lookback_days)

        # Query for matching hash (partition key filtering for efficiency)
        filter_query = f"InvoiceHash eq '{invoice_hash}'"
        results = list(table_client.query_entities(filter_query))

        # Filter by date range (partition key is YYYYMM)
        for result in results:
            partition_key = result.get("PartitionKey", "")
            if len(partition_key) == 6:
                year_month = f"{partition_key[:4]}-{partition_key[4:]}-01"
                try:
                    record_date = datetime.fromisoformat(year_month)
                    if start_date <= record_date <= end_date:
                        logger.warning(
                            f"Duplicate invoice detected: hash={invoice_hash[:8]}... "
                            f"matches existing transaction {result.get('RowKey')}"
                        )
                        return dict(result)
                except ValueError:
                    continue

    except Exception as e:
        # Fail open: if dedup check fails, proceed with processing
        logger.warning(f"Invoice duplicate check failed: {str(e)} - proceeding")
        return None

    return None
