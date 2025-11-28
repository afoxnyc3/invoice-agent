"""
Email parsing utilities for vendor extraction.

Provides function to extract domains from email addresses for vendor lookup.
"""


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
    if not email or "@" not in email:
        raise ValueError(f"Invalid email format: {email}")

    # Split email and get domain part
    domain_part = email.split("@")[1].lower()

    # Remove subdomain (keep only last two parts)
    # e.g., accounts.microsoft.com -> microsoft.com
    parts = domain_part.split(".")
    if len(parts) >= 2:
        domain = f"{parts[-2]}_{parts[-1].replace('.', '_')}"
    else:
        domain = domain_part.replace(".", "_")

    return domain
