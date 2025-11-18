#!/usr/bin/env python3
"""
Real-time monitoring of email flow during testing.

Checks mailboxes and transactions every 10 seconds for 5 minutes.
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from shared.graph_client import GraphAPIClient
from shared.logger import get_logger
from shared.ulid_generator import generate_ulid
from azure.data.tables import TableClient
from azure.identity import DefaultAzureCredential

logger = get_logger(__name__, generate_ulid())


class LiveMonitor:
    """Real-time monitoring of email flow."""

    def __init__(self):
        self.client = GraphAPIClient()
        self.invoice_mailbox = os.environ.get("INVOICE_MAILBOX")
        self.ap_mailbox = os.environ.get("AP_EMAIL_ADDRESS")
        self.storage_account = os.environ.get("STORAGE_ACCOUNT", "stinvoiceagentprod")
        self.start_time = datetime.utcnow()
        self.baseline_invoice = 0
        self.baseline_ap = 0

    def get_mailbox_status(self) -> dict:
        """Get current unread counts."""
        try:
            invoice_unread = len(
                self.client.get_unread_emails(self.invoice_mailbox, max_results=100)
            )
            ap_unread = len(self.client.get_unread_emails(self.ap_mailbox, max_results=100))

            return {"invoice": invoice_unread, "ap": ap_unread}
        except Exception as e:
            logger.error(f"Error getting mailbox status: {e}")
            return {"invoice": None, "ap": None}

    def get_transaction_count(self) -> int:
        """Get recent transaction count."""
        try:
            table_url = f"https://{self.storage_account}.table.core.windows.net"
            credential = DefaultAzureCredential()
            client = TableClient(table_url, "InvoiceTransactions", credential=credential)

            cutoff = datetime.utcnow() - timedelta(minutes=10)
            cutoff_iso = cutoff.isoformat() + "Z"
            query = f"CreatedAt gt datetime'{cutoff_iso}'"

            entities = client.query_entities(filter=query)
            transactions = list(entities)

            # Filter for Test Invoice
            test_txns = [t for t in transactions if "Test Invoice" in t.get("Subject", "")]
            return len(test_txns)
        except Exception as e:
            logger.warning(f"Error getting transactions: {e}")
            return None

    def monitor(self, duration_seconds: int = 300):
        """Monitor for duration."""
        print()
        print("🚀 REAL-TIME MONITORING - Email Flow Test")
        print("=" * 70)
        print(f"Start Time: {self.start_time.strftime('%H:%M:%S')}")
        print(f"Invoice Mailbox: {self.invoice_mailbox}")
        print(f"AP Mailbox: {self.ap_mailbox}")
        print(f"Duration: {duration_seconds} seconds (~{duration_seconds // 60} min)")
        print("=" * 70)

        # Get baseline
        print("\n📊 Capturing baseline...")
        baseline = self.get_mailbox_status()
        self.baseline_invoice = baseline["invoice"]
        self.baseline_ap = baseline["ap"]

        print(f"   Invoice inbox: {self.baseline_invoice} unread")
        print(f"   AP inbox: {self.baseline_ap} unread")

        # Monitor
        elapsed = 0
        check_interval = 10
        previous_invoice = self.baseline_invoice
        previous_ap = self.baseline_ap
        previous_txn = 0

        print(f"\n⏱️  Monitoring for {duration_seconds} seconds...")
        print("   (Checking every 10 seconds)")
        print()

        # Timeline
        timeline = {
            "0-10": "✉️  Waiting for MailIngest to pick up email...",
            "10-20": "🔍 MailIngest processing (should mark email as read)",
            "20-30": "📤 ExtractEnrich enriching vendor data",
            "30-40": "✉️  PostToAP sending to AP mailbox",
            "40-50": "📧 Email should arrive in AP inbox now",
            "50-60": "💬 Notify posting to Teams",
            "60+": "✅ All done - analyzing results",
        }

        while elapsed < duration_seconds:
            # Get current status
            status = self.get_mailbox_status()
            txn_count = self.get_transaction_count()

            elapsed = int((datetime.utcnow() - self.start_time).total_seconds())
            elapsed_min = elapsed // 60
            elapsed_sec = elapsed % 60

            # Get timeline expectation
            expectation = ""
            for range_key, desc in timeline.items():
                if "-" in range_key:
                    min_sec, max_sec = range_key.split("-")
                    if int(min_sec) <= elapsed <= int(max_sec):
                        expectation = desc
                        break
                elif range_key == "60+":
                    if elapsed >= 60:
                        expectation = desc
                        break

            # Print status
            print(
                f"[{elapsed_min}m{elapsed_sec:02d}s] Invoice: {status['invoice']:2d}  "
                f"AP: {status['ap']:2d}  Txn: {str(txn_count):>2}  │ {expectation}"
            )

            # Check for changes
            if status["invoice"] != previous_invoice:
                if status["invoice"] < previous_invoice:
                    print(
                        f"        ✅ Invoice inbox changed (marked read by MailIngest)"
                    )
                else:
                    print(f"        ⚠️  Invoice inbox increased (email re-appeared?)")

            if status["ap"] != previous_ap:
                if status["ap"] > previous_ap:
                    print(f"        ✅ AP inbox email received (PostToAP successful)")
                else:
                    print(f"        ⚠️  AP inbox decreased (email deleted?)")

            if txn_count and txn_count != previous_txn:
                if txn_count > previous_txn:
                    print(
                        f"        ✅ Transaction created (ExtractEnrich processed)"
                    )
                else:
                    print(f"        ⚠️  Transaction count decreased")

            # Check for loop
            if status["ap"] > 1:
                print()
                print("        ⚠️  WARNING: Multiple emails in AP inbox!")
                print("        🚨 POTENTIAL LOOP DETECTED!")
                print()
                print("        IMMEDIATE ACTION: Stop Function App")
                print("        az functionapp stop --name func-invoice-agent-prod \\")
                print("          --resource-group rg-invoice-agent-prod")
                print()

            previous_invoice = status["invoice"]
            previous_ap = status["ap"]
            previous_txn = txn_count

            # Wait before next check
            if elapsed < duration_seconds:
                time.sleep(check_interval)

        # Final status
        print()
        print("=" * 70)
        print("📊 FINAL STATUS")
        print("=" * 70)

        final = self.get_mailbox_status()
        final_txn = self.get_transaction_count()

        print(f"Invoice inbox final: {final['invoice']} unread (was {self.baseline_invoice})")
        print(f"AP inbox final: {final['ap']} unread (was {self.baseline_ap})")
        print(f"Transactions: {final_txn}")

        print()
        print("📋 SAFETY ASSESSMENT:")
        print("─" * 70)

        checks = []

        # Check 1: Invoice processed
        if final["invoice"] < self.baseline_invoice:
            print("✅ Invoice email was processed (marked read)")
            checks.append(True)
        elif final["invoice"] == self.baseline_invoice:
            print("⚠️  Invoice email still unread (may still be processing)")
            checks.append(None)
        else:
            print("❌ Invoice email count increased (unexpected)")
            checks.append(False)

        # Check 2: AP received exactly 1
        if final["ap"] == self.baseline_ap + 1:
            print("✅ Exactly ONE email sent to AP mailbox (no loop)")
            checks.append(True)
        elif final["ap"] == self.baseline_ap:
            print("⚠️  No email in AP yet (may still be processing)")
            checks.append(None)
        else:
            print(f"❌ LOOP DETECTED: {final['ap']} emails in AP (expected 1)")
            checks.append(False)

        # Check 3: Transaction created
        if final_txn == 1:
            print("✅ Exactly ONE transaction created (no duplicate processing)")
            checks.append(True)
        elif final_txn == 0:
            print("⚠️  No transactions yet (may still be processing)")
            checks.append(None)
        else:
            print(f"❌ Duplicate processing: {final_txn} transactions (expected 1)")
            checks.append(False)

        print()
        print("=" * 70)

        if all(checks):
            print("✅ ALL CHECKS PASSED - System is safe!")
            return True
        elif None in checks and not any(c is False for c in checks):
            print("⏳ Still processing - wait another minute and run: python scripts/analyze_test_results.py")
            return None
        else:
            print("❌ ISSUES DETECTED - Review above")
            return False


if __name__ == "__main__":
    monitor = LiveMonitor()
    result = monitor.monitor(duration_seconds=300)  # 5 minutes

    print()
    print("Next step: python scripts/analyze_test_results.py")
    print()

    sys.exit(0 if result else 1)
