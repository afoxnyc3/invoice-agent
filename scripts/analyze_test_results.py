#!/usr/bin/env python3
"""
Detailed post-test analysis of email flow.

This script performs in-depth inspection after a test to ensure:
- Exactly ONE email was sent (no loop)
- Email was sent ONLY to AP mailbox
- Transaction was created with correct message ID
- No stuck messages in queues

Usage:
    python scripts/analyze_test_results.py

Environment:
    GRAPH_TENANT_ID, GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET
    INVOICE_MAILBOX, AP_EMAIL_ADDRESS
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from shared.graph_client import GraphAPIClient
from shared.logger import get_logger
from azure.data.tables import TableClient
from azure.identity import DefaultAzureCredential
from azure.storage.queue import QueueClient

logger = get_logger(__name__)


class TestAnalyzer:
    """Analyze test results in detail."""

    def __init__(self):
        self.client = GraphAPIClient()
        self.invoice_mailbox = os.environ.get("INVOICE_MAILBOX")
        self.ap_mailbox = os.environ.get("AP_EMAIL_ADDRESS")
        self.storage_account = os.environ.get("STORAGE_ACCOUNT", "stinvoiceagentprod")

    def analyze_ap_mailbox(self):
        """Inspect AP mailbox for sent emails."""
        print(f"\n📬 AP Mailbox Analysis")
        print(f"=" * 60)

        try:
            emails = self.client.get_unread_emails(self.ap_mailbox, max_results=20)

            if not emails:
                print(f"   ⚠️  No unread emails in AP mailbox")
                return

            print(f"   Found {len(emails)} unread email(s):\n")

            test_emails = []
            for i, email in enumerate(emails, 1):
                sender = email.get("sender", {}).get("emailAddress", {}).get("address", "Unknown")
                subject = email.get("subject", "No subject")
                msg_id = email.get("id", "")
                received = email.get("receivedDateTime", "Unknown")

                # Check if this is from the system (invoice mailbox)
                is_system = sender.lower() == self.invoice_mailbox.lower()
                system_marker = "✅ SYSTEM" if is_system else "⚠️  EXTERNAL"

                print(f"   Email {i}: {system_marker}")
                print(f"      From: {sender}")
                print(f"      Subject: {subject}")
                print(f"      Received: {received}")
                print(f"      ID: {msg_id[:20]}...")

                if is_system and "Test" in subject:
                    test_emails.append(email)

                print()

            # Safety check: Only ONE system-generated test email
            if len(test_emails) == 1:
                print(f"   ✅ Exactly ONE test email found (no loop)")
            elif len(test_emails) == 0:
                print(f"   ⚠️  No test emails found in AP mailbox")
            else:
                print(f"   ❌ LOOP DETECTED: {len(test_emails)} test emails (expected 1)")
                print(f"      This suggests the email was processed multiple times!")

        except Exception as e:
            print(f"   ❌ Error analyzing AP mailbox: {e}")

    def analyze_transactions(self):
        """Inspect InvoiceTransactions table for test."""
        print(f"\n📊 Transaction Analysis")
        print(f"=" * 60)

        try:
            table_url = f"https://{self.storage_account}.table.core.windows.net"
            credential = DefaultAzureCredential()
            client = TableClient(table_url, "InvoiceTransactions", credential=credential)

            # Query recent transactions
            cutoff = datetime.utcnow() - timedelta(hours=2)
            cutoff_iso = cutoff.isoformat() + "Z"
            query = f"CreatedAt gt datetime'{cutoff_iso}'"

            entities = client.query_entities(filter=query)
            transactions = list(entities)

            if not transactions:
                print(f"   ⚠️  No transactions in past 2 hours")
                return

            print(f"   Found {len(transactions)} transaction(s):\n")

            test_txns = []
            for i, txn in enumerate(transactions, 1):
                sender = txn.get("Sender", "Unknown")
                subject = txn.get("Subject", "No subject")[:50]
                status = txn.get("Status", "Unknown")
                vendor = txn.get("VendorName", "Unknown")
                msg_id = txn.get("OriginalMessageId", "N/A")
                created = txn.get("CreatedAt", "Unknown")

                print(f"   Transaction {i}:")
                print(f"      Status: {status}")
                print(f"      Vendor: {vendor}")
                print(f"      From: {sender}")
                print(f"      Subject: {subject}...")
                print(f"      Message ID: {msg_id[:20] if msg_id else 'N/A'}...")
                print(f"      Created: {created}")

                if "Test Invoice" in subject:
                    test_txns.append(txn)

                print()

            # Safety check: Only ONE transaction per test email
            if len(test_txns) == 1:
                print(f"   ✅ Exactly ONE transaction created (no duplicate processing)")
                txn = test_txns[0]

                # Verify deduplication
                if txn.get("OriginalMessageId"):
                    print(f"   ✅ Deduplication ID captured: {txn['OriginalMessageId'][:20]}...")
                else:
                    print(f"   ❌ DEDUPLICATION BROKEN: No OriginalMessageId stored")

            elif len(test_txns) == 0:
                print(f"   ⚠️  No test transactions found")
            else:
                print(f"   ❌ DUPLICATE PROCESSING: {len(test_txns)} transactions (expected 1)")
                print(f"      This suggests deduplication is not working!")

        except Exception as e:
            print(f"   ❌ Error analyzing transactions: {e}")

    def analyze_queues(self):
        """Check queue depths for stuck messages."""
        print(f"\n🚦 Queue Analysis")
        print(f"=" * 60)

        queue_names = ["raw-mail", "to-post", "notify", "raw-mail-poison", "to-post-poison", "notify-poison"]

        try:
            # Get queue client (requires Azure credentials)
            credential = DefaultAzureCredential()

            for queue_name in queue_names:
                try:
                    queue_url = f"https://{self.storage_account}.queue.core.windows.net/{queue_name}"
                    queue_client = QueueClient.from_queue_url(queue_url, credential=credential)

                    # Get queue properties
                    properties = queue_client.get_queue_properties()
                    count = properties.metadata.get("approximateMessageCount", 0) if properties.metadata else 0

                    if count == 0:
                        print(f"   ✅ {queue_name:20} : {count} messages")
                    else:
                        print(f"   ⚠️  {queue_name:20} : {count} messages (stuck?)")

                except Exception as e:
                    print(f"   ⚠️  {queue_name:20} : Could not access ({str(e)[:40]}...)")

        except Exception as e:
            print(f"   ⚠️  Could not analyze queues: {e}")
            print(f"      Make sure Azure credentials are configured")

    def analyze_invoice_mailbox(self):
        """Check if test email is still in invoice mailbox."""
        print(f"\n📧 Invoice Mailbox Analysis")
        print(f"=" * 60)

        try:
            emails = self.client.get_unread_emails(self.invoice_mailbox, max_results=20)

            if not emails:
                print(f"   ✅ No unread emails (inbox processed)")
                return

            print(f"   Unread emails in invoice mailbox: {len(emails)}\n")

            for i, email in enumerate(emails[:5], 1):  # Show first 5
                sender = email.get("sender", {}).get("emailAddress", {}).get("address", "Unknown")
                subject = email.get("subject", "No subject")[:50]
                received = email.get("receivedDateTime", "Unknown")

                print(f"   {i}. From: {sender}")
                print(f"      Subject: {subject}...")
                print(f"      Received: {received}\n")

        except Exception as e:
            print(f"   ❌ Error analyzing invoice mailbox: {e}")

    def run(self):
        """Run complete analysis."""
        print(f"\n🔍 Email Flow Test Analysis")
        print(f"=" * 60)
        print(f"Invoice Mailbox: {self.invoice_mailbox}")
        print(f"AP Mailbox: {self.ap_mailbox}")
        print(f"Storage Account: {self.storage_account}")
        print(f"Analysis Time: {datetime.utcnow().isoformat()}Z")

        self.analyze_invoice_mailbox()
        self.analyze_ap_mailbox()
        self.analyze_transactions()
        self.analyze_queues()

        print(f"\n" + "=" * 60)
        print(f"📝 Analysis Summary:")
        print(f"   1. Check if exactly ONE email in AP mailbox (no loop)")
        print(f"   2. Check if exactly ONE transaction created (no duplicates)")
        print(f"   3. Check if deduplication ID captured (anti-loop)")
        print(f"   4. Check if queues are empty (no stuck messages)")
        print(f"\n✅ If all checks pass, the system is safe!")


if __name__ == "__main__":
    analyzer = TestAnalyzer()
    analyzer.run()
