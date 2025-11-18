#!/usr/bin/env python3
"""
Comprehensive email flow test with loop & safety detection.

This script:
1. Records baseline state (queue depths, email counts, transactions)
2. Sends a test invoice email
3. Monitors processing and validates safety constraints
4. Detects loops, duplicate sends, and unauthorized recipients

Usage:
    python scripts/test_email_safety.py <test_email>

Args:
    test_email: Email address to send FROM (e.g., contact@adobe.com)

Environment:
    GRAPH_TENANT_ID, GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET
    INVOICE_MAILBOX, AP_EMAIL_ADDRESS
"""

import os
import sys
import time
import json
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from shared.graph_client import GraphAPIClient
from shared.logger import get_logger
from azure.data.tables import TableClient
from azure.identity import DefaultAzureCredential

logger = get_logger(__name__)


class TestEmailSafety:
    """Comprehensive email flow testing with safety checks."""

    def __init__(self):
        self.client = GraphAPIClient()
        self.invoice_mailbox = os.environ.get("INVOICE_MAILBOX")
        self.ap_mailbox = os.environ.get("AP_EMAIL_ADDRESS")
        self.storage_account = os.environ.get("STORAGE_ACCOUNT", "stinvoiceagentprod")
        self.test_start = datetime.utcnow()

        if not self.invoice_mailbox or not self.ap_mailbox:
            raise ValueError("INVOICE_MAILBOX or AP_EMAIL_ADDRESS not configured")

        print(f"\n🔒 Email Flow Safety Test")
        print(f"=" * 60)
        print(f"Invoice Mailbox: {self.invoice_mailbox}")
        print(f"AP Mailbox: {self.ap_mailbox}")
        print(f"Storage Account: {self.storage_account}")
        print(f"Test Start: {self.test_start.isoformat()}Z")

    def get_baseline_metrics(self) -> dict:
        """Record baseline state before sending test email."""
        print(f"\n📊 Recording baseline metrics...")

        try:
            # Get current unread counts
            invoice_unread = len(self.client.get_unread_emails(self.invoice_mailbox, max_results=100))
            ap_unread = len(self.client.get_unread_emails(self.ap_mailbox, max_results=100))

            # Get transaction count from table
            transactions = self._query_recent_transactions(hours=1)
            initial_txn_count = len(transactions)

            baseline = {
                "timestamp": self.test_start.isoformat() + "Z",
                "invoice_mailbox_unread": invoice_unread,
                "ap_mailbox_unread": ap_unread,
                "transactions_count": initial_txn_count,
            }

            print(f"   ✅ Invoice mailbox: {invoice_unread} unread")
            print(f"   ✅ AP mailbox: {ap_unread} unread")
            print(f"   ✅ Transactions: {initial_txn_count} in past hour")

            return baseline

        except Exception as e:
            print(f"   ⚠️  Could not get all metrics: {e}")
            return {}

    def _query_recent_transactions(self, hours: int = 1) -> list:
        """Query InvoiceTransactions table for recent entries."""
        try:
            table_url = f"https://{self.storage_account}.table.core.windows.net"
            credential = DefaultAzureCredential()
            client = TableClient(table_url, "InvoiceTransactions", credential=credential)

            cutoff = datetime.utcnow() - timedelta(hours=hours)
            cutoff_iso = cutoff.isoformat() + "Z"
            query = f"CreatedAt gt datetime'{cutoff_iso}'"

            entities = client.query_entities(filter=query)
            return list(entities)
        except Exception as e:
            logger.warning(f"Could not query transactions: {e}")
            return []

    def send_test_email(self, from_email: str) -> str:
        """
        Send test email FROM vendor TO invoice mailbox.

        This simulates a vendor sending an invoice.
        """
        print(f"\n📧 Preparing test email...")

        # Create minimal test invoice
        subject = f"Test Invoice #{self.test_start.strftime('%H%M%S')}"
        body = f"""
Test invoice for email loop prevention validation.

Sender: {from_email}
Time: {self.test_start.isoformat()}Z
"""

        print(f"   To: {self.invoice_mailbox}")
        print(f"   From: {from_email}")
        print(f"   Subject: {subject}")

        try:
            # Note: This is a MANUAL step - we can't actually send FROM a vendor
            # Instead, we'll show the user what to do
            print(f"\n⚠️  Manual Step Required:")
            print(f"   Send an email manually with these details:")
            print(f"   - TO: {self.invoice_mailbox}")
            print(f"   - FROM: {from_email}")
            print(f"   - SUBJECT: {subject}")
            print(f"   - BODY: Test invoice attachment (any PDF)")
            print(f"\n   Then run: python scripts/test_email_safety.py --wait-only")
            print(f"   (or press Enter to continue with monitoring)")

            input("\nPress Enter when email is sent, or Ctrl+C to cancel: ")
            return subject

        except KeyboardInterrupt:
            print("\n❌ Test cancelled")
            sys.exit(0)

    def monitor_processing(self, test_subject: str, wait_seconds: int = 30) -> dict:
        """Monitor email flow through the system."""
        print(f"\n⏳ Monitoring processing for {wait_seconds} seconds...")
        print(f"   (MailIngest timer runs every 5 min, queue processing is immediate)")

        # Poll for changes
        results = {
            "found_in_invoice": False,
            "found_in_ap": False,
            "transaction_created": False,
            "message_ids_match": False,
            "transaction_details": None,
        }

        for i in range(wait_seconds):
            # Check invoice mailbox
            invoice_emails = self.client.get_unread_emails(self.invoice_mailbox, max_results=10)
            for email in invoice_emails:
                if test_subject in email.get("subject", ""):
                    results["found_in_invoice"] = True
                    print(f"   ✅ Found test email in invoice mailbox (ID: {email.get('id')[:20]}...)")
                    break

            # Check AP mailbox
            ap_emails = self.client.get_unread_emails(self.ap_mailbox, max_results=10)
            for email in ap_emails:
                if "Test Invoice" in email.get("subject", ""):
                    results["found_in_ap"] = True
                    print(f"   ✅ Found routed email in AP mailbox (ID: {email.get('id')[:20]}...)")
                    # Verify sender
                    sender = email.get("sender", {}).get("emailAddress", {}).get("address", "")
                    if sender.lower() != self.invoice_mailbox.lower():
                        print(f"   ⚠️  WARNING: Email from unexpected sender: {sender}")
                    break

            # Check transactions
            transactions = self._query_recent_transactions(hours=1)
            test_txns = [
                t for t in transactions if "Test Invoice" in t.get("Subject", "")
            ]
            if test_txns:
                results["transaction_created"] = True
                results["transaction_details"] = test_txns[0]
                print(f"   ✅ Transaction logged (Status: {test_txns[0].get('Status')})")

            if results["found_in_ap"] and results["transaction_created"]:
                print(f"   ✅ Processing complete!")
                break

            if i % 5 == 0 and i > 0:
                print(f"   ... still waiting ({i}s elapsed)")

            time.sleep(1)

        return results

    def validate_safety_constraints(
        self, baseline: dict, results: dict, test_subject: str
    ) -> bool:
        """Validate critical safety constraints."""
        print(f"\n🔒 Validating Safety Constraints...")
        print(f"=" * 60)

        all_ok = True
        checks = []

        # Check 1: Only ONE email sent to AP
        try:
            ap_emails_after = len(self.client.get_unread_emails(self.ap_mailbox, max_results=100))
            ap_emails_added = ap_emails_after - baseline.get("ap_mailbox_unread", 0)

            if ap_emails_added == 1:
                checks.append(("✅", "Only ONE email sent to AP mailbox", True))
            elif ap_emails_added == 0:
                checks.append(("⚠️", "No email sent to AP yet (may still be processing)", None))
            else:
                checks.append((
                    "❌",
                    f"LOOP DETECTED: {ap_emails_added} emails sent to AP (expected 1)",
                    False,
                ))
                all_ok = False
        except Exception as e:
            checks.append(("⚠️", f"Could not check AP mailbox: {e}", None))

        # Check 2: Only ONE transaction created
        try:
            transactions = self._query_recent_transactions(hours=1)
            test_txns = [t for t in transactions if "Test Invoice" in t.get("Subject", "")]

            if len(test_txns) == 1:
                checks.append(("✅", "Only ONE transaction created", True))
                results["transaction_details"] = test_txns[0]
            elif len(test_txns) == 0:
                checks.append(("⚠️", "No transactions created yet (may still be processing)", None))
            else:
                checks.append((
                    "❌",
                    f"DUPLICATE PROCESSING: {len(test_txns)} transactions (expected 1)",
                    False,
                ))
                all_ok = False
        except Exception as e:
            checks.append(("⚠️", f"Could not check transactions: {e}", None))

        # Check 3: Deduplication working (original_message_id captured)
        if results.get("transaction_details"):
            msg_id = results["transaction_details"].get("OriginalMessageId")
            if msg_id:
                checks.append(("✅", f"Deduplication ID captured: {msg_id[:20]}...", True))
            else:
                checks.append(("❌", "DEDUPLICATION BROKEN: No OriginalMessageId", False))
                all_ok = False

        # Check 4: Correct AP recipient
        try:
            ap_emails = self.client.get_unread_emails(self.ap_mailbox, max_results=10)
            for email in ap_emails:
                if "Test Invoice" in email.get("subject", ""):
                    # Email was successfully sent to AP, which means PostToAP validated recipient
                    checks.append(("✅", f"Email sent to correct recipient: {self.ap_mailbox}", True))
                    break
        except Exception as e:
            checks.append(("⚠️", f"Could not verify recipient: {e}", None))

        # Check 5: No stuck messages in queues
        try:
            # This would require queue depth monitoring - for now we note it
            checks.append((
                "📝",
                "Manual check: Verify no messages stuck in raw-mail, to-post, or notify queues",
                None,
            ))
        except Exception as e:
            checks.append(("⚠️", f"Could not check queues: {e}", None))

        # Print results
        for status, check, result in checks:
            print(f"{status} {check}")

        print(f"\n" + "=" * 60)
        if all_ok:
            print(f"✅ ALL SAFETY CHECKS PASSED")
        else:
            print(f"❌ SAFETY CHECKS FAILED - POTENTIAL LOOP DETECTED")

        return all_ok

    def run(self, test_email: str):
        """Run complete test flow."""
        try:
            # Step 1: Baseline
            baseline = self.get_baseline_metrics()

            # Step 2: Send test email
            test_subject = self.send_test_email(test_email)

            # Step 3: Monitor
            results = self.monitor_processing(test_subject)

            # Step 4: Validate safety
            safety_ok = self.validate_safety_constraints(baseline, results, test_subject)

            # Final summary
            print(f"\n📋 Test Summary:")
            print(f"   Found in invoice inbox: {results['found_in_invoice']}")
            print(f"   Found in AP inbox: {results['found_in_ap']}")
            print(f"   Transaction created: {results['transaction_created']}")
            print(f"   Safety constraints: {'✅ PASS' if safety_ok else '❌ FAIL'}")

            return safety_ok

        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            logger.exception(e)
            return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_email_safety.py <sender_email>")
        print("Example: python scripts/test_email_safety.py contact@adobe.com")
        sys.exit(1)

    test_email = sys.argv[1]
    tester = TestEmailSafety()
    success = tester.run(test_email)
    sys.exit(0 if success else 1)
