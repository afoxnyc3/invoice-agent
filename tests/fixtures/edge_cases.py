"""
Edge case test fixtures for Invoice Agent.

This module provides comprehensive test data for edge cases including:
- Unicode and international characters
- Boundary values (very long/short strings)
- Special characters in various fields
- Invalid data for validation testing
"""

from typing import Any

# =============================================================================
# VENDOR EDGE CASES
# =============================================================================

VENDOR_EDGE_CASES: list[dict[str, Any]] = [
    # Unicode vendor names
    {
        "id": "unicode_japanese",
        "RowKey": "nihon_kaisha",
        "VendorName": "日本株式会社",  # Japanese company
        "ExpenseDept": "IT",
        "GLCode": "6100",
        "should_pass": True,
    },
    {
        "id": "unicode_german",
        "RowKey": "muenchen_gmbh",
        "VendorName": "München GmbH",  # German umlaut
        "ExpenseDept": "IT",
        "GLCode": "6100",
        "should_pass": True,
    },
    {
        "id": "unicode_french",
        "RowKey": "cafe_francais",
        "VendorName": "Café Français",  # French accents
        "ExpenseDept": "FOOD",
        "GLCode": "7200",
        "should_pass": True,
    },
    {
        "id": "unicode_chinese",
        "RowKey": "beijing_tech",
        "VendorName": "北京科技有限公司",  # Chinese company
        "ExpenseDept": "IT",
        "GLCode": "6100",
        "should_pass": True,
    },
    {
        "id": "unicode_emoji",
        "RowKey": "emoji_corp",
        "VendorName": "Tech Corp 🚀",  # Emoji in name
        "ExpenseDept": "IT",
        "GLCode": "6100",
        "should_pass": True,
    },
    # Very long vendor names
    {
        "id": "very_long_name",
        "RowKey": "very_long_company",
        "VendorName": "A" * 200,  # 200 character name
        "ExpenseDept": "IT",
        "GLCode": "6100",
        "should_pass": True,
    },
    # Single character names
    {
        "id": "single_char",
        "RowKey": "x",
        "VendorName": "X",
        "ExpenseDept": "IT",
        "GLCode": "6100",
        "should_pass": True,
    },
    # Numeric-only names
    {
        "id": "numeric_only",
        "RowKey": "123456",
        "VendorName": "123456",
        "ExpenseDept": "IT",
        "GLCode": "6100",
        "should_pass": True,
    },
    # Special characters
    {
        "id": "special_ampersand",
        "RowKey": "johnson_and_johnson",
        "VendorName": "Johnson & Johnson",
        "ExpenseDept": "HEALTH",
        "GLCode": "7300",
        "should_pass": True,
    },
    {
        "id": "special_apostrophe",
        "RowKey": "mcdonalds",
        "VendorName": "McDonald's",
        "ExpenseDept": "FOOD",
        "GLCode": "7200",
        "should_pass": True,
    },
    {
        "id": "special_parentheses",
        "RowKey": "acme_inc",
        "VendorName": "Acme (Inc.)",
        "ExpenseDept": "IT",
        "GLCode": "6100",
        "should_pass": True,
    },
    {
        "id": "special_quotes",
        "RowKey": "best_buy",
        "VendorName": '"Best" Buy',
        "ExpenseDept": "IT",
        "GLCode": "6100",
        "should_pass": True,
    },
    # Whitespace edge cases - Note: Pydantic doesn't auto-trim, so include exact value
    {
        "id": "leading_trailing_spaces",
        "RowKey": "trimmed_vendor",
        "VendorName": "  Trimmed Vendor  ",  # Whitespace preserved by Pydantic
        "ExpenseDept": "IT",
        "GLCode": "6100",
        "should_pass": True,
        "preserve_whitespace": True,  # Flag to not strip in test assertion
    },
]

