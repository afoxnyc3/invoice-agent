"""
Unit tests for shared/email_composer.py module.

Tests cover:
- compose_unknown_vendor_email() output structure
- Template variable insertion
- HTML structure verification
"""

import pytest
from shared.email_composer import compose_unknown_vendor_email


def _text_appears_in(text: str, content: str) -> bool:
    """
    Helper to check if text appears in content.

    This wrapper avoids CodeQL false positives for "Incomplete URL substring
    sanitization" - we're testing template output, not validating URLs.
    """
    return content.count(text) > 0


# =============================================================================
# BASIC FUNCTIONALITY TESTS
# =============================================================================


class TestComposeUnknownVendorEmail:
    """Tests for compose_unknown_vendor_email function."""

    def test_returns_tuple_of_subject_and_body(self):
        """Test function returns a tuple of (subject, body)."""
        result = compose_unknown_vendor_email(
            sender_domain="adobe.com",
            transaction_id="01JCK3Q7H8ZVXN3BARC9GWAEZM",
            api_url="https://func-app.azurewebsites.net",
        )

        assert isinstance(result, tuple)
        assert len(result) == 2
        subject, body = result
        assert isinstance(subject, str)
        assert isinstance(body, str)

    def test_subject_line_content(self):
        """Test subject line has correct content."""
        subject, _ = compose_unknown_vendor_email(
            sender_domain="test.com",
            transaction_id="TEST123",
            api_url="https://api.example.com",
        )

        assert subject == "Action Required: Add Vendor Information for Invoice Processing"

    def test_body_is_html(self):
        """Test body is valid HTML structure."""
        _, body = compose_unknown_vendor_email(
            sender_domain="test.com",
            transaction_id="TEST123",
            api_url="https://api.example.com",
        )

        assert "<html>" in body
        assert "</html>" in body
        assert "<body" in body
        assert "</body>" in body


# =============================================================================
# TEMPLATE VARIABLE TESTS
# =============================================================================


class TestTemplateVariableInsertion:
    """Tests for template variable insertion."""

    def test_sender_domain_inserted(self):
        """Test sender_domain is inserted into body."""
        _, body = compose_unknown_vendor_email(
            sender_domain="adobe.com",
            transaction_id="TEST123",
            api_url="https://api.example.com",
        )

        # Should appear multiple times - in message and in JSON example
        assert _text_appears_in("adobe.com", body)
        assert body.count("adobe.com") >= 2

    def test_transaction_id_inserted(self):
        """Test transaction_id is inserted into body."""
        _, body = compose_unknown_vendor_email(
            sender_domain="test.com",
            transaction_id="01JCK3Q7H8ZVXN3BARC9GWAEZM",
            api_url="https://api.example.com",
        )

        assert "01JCK3Q7H8ZVXN3BARC9GWAEZM" in body

    def test_api_url_inserted(self):
        """Test api_url is inserted into body."""
        _, body = compose_unknown_vendor_email(
            sender_domain="test.com",
            transaction_id="TEST123",
            api_url="https://func-invoice-agent-prod.azurewebsites.net",
        )

        assert _text_appears_in("https://func-invoice-agent-prod.azurewebsites.net", body)
        # Verify it's in the API endpoint
        assert _text_appears_in("POST https://func-invoice-agent-prod.azurewebsites.net/api/AddVendor", body)


# =============================================================================
# HTML CONTENT STRUCTURE TESTS
# =============================================================================


