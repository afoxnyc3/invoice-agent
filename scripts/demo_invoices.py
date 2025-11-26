#!/usr/bin/env python3
"""Demo script to show generated invoice content without dependencies."""

import sys
from pathlib import Path

# Add tests/test_data to path
sys.path.insert(0, str(Path(__file__).parent.parent / "tests" / "test_data"))

from invoice_templates import generate_all_test_invoices, InvoiceGenerator

# Generate all invoices
invoices = generate_all_test_invoices()
generator = InvoiceGenerator()

print(f"Generated {len(invoices)} test invoices for Invoice Agent testing\n")
print("=" * 80)
print("AVAILABLE TEST VENDORS:")
print("=" * 80)

for i, invoice in enumerate(invoices, 1):
    print(f"{i:2}. {invoice['vendor_name']:<30} | {invoice['department']:<12} | ${invoice['total']:>10,.2f}")

print("\n" + "=" * 80)
print("\nShowing 3 sample invoices:")
print("=" * 80)

# Show 3 sample invoices
for i, invoice in enumerate(invoices[:3], 1):
    print(f"\n{'='*80}")
    print(f"SAMPLE INVOICE #{i}")
    print('='*80)
    print(generator.format_as_text_invoice(invoice))

    email = generator.format_as_email_body(invoice)
    print(f"\nEMAIL SUBJECT:")
    print(f"  {email['subject']}")
    print(f"\nEMAIL SENDER:")
    print(f"  {invoice['sender_email']}")
    print(f"\nEMAIL BODY (PREVIEW):")
    print("  " + "\n  ".join(email['body'].split('\n')[:15]))
    print("  ...")
    print()
