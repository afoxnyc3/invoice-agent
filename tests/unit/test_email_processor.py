"""
Unit tests for email_processor module.

Tests the shared email processing utilities including:
- parse_webhook_resource
- process_email_attachments
- should_skip_email
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
import base64

from shared.email_processor import (
    parse_webhook_resource,
    process_email_attachments,
    should_skip_email,
)


class TestParseWebhookResource:
    """Tests for parse_webhook_resource function."""

    def test_parses_valid_resource_path(self):
        """Parses valid Graph API resource path."""
        resource = "users/invoices@company.com/messages/AAMkAD123456"
        mailbox, message_id = parse_webhook_resource(resource)

        assert mailbox == "invoices@company.com"
        assert message_id == "AAMkAD123456"

    def test_parses_uppercase_users(self):
        """Handles uppercase 'Users' in path."""
        resource = "Users/invoices@company.com/Messages/AAMkAD123456"
        mailbox, message_id = parse_webhook_resource(resource)

        assert mailbox == "invoices@company.com"
        assert message_id == "AAMkAD123456"

    def test_parses_mixed_case(self):
        """Handles mixed case in path components."""
        resource = "USERS/invoices@company.com/MESSAGES/AAMkAD123456"
        mailbox, message_id = parse_webhook_resource(resource)

        assert mailbox == "invoices@company.com"
        assert message_id == "AAMkAD123456"

    def test_raises_on_invalid_path_too_short(self):
        """Raises ValueError on path with too few parts."""
        resource = "users/invoices@company.com"
        with pytest.raises(ValueError, match="Invalid webhook resource path"):
            parse_webhook_resource(resource)

    def test_raises_on_invalid_path_wrong_format(self):
        """Raises ValueError on path with wrong format."""
        resource = "groups/group-id/messages/msg123"
        with pytest.raises(ValueError, match="Invalid webhook resource path"):
            parse_webhook_resource(resource)

    def test_raises_on_missing_messages_segment(self):
        """Raises ValueError when 'messages' segment is missing."""
        resource = "users/invoices@company.com/folders/inbox"
        with pytest.raises(ValueError, match="Invalid webhook resource path"):
            parse_webhook_resource(resource)

    def test_raises_on_empty_mailbox(self):
        """Raises ValueError when mailbox is empty."""
        resource = "users//messages/AAMkAD123456"
        with pytest.raises(ValueError, match="Missing mailbox or message_id"):
            parse_webhook_resource(resource)

    def test_raises_on_empty_message_id(self):
        """Raises ValueError when message_id is empty."""
        resource = "users/invoices@company.com/messages/"
        with pytest.raises(ValueError, match="Missing mailbox or message_id"):
            parse_webhook_resource(resource)

    def test_handles_complex_message_id(self):
        """Handles complex Graph API message IDs."""
        long_id = "AAMkAGE4YjM2YjBkLWNiYTgtNDNhYy1hMTExLWI1ZDM4MzY3NjM3MgBGAAAAAADEPLDzrVtDQJrZ"
        resource = f"users/invoices@company.com/messages/{long_id}"
        mailbox, message_id = parse_webhook_resource(resource)

        assert mailbox == "invoices@company.com"
        assert message_id == long_id


class TestShouldSkipEmail:
    """Tests for should_skip_email function."""

    def test_skips_system_mailbox_sender(self):
        """Skips emails from the system mailbox."""
        email = {
            "sender": {"emailAddress": {"address": "invoices@company.com"}},
            "subject": "Invoice from Vendor",
        }
        should_skip, reason = should_skip_email(email, "invoices@company.com")

        assert should_skip is True
        assert "system mailbox" in reason.lower()

    def test_skips_system_mailbox_case_insensitive(self):
        """Skips system mailbox emails case-insensitively."""
        email = {
            "sender": {"emailAddress": {"address": "INVOICES@COMPANY.COM"}},
            "subject": "Invoice from Vendor",
        }
        should_skip, reason = should_skip_email(email, "invoices@company.com")

        assert should_skip is True

    def test_skips_system_generated_invoice_pattern(self):
        """Skips system-generated invoice email patterns."""
        email = {
            "sender": {"emailAddress": {"address": "vendor@external.com"}},
            "subject": "Invoice: Adobe Inc - GL 5010",
        }
        should_skip, reason = should_skip_email(email, "invoices@company.com")

        assert should_skip is True
        assert "system-generated" in reason.lower()

    def test_skips_system_generated_with_various_vendors(self):
        """Skips various system-generated invoice patterns."""
        test_subjects = [
            "Invoice: Microsoft Corp - GL 5020",
            "Invoice: Amazon Web Services - GL 6000",
            "Invoice: Acme Inc - GL 1234",
        ]
        for subject in test_subjects:
            email = {
                "sender": {"emailAddress": {"address": "vendor@external.com"}},
                "subject": subject,
            }
            should_skip, _ = should_skip_email(email, "invoices@company.com")
            assert should_skip is True, f"Should skip: {subject}"

    def test_skips_reply_to_registration_email(self):
        """Skips replies to vendor registration emails."""
        email = {
            "sender": {"emailAddress": {"address": "vendor@external.com"}},
            "subject": "Re: Vendor Registration Required - Invoice Agent",
        }
        should_skip, reason = should_skip_email(email, "invoices@company.com")

        assert should_skip is True
        assert "registration" in reason.lower()

    def test_does_not_skip_normal_invoice_email(self):
        """Does not skip normal invoice emails."""
        email = {
            "sender": {"emailAddress": {"address": "billing@vendor.com"}},
            "subject": "Invoice #12345 for December 2024",
        }
        should_skip, reason = should_skip_email(email, "invoices@company.com")

        assert should_skip is False
        assert reason == ""

    def test_does_not_skip_forwarded_invoice(self):
        """Does not skip forwarded invoices."""
        email = {
            "sender": {"emailAddress": {"address": "employee@company.com"}},
            "subject": "Fwd: Invoice from Adobe",
        }
        should_skip, reason = should_skip_email(email, "invoices@company.com")

        assert should_skip is False

    def test_handles_missing_sender(self):
        """Handles email with missing sender gracefully."""
        email = {
            "subject": "Test Invoice",
        }
        should_skip, reason = should_skip_email(email, "invoices@company.com")

        assert should_skip is False

    def test_handles_missing_subject(self):
        """Handles email with missing subject gracefully."""
        email = {
            "sender": {"emailAddress": {"address": "vendor@external.com"}},
        }
        should_skip, reason = should_skip_email(email, "invoices@company.com")

        assert should_skip is False


class TestProcessEmailAttachments:
    """Tests for process_email_attachments function."""

    @pytest.fixture
    def mock_email(self):
        """Create a mock email with PDF attachment."""
        return {
            "id": "msg123",
            "sender": {"emailAddress": {"address": "vendor@example.com"}},
            "subject": "Invoice #12345",
            "receivedDateTime": "2024-12-08T10:00:00Z",
        }

    @pytest.fixture
    def mock_graph_client(self):
        """Create a mock Graph API client."""
        client = MagicMock()
        return client

    @pytest.fixture
    def mock_blob_container(self):
        """Create a mock blob container client."""
        container = MagicMock()
        blob_client = MagicMock()
        blob_client.url = "https://storage.blob.core.windows.net/invoices/test.pdf"
        container.get_blob_client.return_value = blob_client
        return container

    @pytest.fixture
    def mock_queue_output(self):
        """Create a mock queue output binding."""
        return MagicMock()

    def test_processes_pdf_attachment(
        self, mock_email, mock_graph_client, mock_blob_container, mock_queue_output
    ):
        """Successfully processes email with PDF attachment."""
        # Setup attachment data
        pdf_content = b"%PDF-1.4 mock pdf content"
        mock_graph_client.get_attachments.return_value = [
            {
                "name": "invoice.pdf",
                "contentBytes": base64.b64encode(pdf_content).decode(),
            }
        ]

        with patch("shared.email_processor.extract_vendor_from_pdf") as mock_extract:
            mock_extract.return_value = "Adobe Inc"

            count = process_email_attachments(
                mock_email,
                mock_graph_client,
                "invoices@company.com",
                mock_blob_container,
                mock_queue_output,
            )

        assert count == 1
        mock_queue_output.set.assert_called_once()
        # Verify blob was uploaded
        mock_blob_container.get_blob_client.assert_called_once()

    def test_skips_non_pdf_attachments(
        self, mock_email, mock_graph_client, mock_blob_container, mock_queue_output
    ):
        """Skips non-PDF attachments like images."""
        mock_graph_client.get_attachments.return_value = [
            {
                "name": "signature.png",
                "contentBytes": base64.b64encode(b"image data").decode(),
            },
            {
                "name": "logo.jpg",
                "contentBytes": base64.b64encode(b"image data").decode(),
            },
        ]

        count = process_email_attachments(
            mock_email,
            mock_graph_client,
            "invoices@company.com",
            mock_blob_container,
            mock_queue_output,
        )

        assert count == 0
        mock_queue_output.set.assert_not_called()

    def test_returns_zero_for_no_attachments(
        self, mock_email, mock_graph_client, mock_blob_container, mock_queue_output
    ):
        """Returns 0 when email has no attachments."""
        mock_graph_client.get_attachments.return_value = []

        count = process_email_attachments(
            mock_email,
            mock_graph_client,
            "invoices@company.com",
            mock_blob_container,
            mock_queue_output,
        )

        assert count == 0
        mock_queue_output.set.assert_not_called()

    def test_processes_multiple_pdf_attachments(
        self, mock_email, mock_graph_client, mock_blob_container, mock_queue_output
    ):
        """Processes multiple PDF attachments from same email."""
        pdf_content = b"%PDF-1.4 mock pdf content"
        mock_graph_client.get_attachments.return_value = [
            {
                "name": "invoice1.pdf",
                "contentBytes": base64.b64encode(pdf_content).decode(),
            },
            {
                "name": "invoice2.PDF",  # uppercase extension
                "contentBytes": base64.b64encode(pdf_content).decode(),
            },
        ]

        with patch("shared.email_processor.extract_vendor_from_pdf") as mock_extract:
            mock_extract.return_value = None  # No vendor extracted

            count = process_email_attachments(
                mock_email,
                mock_graph_client,
                "invoices@company.com",
                mock_blob_container,
                mock_queue_output,
            )

        assert count == 2
        assert mock_queue_output.set.call_count == 2

    def test_handles_pdf_extraction_failure(
        self, mock_email, mock_graph_client, mock_blob_container, mock_queue_output
    ):
        """Continues processing when PDF extraction fails."""
        pdf_content = b"%PDF-1.4 mock pdf content"
        mock_graph_client.get_attachments.return_value = [
            {
                "name": "invoice.pdf",
                "contentBytes": base64.b64encode(pdf_content).decode(),
            }
        ]

        with patch("shared.email_processor.extract_vendor_from_pdf") as mock_extract:
            mock_extract.side_effect = Exception("OpenAI unavailable")

            count = process_email_attachments(
                mock_email,
                mock_graph_client,
                "invoices@company.com",
                mock_blob_container,
                mock_queue_output,
            )

        # Should still process despite extraction failure
        assert count == 1
        mock_queue_output.set.assert_called_once()

    def test_filters_mixed_attachment_types(
        self, mock_email, mock_graph_client, mock_blob_container, mock_queue_output
    ):
        """Only processes PDFs when mixed with other file types."""
        pdf_content = b"%PDF-1.4 mock pdf content"
        mock_graph_client.get_attachments.return_value = [
            {
                "name": "invoice.pdf",
                "contentBytes": base64.b64encode(pdf_content).decode(),
            },
            {
                "name": "signature.png",
                "contentBytes": base64.b64encode(b"image").decode(),
            },
            {
                "name": "document.docx",
                "contentBytes": base64.b64encode(b"doc").decode(),
            },
        ]

        with patch("shared.email_processor.extract_vendor_from_pdf") as mock_extract:
            mock_extract.return_value = "Test Vendor"

            count = process_email_attachments(
                mock_email,
                mock_graph_client,
                "invoices@company.com",
                mock_blob_container,
                mock_queue_output,
            )

        # Only the PDF should be processed
        assert count == 1

    def test_queue_message_contains_transaction_id(
        self, mock_email, mock_graph_client, mock_blob_container, mock_queue_output
    ):
        """Queue message contains a valid ULID transaction ID."""
        pdf_content = b"%PDF-1.4 mock pdf content"
        mock_graph_client.get_attachments.return_value = [
            {
                "name": "invoice.pdf",
                "contentBytes": base64.b64encode(pdf_content).decode(),
            }
        ]

        with patch("shared.email_processor.extract_vendor_from_pdf") as mock_extract:
            mock_extract.return_value = None

            process_email_attachments(
                mock_email,
                mock_graph_client,
                "invoices@company.com",
                mock_blob_container,
                mock_queue_output,
            )

        # Get the queued message JSON
        queued_json = mock_queue_output.set.call_args[0][0]
        assert "id" in queued_json
        # ULID is 26 characters
        import json
        msg = json.loads(queued_json)
        assert len(msg["id"]) == 26

    def test_includes_vendor_name_when_extracted(
        self, mock_email, mock_graph_client, mock_blob_container, mock_queue_output
    ):
        """Queue message includes vendor_name when PDF extraction succeeds."""
        pdf_content = b"%PDF-1.4 mock pdf content"
        mock_graph_client.get_attachments.return_value = [
            {
                "name": "invoice.pdf",
                "contentBytes": base64.b64encode(pdf_content).decode(),
            }
        ]

        with patch("shared.email_processor.extract_vendor_from_pdf") as mock_extract:
            mock_extract.return_value = "Adobe Inc"

            process_email_attachments(
                mock_email,
                mock_graph_client,
                "invoices@company.com",
                mock_blob_container,
                mock_queue_output,
            )

        import json
        queued_json = mock_queue_output.set.call_args[0][0]
        msg = json.loads(queued_json)
        assert msg["vendor_name"] == "Adobe Inc"
