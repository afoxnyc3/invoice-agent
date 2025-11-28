"""
Unit tests for shared/email_parser.py module.

Tests cover:
- extract_domain() with various email formats
- Subdomain handling
- Case normalization
- Error handling for invalid inputs
- Edge cases and special characters
"""

import pytest
from shared.email_parser import extract_domain


# =============================================================================
# BASIC FUNCTIONALITY TESTS
# =============================================================================


class TestExtractDomainBasic:
    """Basic tests for extract_domain function."""

    def test_simple_email(self):
        """Test extracting domain from simple email."""
        assert extract_domain("billing@adobe.com") == "adobe_com"

    def test_standard_corporate_email(self):
        """Test standard corporate email format."""
        assert extract_domain("john.doe@microsoft.com") == "microsoft_com"

    def test_returns_string(self):
        """Test function returns string type."""
        result = extract_domain("test@example.com")
        assert isinstance(result, str)

    def test_replaces_dot_with_underscore(self):
        """Test domain separator is underscore not dot."""
        result = extract_domain("test@example.com")
        assert "." not in result
        assert "_" in result


# =============================================================================
# SUBDOMAIN HANDLING TESTS
# =============================================================================


class TestExtractDomainSubdomains:
    """Tests for subdomain handling."""

    def test_single_subdomain_removed(self):
        """Test single subdomain is removed."""
        assert extract_domain("invoices@accounts.microsoft.com") == "microsoft_com"

    def test_multiple_subdomains_removed(self):
        """Test multiple subdomains are removed."""
        assert extract_domain("billing@mail.invoices.adobe.com") == "adobe_com"

    def test_deep_subdomain_structure(self):
        """Test deeply nested subdomains are handled."""
        result = extract_domain("user@a.b.c.d.example.com")
        assert result == "example_com"

    def test_no_subdomain(self):
        """Test email with no subdomain works."""
        assert extract_domain("user@company.org") == "company_org"


# =============================================================================
# CASE NORMALIZATION TESTS
# =============================================================================