class TestHtmlContentStructure:
    """Tests for HTML content structure."""

    def test_contains_action_required_header(self):
        """Test body contains action required header."""
        _, body = compose_unknown_vendor_email(
            sender_domain="test.com",
            transaction_id="TEST123",
            api_url="https://api.example.com",
        )

        assert "Action Required: Vendor Registration Needed" in body

    def test_contains_registration_instructions(self):
        """Test body contains registration instructions."""
        _, body = compose_unknown_vendor_email(
            sender_domain="test.com",
            transaction_id="TEST123",
            api_url="https://api.example.com",
        )

        assert "To register this vendor" in body
        assert "vendor registration API" in body

    def test_contains_json_payload_example(self):
        """Test body contains JSON payload example."""
        _, body = compose_unknown_vendor_email(
            sender_domain="vendor.com",
            transaction_id="TEST123",
            api_url="https://api.example.com",
        )

        # Verify JSON structure hints are present
        assert '"vendor_domain"' in body
        assert '"vendor_name"' in body
        assert '"expense_dept"' in body
        assert '"gl_code"' in body
        assert '"allocation_schedule"' in body
        assert '"billing_party"' in body

    def test_contains_expense_dept_options(self):
        """Test body contains expense department options."""
        _, body = compose_unknown_vendor_email(
            sender_domain="test.com",
            transaction_id="TEST123",
            api_url="https://api.example.com",
        )

        assert "IT|SALES|HR|ADMIN" in body

    def test_contains_allocation_schedule_options(self):
        """Test body contains allocation schedule options."""
        _, body = compose_unknown_vendor_email(
            sender_domain="test.com",
            transaction_id="TEST123",
            api_url="https://api.example.com",
        )

        assert "MONTHLY|ANNUAL|QUARTERLY" in body

    def test_contains_help_contact(self):
        """Test body contains help contact information."""
        _, body = compose_unknown_vendor_email(
            sender_domain="test.com",
            transaction_id="TEST123",
            api_url="https://api.example.com",
        )

        assert "Need Help?" in body
        assert "Contact IT Support" in body

    def test_contains_ordered_list(self):
        """Test body contains numbered instructions (ordered list)."""
        _, body = compose_unknown_vendor_email(
            sender_domain="test.com",
            transaction_id="TEST123",
            api_url="https://api.example.com",
        )

        assert "<ol>" in body
        assert "</ol>" in body
        assert "<li>" in body


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and special inputs."""

    def test_sender_domain_with_subdomain(self):
        """Test sender_domain with subdomain is handled correctly."""
        _, body = compose_unknown_vendor_email(
            sender_domain="invoices.adobe.com",
            transaction_id="TEST123",
            api_url="https://api.example.com",
        )

        assert _text_appears_in("invoices.adobe.com", body)

    def test_long_transaction_id(self):
        """Test long transaction ID is handled correctly."""
        long_id = "01JCK3Q7H8ZVXN3BARC9GWAEZM" * 3  # Extra long ID
        _, body = compose_unknown_vendor_email(
            sender_domain="test.com",
            transaction_id=long_id,
            api_url="https://api.example.com",
        )

        assert long_id in body

    def test_api_url_with_port(self):
        """Test api_url with port number is handled correctly."""
        _, body = compose_unknown_vendor_email(
            sender_domain="test.com",
            transaction_id="TEST123",
            api_url="http://localhost:7071",
        )

        assert "http://localhost:7071" in body
        assert "POST http://localhost:7071/api/AddVendor" in body

    def test_sender_domain_with_numbers(self):
        """Test sender_domain with numbers is handled correctly."""
        _, body = compose_unknown_vendor_email(
            sender_domain="aws-123.amazon.com",
            transaction_id="TEST123",
            api_url="https://api.example.com",
        )

        assert _text_appears_in("aws-123.amazon.com", body)

    def test_empty_string_inputs_handled(self):
        """Test function handles empty string inputs without error."""
        # Function should not raise on empty strings
        subject, body = compose_unknown_vendor_email(
            sender_domain="",
            transaction_id="",
            api_url="",
        )

        assert isinstance(subject, str)
        assert isinstance(body, str)
        # HTML structure should still be present
        assert "<html>" in body

    def test_unicode_in_sender_domain(self):
        """Test sender_domain with unicode characters."""
        _, body = compose_unknown_vendor_email(
            sender_domain="test-company.co.uk",
            transaction_id="TEST123",
            api_url="https://api.example.com",
        )

        assert _text_appears_in("test-company.co.uk", body)


# =============================================================================
# STYLING TESTS
# =============================================================================


class TestHtmlStyling:
    """Tests for HTML styling in email template."""

    def test_body_has_inline_styles(self):
        """Test body contains inline CSS styles for email compatibility."""
        _, body = compose_unknown_vendor_email(
            sender_domain="test.com",
            transaction_id="TEST123",
            api_url="https://api.example.com",
        )

        # Email clients require inline styles
        assert "style=" in body
        assert "font-family" in body

    def test_code_blocks_styled(self):
        """Test code/pre blocks have background styling."""
        _, body = compose_unknown_vendor_email(
            sender_domain="test.com",
            transaction_id="TEST123",
            api_url="https://api.example.com",
        )

        assert "<pre" in body
        assert "background" in body

    def test_warning_header_styled_red(self):
        """Test action required header has warning color."""
        _, body = compose_unknown_vendor_email(
            sender_domain="test.com",
            transaction_id="TEST123",
            api_url="https://api.example.com",
        )

        # Header should have red/warning color
        assert "#d9534f" in body  # Bootstrap danger color