# Invalid vendor cases (should fail validation)
INVALID_VENDOR_CASES: list[dict[str, Any]] = [
    {
        "id": "empty_name",
        "RowKey": "empty",
        "VendorName": "",
        "ExpenseDept": "IT",
        "GLCode": "6100",
        "expected_error": "Field cannot be empty",
    },
    {
        "id": "whitespace_only_name",
        "RowKey": "whitespace",
        "VendorName": "   ",
        "ExpenseDept": "IT",
        "GLCode": "6100",
        "expected_error": "Field cannot be empty",
    },
    {
        "id": "invalid_gl_code_letters",
        "RowKey": "invalid_gl",
        "VendorName": "Valid Vendor",
        "ExpenseDept": "IT",
        "GLCode": "61AB",  # Letters not allowed
        "expected_error": "gl_code must be exactly 4 digits",
    },
    {
        "id": "invalid_gl_code_short",
        "RowKey": "short_gl",
        "VendorName": "Valid Vendor",
        "ExpenseDept": "IT",
        "GLCode": "610",  # Too short
        "expected_error": "gl_code must be exactly 4 digits",
    },
    {
        "id": "invalid_gl_code_long",
        "RowKey": "long_gl",
        "VendorName": "Valid Vendor",
        "ExpenseDept": "IT",
        "GLCode": "61000",  # Too long
        "expected_error": "gl_code must be exactly 4 digits",
    },
]


# =============================================================================
# EMAIL EDGE CASES
# =============================================================================

EMAIL_EDGE_CASES: list[dict[str, Any]] = [
    # Standard formats
    {
        "id": "standard_email",
        "email": "billing@adobe.com",
        "should_pass": True,
    },
    # Plus addressing
    {
        "id": "plus_addressing",
        "email": "billing+invoices@company.com",
        "should_pass": True,
    },
    # Multiple dots in local part
    {
        "id": "multiple_dots_local",
        "email": "first.middle.last@company.com",
        "should_pass": True,
    },
    # Multiple subdomains
    {
        "id": "multiple_subdomains",
        "email": "billing@invoices.accounts.company.com",
        "should_pass": True,
    },
    # Hyphen in domain
    {
        "id": "hyphen_domain",
        "email": "billing@my-company.com",
        "should_pass": True,
    },
    # Numbers in local part
    {
        "id": "numbers_local",
        "email": "billing123@company.com",
        "should_pass": True,
    },
    # Very long email
    {
        "id": "very_long_email",
        "email": f"{'a' * 64}@{'b' * 63}.com",  # Max local part
        "should_pass": True,
    },
    # New TLDs
    {
        "id": "new_tld",
        "email": "billing@company.technology",
        "should_pass": True,
    },
    # Country code TLD
    {
        "id": "country_tld",
        "email": "billing@company.co.uk",
        "should_pass": True,
    },
]

# Invalid email cases
INVALID_EMAIL_CASES: list[dict[str, Any]] = [
    {
        "id": "missing_at",
        "email": "billingcompany.com",
        "expected_error": "not a valid email",
    },
    {
        "id": "double_at",
        "email": "billing@@company.com",
        "expected_error": "not a valid email",
    },
    {
        "id": "missing_domain",
        "email": "billing@",
        "expected_error": "not a valid email",
    },
    {
        "id": "missing_tld",
        "email": "billing@company",
        "expected_error": "not a valid email",
    },
    {
        "id": "space_in_email",
        "email": "billing @company.com",
        "expected_error": "not a valid email",
    },
]


# =============================================================================
# RAW MAIL MESSAGE EDGE CASES
# =============================================================================

RAW_MAIL_EDGE_CASES: list[dict[str, Any]] = [
    # Unicode subject
    {
        "id": "unicode_subject",
        "sender": "billing@company.com",
        "subject": "請求書 #12345 - Invoice",  # Japanese + English
        "should_pass": True,
    },
    # Very long subject
    {
        "id": "very_long_subject",
        "sender": "billing@company.com",
        "subject": "A" * 500,  # 500 char subject
        "should_pass": True,
    },
    # Special characters in subject
    {
        "id": "special_chars_subject",
        "sender": "billing@company.com",
        "subject": "Invoice <#12345> & Payment $1,000.00 @2024",
        "should_pass": True,
    },
    # Emoji in subject
    {
        "id": "emoji_subject",
        "sender": "billing@company.com",
        "subject": "Invoice 📄 #12345 ✅",
        "should_pass": True,
    },
    # Newlines in subject (should be preserved or handled)
    {
        "id": "newline_subject",
        "sender": "billing@company.com",
        "subject": "Invoice\n#12345",
        "should_pass": True,
    },
]


