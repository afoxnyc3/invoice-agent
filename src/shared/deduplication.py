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
from datetime import datetime, timedelta, timezone
from typing import Any
from azure.data.tables import TableServiceClient
from shared.config import config

logger = logging.getLogger(__name__)


def _sanitize_odata_string(value: str | None) -> str:
    """
    Sanitize a string value for use in OData filter queries.

    Escapes single quotes to prevent OData injection attacks.
    Azure Table Storage OData filter syntax requires single quotes
    to be escaped by doubling them.

    Args:
        value: String value to sanitize

    Returns:
        Sanitized string safe for OData queries
    """
    if not value:
        return ""
    return value.replace("'", "''")


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
        # Use centralized config (handles slot swap gracefully)
        table_client = config.get_table_client("InvoiceTransactions")
        if not table_client:
            logger.warning("Storage unavailable - dedup check skipped (fail open)")
            return False

        # Query for ANY existing transaction with this message ID
        # (not just 'processed' - unknown vendor invoices have status='unknown')
        safe_message_id = _sanitize_odata_string(original_message_id)
        filter_query = f"OriginalMessageId eq '{safe_message_id}'"
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
    Generate SHA-256 hash for invoice duplicate detection.

    Uses vendor name (normalized) + sender email (normalized) + date portion
    of received_at timestamp. This detects if same vendor sends same invoice
    on the same day.

    Args:
        vendor_name: Vendor name (will be normalized to lowercase)
        sender_email: Sender email address (will be normalized to lowercase)
        received_at: ISO 8601 timestamp (only date portion used)

    Returns:
        32-character SHA-256 hash string (truncated for storage efficiency)
    """
    vendor_normalized = vendor_name.lower().strip().replace(" ", "_")
    sender_normalized = sender_email.lower().strip()
    date_portion = received_at[:10]  # Extract YYYY-MM-DD from ISO timestamp

    hash_input = f"{vendor_normalized}|{sender_normalized}|{date_portion}"
    # Use SHA-256 (cryptographically secure) instead of MD5, truncate to 32 chars
    return hashlib.sha256(hash_input.encode()).hexdigest()[:32]


def check_duplicate_invoice(invoice_hash: str, lookback_days: int = 90) -> dict[str, Any] | None:
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
        # Use centralized config (handles slot swap gracefully)
        table_client = config.get_table_client("InvoiceTransactions")
        if not table_client:
            logger.warning("Storage unavailable - invoice dedup check skipped")
            return None

        # Calculate partition key range for lookback period
        end_date = datetime.now(timezone.utc).replace(tzinfo=None)
        start_date = end_date - timedelta(days=lookback_days)

        # Query for matching hash (partition key filtering for efficiency)
        safe_hash = _sanitize_odata_string(invoice_hash)
        filter_query = f"InvoiceHash eq '{safe_hash}'"
        results = list(table_client.query_entities(filter_query))

        # Filter by date range using actual ProcessedAt timestamp
        for result in results:
            processed_at = result.get("ProcessedAt", "")
            if processed_at:
                try:
                    # Handle ISO format with Z suffix
                    processed_at_clean = processed_at.replace("Z", "+00:00")
                    record_date = datetime.fromisoformat(processed_at_clean).replace(tzinfo=None)
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
