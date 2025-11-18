#!/usr/bin/env python3
"""
Verify emails received in both invoice and AP mailboxes.

Usage:
    python scripts/verify_test_emails.py

Environment:
    GRAPH_TENANT_ID, GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET must be set
    INVOICE_MAILBOX, AP_EMAIL_ADDRESS must be set
"""

import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from shared.graph_client import GraphAPIClient
from shared.logger import get_logger
from shared.ulid_generator import generate_ulid

logger = get_logger(__name__, generate_ulid())


def verify_emails():
    """Check for test emails in both mailboxes."""
    try:
        # Initialize Graph API client
        client = GraphAPIClient()
        invoice_mailbox = os.environ.get("INVOICE_MAILBOX")
        ap_mailbox = os.environ.get("AP_EMAIL_ADDRESS")

        if not invoice_mailbox or not ap_mailbox:
            logger.error("INVOICE_MAILBOX or AP_EMAIL_ADDRESS not configured")
            return False

        print(f"\n📧 Checking mailboxes...")
        print(f"   Invoice: {invoice_mailbox}")
        print(f"   AP:      {ap_mailbox}\n")

        # Check invoice mailbox
        print(f"📬 Invoice Mailbox ({invoice_mailbox}):")
        invoice_emails = client.get_unread_emails(invoice_mailbox, max_results=5)
        if invoice_emails:
            print(f"   ✅ Found {len(invoice_emails)} unread email(s):")
            for i, email in enumerate(invoice_emails, 1):
                sender = email.get("sender", {}).get("emailAddress", {}).get("address", "Unknown")
                subject = email.get("subject", "No subject")
                msg_id = email.get("id", "No ID")
                print(f"      {i}. From: {sender}")
                print(f"         Subject: {subject}")
                print(f"         ID: {msg_id}")
        else:
            print(f"   ⚠️  No unread emails in invoice mailbox")

        # Check AP mailbox
        print(f"\n📬 AP Mailbox ({ap_mailbox}):")
        ap_emails = client.get_unread_emails(ap_mailbox, max_results=5)
        if ap_emails:
            print(f"   ✅ Found {len(ap_emails)} unread email(s):")
            for i, email in enumerate(ap_emails, 1):
                sender = email.get("sender", {}).get("emailAddress", {}).get("address", "Unknown")
                subject = email.get("subject", "No subject")
                msg_id = email.get("id", "No ID")
                print(f"      {i}. From: {sender}")
                print(f"         Subject: {subject}")
                print(f"         ID: {msg_id}")
        else:
            print(f"   ⚠️  No unread emails in AP mailbox")

        print("\n✅ Verification complete")
        return True

    except Exception as e:
        logger.error(f"Verification failed: {e}")
        print(f"\n❌ Error: {e}")
        return False


if __name__ == "__main__":
    verify_emails()
