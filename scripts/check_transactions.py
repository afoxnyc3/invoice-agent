#!/usr/bin/env python3
"""
Check InvoiceTransactions table for processed invoices.

Usage:
    python scripts/check_transactions.py [hours_ago]

Args:
    hours_ago: Look back this many hours (default: 1)

Environment:
    INVOICE_MAILBOX must be set (for authentication scope only)
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from azure.data.tables import TableClient
from azure.identity import DefaultAzureCredential
from shared.logger import get_logger

logger = get_logger(__name__)


def check_transactions(hours_ago: int = 1):
    """Check recent transactions in InvoiceTransactions table."""
    try:
        # Get storage account name from environment (derived from pattern)
        # or pass via STORAGE_ACCOUNT env var
        storage_account = os.environ.get("STORAGE_ACCOUNT", "stinvoiceagentprod")
        table_name = "InvoiceTransactions"

        # Construct table URL
        table_url = f"https://{storage_account}.table.core.windows.net"

        # Use DefaultAzureCredential (same as production)
        credential = DefaultAzureCredential()
        client = TableClient(table_url, table_name, credential=credential)

        # Calculate time range
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_ago)
        cutoff_iso = cutoff_time.isoformat() + "Z"

        print(f"\n📊 InvoiceTransactions Table ({storage_account}):")
        print(f"   Table: {table_name}")
        print(f"   Looking back: {hours_ago} hour(s)")
        print(f"   Since: {cutoff_iso}\n")

        # Query recent transactions
        # Note: Table Storage queries use ISO format and OData syntax
        query_filter = f"CreatedAt gt datetime'{cutoff_iso}'"

        try:
            entities = client.query_entities(filter=query_filter)
            transactions = list(entities)

            if transactions:
                print(f"   ✅ Found {len(transactions)} transaction(s):")
                for i, txn in enumerate(transactions, 1):
                    sender = txn.get("Sender", "Unknown")
                    subject = txn.get("Subject", "No subject")
                    status = txn.get("Status", "Unknown")
                    vendor = txn.get("VendorName", "Unknown")
                    msg_id = txn.get("OriginalMessageId", "N/A")
                    timestamp = txn.get("CreatedAt", "N/A")

                    print(f"\n      Transaction {i}:")
                    print(f"         Status: {status}")
                    print(f"         Vendor: {vendor}")
                    print(f"         From: {sender}")
                    print(f"         Subject: {subject}")
                    print(f"         Message ID: {msg_id}")
                    print(f"         Timestamp: {timestamp}")
            else:
                print(f"   ⚠️  No transactions in the past {hours_ago} hour(s)")

        except Exception as e:
            print(f"   ⚠️  Could not query table: {e}")
            print(f"      Make sure you have access to storage account '{storage_account}'")
            print(f"      and table '{table_name}' exists")

    except Exception as e:
        logger.error(f"Failed to check transactions: {e}")
        print(f"\n❌ Error: {e}")
        print(f"   Check that Azure credentials are configured (DefaultAzureCredential)")
        return False

    return True


if __name__ == "__main__":
    hours = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    check_transactions(hours)
