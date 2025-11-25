"""
Deduplication utilities for preventing duplicate email processing.

Provides reusable functions for checking if emails have already been
processed, used by ExtractEnrich and PostToAP to prevent duplicate
vendor registration emails and duplicate AP postings.
"""

import os
import logging
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
