#!/usr/bin/env python3
"""
Send test invoice emails to the invoice agent mailbox for end-to-end testing.

Usage:
    # Send all test invoices
    python scripts/send_test_emails.py --all

    # Send specific vendors
    python scripts/send_test_emails.py --vendors "Adobe" "Microsoft" "AWS"

    # Send one random invoice
    python scripts/send_test_emails.py --random

    # Send with delay between emails
    python scripts/send_test_emails.py --all --delay 5

Requirements:
    - Graph API credentials configured
    - Permissions: Mail.Send
    - Test mailbox: dev-invoices@chelseapiers.com
"""

import os
import sys
import time
import argparse
import json
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from shared.graph_client import GraphAPIClient
from tests.test_data.invoice_templates import generate_all_test_invoices, InvoiceGenerator


def send_test_invoice_email(graph_client: GraphAPIClient, invoice_data: dict, target_mailbox: str, delay: int = 0):
    """
    Send a test invoice email to the target mailbox.

    Args:
        graph_client: Authenticated Graph API client
        invoice_data: Invoice data dictionary
        target_mailbox: Email address to send to (e.g., dev-invoices@chelseapiers.com)
        delay: Seconds to wait before sending
    """
    if delay > 0:
        print(f"  ⏳ Waiting {delay} seconds...")
        time.sleep(delay)

    generator = InvoiceGenerator()
    email = generator.format_as_email_body(invoice_data)
    invoice_text = generator.format_as_text_invoice(invoice_data)

    # Create email body with invoice text
    body = email["body"] + "\n\n" + "-" * 80 + "\n\n" + invoice_text

    print(f"  📧 Sending from: {invoice_data['sender_email']}")
    print(f"  📬 Sending to: {target_mailbox}")
    print(f"  📄 Invoice: {invoice_data['invoice_number']}")
    print(f"  💰 Total: ${invoice_data['total']:.2f}")

    try:
        graph_client.send_email(
            from_address=os.environ.get("INVOICE_MAILBOX", "dev-invoices@chelseapiers.com"),
            to_address=target_mailbox,
            subject=email["subject"],
            body=body,
            is_html=False,
        )
        print(f"  ✅ Sent successfully!\n")
        return True
    except Exception as e:
        print(f"  ❌ Failed: {str(e)}\n")
        return False


def main():
    parser = argparse.ArgumentParser(description="Send test invoice emails for Invoice Agent testing")
    parser.add_argument("--all", action="store_true", help="Send all test invoices")
    parser.add_argument("--vendors", nargs="+", help="Send invoices for specific vendors (partial name match)")
    parser.add_argument("--random", action="store_true", help="Send one random invoice")
    parser.add_argument("--count", type=int, help="Number of random invoices to send")
    parser.add_argument("--delay", type=int, default=0, help="Delay in seconds between emails (default: 0)")
    parser.add_argument("--mailbox", default=None, help="Target mailbox (default: from INVOICE_MAILBOX env var)")
    parser.add_argument("--list", action="store_true", help="List all available vendors and exit")
    parser.add_argument("--dry-run", action="store_true", help="Generate invoices but don't send emails")

    args = parser.parse_args()

    # Generate all test invoices
    print("🔄 Generating test invoices...")
    all_invoices = generate_all_test_invoices()
    print(f"✅ Generated {len(all_invoices)} test invoices\n")

    # List vendors if requested
    if args.list:
        print("Available vendors:")
        for i, invoice in enumerate(all_invoices, 1):
            print(f"  {i:2}. {invoice['vendor_name']:<30} | {invoice['department']:<12} | ${invoice['total']:>10.2f}")
        return

    # Determine which invoices to send
    invoices_to_send = []

    if args.all:
        invoices_to_send = all_invoices
        print(f"📧 Sending ALL {len(all_invoices)} test invoices")
    elif args.vendors:
        # Filter by vendor name (case-insensitive partial match)
        for vendor_pattern in args.vendors:
            matching = [inv for inv in all_invoices if vendor_pattern.lower() in inv["vendor_name"].lower()]
            invoices_to_send.extend(matching)
        print(f"📧 Sending {len(invoices_to_send)} invoices for vendors: {', '.join(args.vendors)}")
    elif args.random or args.count:
        import random
        count = args.count if args.count else 1
        invoices_to_send = random.sample(all_invoices, min(count, len(all_invoices)))
        print(f"📧 Sending {len(invoices_to_send)} random invoice(s)")
    else:
        print("❌ Error: Must specify --all, --vendors, --random, or --count")
        parser.print_help()
        return

    if not invoices_to_send:
        print("⚠️  No invoices matched the criteria")
        return

    # Determine target mailbox
    target_mailbox = args.mailbox or os.environ.get("INVOICE_MAILBOX", "dev-invoices@chelseapiers.com")

    # Dry run mode
    if args.dry_run:
        print("\n🔍 DRY RUN MODE - No emails will be sent\n")
        for i, invoice in enumerate(invoices_to_send, 1):
            print(f"{i}. {invoice['vendor_name']}")
            print(f"   From: {invoice['sender_email']}")
            print(f"   Invoice: {invoice['invoice_number']}")
            print(f"   Total: ${invoice['total']:.2f}\n")
        print(f"Would send {len(invoices_to_send)} emails to {target_mailbox}")
        return

    # Initialize Graph API client
    print(f"🔐 Authenticating to Graph API...")
    try:
        graph_client = GraphAPIClient()
        print("✅ Authentication successful\n")
    except Exception as e:
        print(f"❌ Authentication failed: {str(e)}")
        print("\nEnsure these environment variables are set:")
        print("  - GRAPH_TENANT_ID")
        print("  - GRAPH_CLIENT_ID")
        print("  - GRAPH_CLIENT_SECRET")
        return

    # Send emails
    print(f"📬 Target mailbox: {target_mailbox}")
    print(f"⏱️  Delay between emails: {args.delay} seconds\n")
    print("=" * 80)

    success_count = 0
    fail_count = 0

    for i, invoice in enumerate(invoices_to_send, 1):
        print(f"\n[{i}/{len(invoices_to_send)}] {invoice['vendor_name']}")

        # Apply delay for all but first email
        delay = args.delay if i > 1 else 0

        if send_test_invoice_email(graph_client, invoice, target_mailbox, delay):
            success_count += 1
        else:
            fail_count += 1

    # Summary
    print("=" * 80)
    print(f"\n📊 Summary:")
    print(f"  ✅ Sent successfully: {success_count}")
    print(f"  ❌ Failed: {fail_count}")
    print(f"  📧 Total attempted: {len(invoices_to_send)}")
    print(f"\n✨ Done! Check {target_mailbox} for test invoices.")


if __name__ == "__main__":
    main()