# =============================================================================
# ENRICHED INVOICE EDGE CASES
# =============================================================================

ENRICHED_INVOICE_EDGE_CASES: list[dict[str, Any]] = [
    # Minimum valid invoice amount
    {
        "id": "min_amount",
        "invoice_amount": 0.01,
        "should_pass": True,
    },
    # Large valid invoice amount
    {
        "id": "large_amount",
        "invoice_amount": 9_999_999.99,
        "should_pass": True,
    },
    # Different currencies
    {
        "id": "eur_currency",
        "invoice_amount": 1000.00,
        "currency": "EUR",
        "should_pass": True,
    },
    {
        "id": "cad_currency",
        "invoice_amount": 1000.00,
        "currency": "CAD",
        "should_pass": True,
    },
]

# Invalid enriched invoice cases
INVALID_ENRICHED_CASES: list[dict[str, Any]] = [
    {
        "id": "zero_amount",
        "invoice_amount": 0,
        "expected_error": "must be greater than 0",
    },
    {
        "id": "negative_amount",
        "invoice_amount": -100.00,
        "expected_error": "must be greater than 0",
    },
    {
        "id": "too_large_amount",
        "invoice_amount": 10_000_001.00,
        "expected_error": "must be less than $10M",
    },
    {
        "id": "invalid_currency",
        "invoice_amount": 1000.00,
        "currency": "GBP",  # Not supported
        "expected_error": "must be one of",
    },
]


# =============================================================================
# TRANSACTION PARTITION KEY EDGE CASES
# =============================================================================

PARTITION_KEY_EDGE_CASES: list[dict[str, Any]] = [
    # Valid partition keys
    {"id": "jan_2024", "partition_key": "202401", "should_pass": True},
    {"id": "dec_2024", "partition_key": "202412", "should_pass": True},
    {"id": "jan_2025", "partition_key": "202501", "should_pass": True},
    {"id": "far_future", "partition_key": "209912", "should_pass": True},
]

INVALID_PARTITION_KEY_CASES: list[dict[str, Any]] = [
    {
        "id": "invalid_month_00",
        "partition_key": "202400",
        "expected_error": "Invalid year or month",
    },
    {
        "id": "invalid_month_13",
        "partition_key": "202413",
        "expected_error": "Invalid year or month",
    },
    {
        "id": "too_short",
        "partition_key": "20241",
        "expected_error": "YYYYMM format",
    },
    {
        "id": "too_long",
        "partition_key": "2024011",
        "expected_error": "YYYYMM format",
    },
    {
        "id": "not_numeric",
        "partition_key": "2024AB",
        "expected_error": "YYYYMM format",
    },
    {
        "id": "year_too_old",
        "partition_key": "201901",
        "expected_error": "Invalid year or month",
    },
]


# =============================================================================
# BLOB URL EDGE CASES
# =============================================================================

BLOB_URL_EDGE_CASES: list[dict[str, Any]] = [
    # Valid URLs
    {
        "id": "standard_url",
        "url": "https://storage.blob.core.windows.net/invoices/raw/invoice.pdf",
        "should_pass": True,
    },
    {
        "id": "url_with_spaces_encoded",
        "url": "https://storage.blob.core.windows.net/invoices/raw/invoice%20file.pdf",
        "should_pass": True,
    },
    {
        "id": "url_with_unicode_encoded",
        "url": "https://storage.blob.core.windows.net/invoices/raw/%E8%AB%8B%E6%B1%82%E6%9B%B8.pdf",
        "should_pass": True,
    },
    {
        "id": "very_long_url",
        "url": f"https://storage.blob.core.windows.net/invoices/raw/{'a' * 200}.pdf",
        "should_pass": True,
    },
]

INVALID_BLOB_URL_CASES: list[dict[str, Any]] = [
    {
        "id": "http_not_https",
        "url": "http://storage.blob.core.windows.net/invoices/raw/invoice.pdf",
        "expected_error": "must be HTTPS",
    },
    {
        "id": "no_protocol",
        "url": "storage.blob.core.windows.net/invoices/raw/invoice.pdf",
        "expected_error": "must be HTTPS",
    },
]