class TestExtractDomainCaseNormalization:
    """Tests for case normalization."""

    def test_uppercase_email_normalized(self):
        """Test uppercase email is normalized to lowercase."""
        assert extract_domain("USER@ADOBE.COM") == "adobe_com"

    def test_mixed_case_email_normalized(self):
        """Test mixed case email is normalized."""
        assert extract_domain("User@Adobe.Com") == "adobe_com"

    def test_lowercase_preserved(self):
        """Test already lowercase email stays lowercase."""
        assert extract_domain("user@adobe.com") == "adobe_com"

    def test_uppercase_local_part_ignored(self):
        """Test uppercase in local part doesn't affect domain."""
        result1 = extract_domain("USER@example.com")
        result2 = extract_domain("user@example.com")
        assert result1 == result2


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestExtractDomainErrorHandling:
    """Tests for error handling."""

    def test_empty_string_raises_error(self):
        """Test empty string raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            extract_domain("")
        assert "Invalid email format" in str(exc_info.value)

    def test_no_at_sign_raises_error(self):
        """Test string without @ raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            extract_domain("not-an-email")
        assert "Invalid email format" in str(exc_info.value)

    def test_none_raises_error(self):
        """Test None input raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            extract_domain(None)
        assert "Invalid email format" in str(exc_info.value)

    def test_whitespace_only_raises_error(self):
        """Test whitespace-only string raises ValueError."""
        with pytest.raises(ValueError):
            extract_domain("   ")

    def test_error_includes_input_value(self):
        """Test error message includes the invalid input."""
        with pytest.raises(ValueError) as exc_info:
            extract_domain("bad-input")
        assert "bad-input" in str(exc_info.value)


# =============================================================================
# SPECIAL CHARACTER TESTS
# =============================================================================


class TestExtractDomainSpecialCharacters:
    """Tests for special characters in email addresses."""

    def test_plus_sign_in_local_part(self):
        """Test email with plus sign in local part."""
        assert extract_domain("user+tag@example.com") == "example_com"

    def test_dots_in_local_part(self):
        """Test email with dots in local part."""
        assert extract_domain("first.last@example.com") == "example_com"

    def test_numbers_in_local_part(self):
        """Test email with numbers in local part."""
        assert extract_domain("user123@example.com") == "example_com"

    def test_underscores_in_local_part(self):
        """Test email with underscores in local part."""
        assert extract_domain("first_last@example.com") == "example_com"

    def test_hyphen_in_domain(self):
        """Test email with hyphen in domain."""
        result = extract_domain("user@my-company.com")
        assert result == "my-company_com"


# =============================================================================
# TLD VARIATIONS TESTS
# =============================================================================


class TestExtractDomainTLDs:
    """Tests for various TLD formats."""

    def test_com_tld(self):
        """Test .com TLD."""
        assert extract_domain("user@company.com") == "company_com"

    def test_org_tld(self):
        """Test .org TLD."""
        assert extract_domain("user@nonprofit.org") == "nonprofit_org"

    def test_net_tld(self):
        """Test .net TLD."""
        assert extract_domain("user@network.net") == "network_net"

    def test_io_tld(self):
        """Test .io TLD."""
        assert extract_domain("user@startup.io") == "startup_io"

    def test_country_code_tld_couk(self):
        """Test .co.uk country code TLD - extracts last two parts."""
        # Note: co.uk will be extracted as just "co_uk" due to subdomain removal
        result = extract_domain("user@company.co.uk")
        assert result == "co_uk"

    def test_country_code_tld_comau(self):
        """Test .com.au country code TLD."""
        result = extract_domain("user@company.com.au")
        assert result == "com_au"


# =============================================================================
# EDGE CASES TESTS
# =============================================================================


class TestExtractDomainEdgeCases:
    """Tests for edge cases."""

    def test_single_part_domain(self):
        """Test domain with only one part (no TLD)."""
        # This is technically invalid but the function handles it
        result = extract_domain("user@localhost")
        assert result == "localhost"

    def test_at_sign_only(self):
        """Test email that is just @ symbol returns empty domain."""
        # This is technically valid per the function logic (has @)
        # but the domain part after @ is empty
        result = extract_domain("@")
        assert result == ""  # Empty domain part after @

    def test_multiple_at_signs(self):
        """Test email with multiple @ signs - uses first split."""
        # Only the part after the first @ is considered
        result = extract_domain("user@domain@extra.com")
        assert result is not None  # Doesn't crash

    def test_very_long_subdomain_chain(self):
        """Test email with very long subdomain chain."""
        email = "user@a.b.c.d.e.f.g.h.i.j.k.example.com"
        result = extract_domain(email)
        assert result == "example_com"

    def test_numeric_domain(self):
        """Test domain with numbers."""
        assert extract_domain("user@123.456.com") == "456_com"

    def test_short_tld(self):
        """Test short TLD like .ai."""
        assert extract_domain("user@company.ai") == "company_ai"


# =============================================================================
# REAL-WORLD VENDOR TESTS
# =============================================================================


class TestExtractDomainRealVendors:
    """Tests using real-world vendor email patterns."""

    def test_adobe_billing(self):
        """Test Adobe billing email."""
        assert extract_domain("billing@adobe.com") == "adobe_com"

    def test_microsoft_accounts(self):
        """Test Microsoft accounts subdomain."""
        assert extract_domain("invoices@accounts.microsoft.com") == "microsoft_com"

    def test_amazon_aws(self):
        """Test Amazon AWS email."""
        assert extract_domain("billing@aws.amazon.com") == "amazon_com"

    def test_google_cloud(self):
        """Test Google Cloud billing."""
        assert extract_domain("billing@cloud.google.com") == "google_com"

    def test_salesforce(self):
        """Test Salesforce invoicing."""
        assert extract_domain("invoices@salesforce.com") == "salesforce_com"

    def test_zoom(self):
        """Test Zoom billing email."""
        assert extract_domain("billing@zoom.us") == "zoom_us"

    def test_slack(self):
        """Test Slack email."""
        assert extract_domain("billing@slack.com") == "slack_com"

    def test_atlassian(self):
        """Test Atlassian billing."""
        assert extract_domain("invoices@atlassian.com") == "atlassian_com"
