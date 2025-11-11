"""
Email parsing utilities for vendor extraction and invoice metadata.

Provides functions to extract domains from email addresses,
normalize vendor names, and parse invoice information from subjects.
"""

import re
from typing import Optional, Dict


def extract_domain(email: str) -> str:
    """
    Extract and normalize domain from an email address.

    Removes subdomains and converts to lowercase for vendor lookup.

    Args:
        email: Email address to parse

    Returns:
        str: Normalized domain (e.g., 'adobe_com')

    Raises:
        ValueError: If email format is invalid

    Example:
        >>> extract_domain('billing@adobe.com')
        'adobe_com'
        >>> extract_domain('invoices@accounts.microsoft.com')
        'microsoft_com'
    """
    if not email or '@' not in email:
        raise ValueError(f"Invalid email format: {email}")

    # Split email and get domain part
    domain_part = email.split('@')[1].lower()

    # Remove subdomain (keep only last two parts)
    # e.g., accounts.microsoft.com -> microsoft.com
    parts = domain_part.split('.')
    if len(parts) >= 2:
        domain = f"{parts[-2]}_{parts[-1].replace('.', '_')}"
    else:
        domain = domain_part.replace('.', '_')

    return domain


def normalize_vendor_name(vendor: str) -> str:
    """
    Normalize vendor name for consistent lookup.

    Converts to lowercase and removes special characters.

    Args:
        vendor: Raw vendor name

    Returns:
        str: Normalized vendor name for table lookup

    Example:
        >>> normalize_vendor_name('Adobe Inc.')
        'adobe_inc'
    """
    # Convert to lowercase
    normalized = vendor.lower()

    # Remove special characters first, keep alphanumeric and spaces
    normalized = re.sub(r'[^a-z0-9\s]', '', normalized)

    # Remove common suffixes (after special char removal)
    suffixes = [' inc', ' llc', ' ltd', ' corp', ' co']
    for suffix in suffixes:
        if normalized.endswith(suffix):
            normalized = normalized[:-len(suffix)]

    # Replace spaces with underscores and strip
    normalized = normalized.strip().replace(' ', '_')

    return normalized


def parse_invoice_subject(subject: str) -> Dict[str, Optional[str]]:
    """
    Parse invoice metadata from email subject line.

    Attempts to extract invoice number and amount if present.

    Args:
        subject: Email subject line

    Returns:
        dict: Parsed metadata with keys:
            - invoice_number: Invoice ID if found
            - amount: Invoice amount if found
            - vendor_hint: Potential vendor name if found

    Example:
        >>> parse_invoice_subject('Invoice #12345 - $1,250.00')
        {'invoice_number': '12345', 'amount': '1250.00', 'vendor_hint': None}
    """
    result: Dict[str, Optional[str]] = {
        'invoice_number': None,
        'amount': None,
        'vendor_hint': None
    }

    # Extract invoice number
    # Patterns: Invoice #12345, INV-12345, Invoice 12345
    inv_patterns = [
        r'invoice\s*#?(\d+)',
        r'inv[oice]*[\s-]*(\d+)',
        r'bill\s*#?(\d+)'
    ]
    for pattern in inv_patterns:
        match = re.search(pattern, subject, re.IGNORECASE)
        if match:
            result['invoice_number'] = match.group(1)
            break

    # Extract amount
    # Patterns: $1,250.00, USD 1250.00, 1250.00
    amount_pattern = r'[\$]?\s*([\d,]+\.?\d*)'
    match = re.search(amount_pattern, subject)
    if match:
        # Remove commas from amount
        result['amount'] = match.group(1).replace(',', '')

    return result
