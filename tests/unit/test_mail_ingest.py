"""
Unit tests for MailIngest timer function.
"""

import base64
import logging
from unittest.mock import Mock, patch, MagicMock
import azure.functions as func
from MailIngest import main


class TestMailIngest:
    """Test suite for MailIngest function."""

    @patch("shared.email_processor.extract_vendor_from_pdf", return_value=None)
    @patch.dict(
        "os.environ",
        {
            "INVOICE_MAILBOX": "invoices@example.com",
            "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test",
            "GRAPH_TENANT_ID": "tenant",
            "GRAPH_CLIENT_ID": "client",
            "GRAPH_CLIENT_SECRET": "secret",
        },
    )
    @patch("MailIngest.BlobServiceClient")
    @patch("MailIngest.GraphAPIClient")
    def test_mail_ingest_with_attachment(
        self, mock_graph_class, mock_blob_service, mock_pdf_extractor
    ):
        """Test successful email processing with attachment."""
        # Mock Graph API client
        mock_graph = MagicMock()
        mock_graph_class.return_value = mock_graph
        mock_graph.get_unread_emails.return_value = [
            {
                "id": "email-123",
                "hasAttachments": True,
                "sender": {"emailAddress": {"address": "vendor@adobe.com"}},
                "subject": "Invoice #12345",
                "receivedDateTime": "2024-11-10T10:00:00Z",
            }
        ]
        mock_graph.get_attachments.return_value = [
            {
                "id": "att-1",
                "name": "invoice.pdf",
                "contentBytes": base64.b64encode(b"PDF content").decode(),
                "contentType": "application/pdf",
                "size": 1024,
            }
        ]

        # Mock Blob Storage
        mock_blob_container = MagicMock()
        mock_blob_client = MagicMock()
        mock_blob_client.url = "https://storage.blob.core.windows.net/invoices/123/invoice.pdf"
        mock_blob_container.get_blob_client.return_value = mock_blob_client
        mock_blob_service.from_connection_string.return_value.get_container_client.return_value = mock_blob_container

        # Mock queue output
        mock_queue = Mock(spec=func.Out)
        queued_messages = []
        mock_queue.set = lambda msg: queued_messages.append(msg)

        # Execute function
        timer = Mock(spec=func.TimerRequest)
        main(timer, mock_queue)

        # Assertions
        assert len(queued_messages) == 1
        assert "vendor@adobe.com" in queued_messages[0]
        assert "Invoice #12345" in queued_messages[0]
        mock_blob_client.upload_blob.assert_called_once()
        # mark_as_read temporarily disabled for security - requires Mail.ReadWrite permission
        # mock_graph.mark_as_read.assert_called_once_with("invoices@example.com", "email-123")

    @patch.dict(
        "os.environ",
        {
            "INVOICE_MAILBOX": "invoices@example.com",
            "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test",
            "GRAPH_TENANT_ID": "tenant",
            "GRAPH_CLIENT_ID": "client",
            "GRAPH_CLIENT_SECRET": "secret",
        },
    )
    @patch("MailIngest.BlobServiceClient")
    @patch("MailIngest.GraphAPIClient")
    def test_mail_ingest_without_attachment(self, mock_graph_class, mock_blob_service):
        """Test email without attachment is skipped."""
        # Mock Graph API client
        mock_graph = MagicMock()
        mock_graph_class.return_value = mock_graph
        mock_graph.get_unread_emails.return_value = [
            {
                "id": "email-456",
                "hasAttachments": False,
                "sender": {"emailAddress": {"address": "vendor@test.com"}},
                "subject": "No attachment",
                "receivedDateTime": "2024-11-10T10:00:00Z",
            }
        ]

        # Mock queue output
        mock_queue = Mock(spec=func.Out)
        queued_messages = []
        mock_queue.set = lambda msg: queued_messages.append(msg)

        # Execute function
        timer = Mock(spec=func.TimerRequest)
        main(timer, mock_queue)

        # Assertions
        assert len(queued_messages) == 0  # Nothing queued
        # mark_as_read temporarily disabled for security - requires Mail.ReadWrite permission
        # mock_graph.mark_as_read.assert_called_once_with("invoices@example.com", "email-456")
        mock_graph.get_attachments.assert_not_called()

    @patch("shared.email_processor.extract_vendor_from_pdf", return_value=None)
    @patch.dict(
        "os.environ",
        {
            "INVOICE_MAILBOX": "invoices@example.com",
            "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test",
            "GRAPH_TENANT_ID": "tenant",
            "GRAPH_CLIENT_ID": "client",
            "GRAPH_CLIENT_SECRET": "secret",
        },
    )
    @patch("MailIngest.BlobServiceClient")
    @patch("MailIngest.GraphAPIClient")
    def test_mail_ingest_multiple_emails(
        self, mock_graph_class, mock_blob_service, mock_pdf_extractor
    ):
        """Test processing multiple emails."""
        # Mock Graph API client
        mock_graph = MagicMock()
        mock_graph_class.return_value = mock_graph
        mock_graph.get_unread_emails.return_value = [
            {
                "id": "email-1",
                "hasAttachments": True,
                "sender": {"emailAddress": {"address": "vendor1@test.com"}},
                "subject": "Invoice 1",
                "receivedDateTime": "2024-11-10T10:00:00Z",
            },
            {
                "id": "email-2",
                "hasAttachments": True,
                "sender": {"emailAddress": {"address": "vendor2@test.com"}},
                "subject": "Invoice 2",
                "receivedDateTime": "2024-11-10T11:00:00Z",
            },
        ]
        mock_graph.get_attachments.return_value = [
            {
                "id": "att-1",
                "name": "invoice.pdf",
                "contentBytes": base64.b64encode(b"PDF").decode(),
                "contentType": "application/pdf",
                "size": 100,
            }
        ]

        # Mock Blob Storage
        mock_blob_container = MagicMock()
        mock_blob_client = MagicMock()
        mock_blob_client.url = "https://storage.blob.core.windows.net/invoices/test.pdf"
        mock_blob_container.get_blob_client.return_value = mock_blob_client
        mock_blob_service.from_connection_string.return_value.get_container_client.return_value = mock_blob_container

        # Mock queue output
        mock_queue = Mock(spec=func.Out)
        queued_messages = []
        mock_queue.set = lambda msg: queued_messages.append(msg)

        # Execute function
        timer = Mock(spec=func.TimerRequest)
        main(timer, mock_queue)

        # Assertions
        assert len(queued_messages) == 2
        assert "vendor1@test.com" in queued_messages[0]
        assert "vendor2@test.com" in queued_messages[1]
        # mark_as_read temporarily disabled for security - requires Mail.ReadWrite permission
        # assert mock_graph.mark_as_read.call_count == 2

    @patch.dict(
        "os.environ",
        {
            "INVOICE_MAILBOX": "invoices@example.com",
            "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test",
            "GRAPH_TENANT_ID": "tenant",
            "GRAPH_CLIENT_ID": "client",
            "GRAPH_CLIENT_SECRET": "secret",
        },
    )
    @patch("MailIngest.GraphAPIClient")
    def test_mail_ingest_graph_api_error(self, mock_graph_class):
        """Test handling of Graph API errors."""
        # Mock Graph API client to raise exception
        mock_graph = MagicMock()
        mock_graph_class.return_value = mock_graph
        mock_graph.get_unread_emails.side_effect = Exception("Graph API connection failed")

        # Mock queue output
        mock_queue = Mock(spec=func.Out)

        # Execute function - should raise exception
        timer = Mock(spec=func.TimerRequest)
        try:
            main(timer, mock_queue)
            assert False, "Expected exception to be raised"
        except Exception as e:
            assert "Graph API connection failed" in str(e)

    @patch.dict(
        "os.environ",
        {
            "INVOICE_MAILBOX": "invoices@example.com",
            "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test",
            "GRAPH_TENANT_ID": "tenant",
            "GRAPH_CLIENT_ID": "client",
            "GRAPH_CLIENT_SECRET": "secret",
        },
    )
    @patch("MailIngest.BlobServiceClient")
    @patch("MailIngest.GraphAPIClient")
    def test_mail_ingest_no_emails(self, mock_graph_class, mock_blob_service):
        """Test when mailbox has no unread emails."""
        # Mock Graph API client
        mock_graph = MagicMock()
        mock_graph_class.return_value = mock_graph
        mock_graph.get_unread_emails.return_value = []

        # Mock queue output
        mock_queue = Mock(spec=func.Out)
        queued_messages = []
        mock_queue.set = lambda msg: queued_messages.append(msg)

        # Execute function
        timer = Mock(spec=func.TimerRequest)
        main(timer, mock_queue)

        # Assertions
        assert len(queued_messages) == 0
        mock_graph.mark_as_read.assert_not_called()

    @patch("shared.email_processor.extract_vendor_from_pdf", return_value=None)
    @patch.dict(
        "os.environ",
        {
            "INVOICE_MAILBOX": "invoices@example.com",
            "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test",
            "GRAPH_TENANT_ID": "tenant",
            "GRAPH_CLIENT_ID": "client",
            "GRAPH_CLIENT_SECRET": "secret",
        },
    )
    @patch("MailIngest.BlobServiceClient")
    @patch("MailIngest.GraphAPIClient")
    def test_mail_ingest_multiple_attachments(
        self, mock_graph_class, mock_blob_service, mock_pdf_extractor
    ):
        """Test email with multiple attachments."""
        # Mock Graph API client
        mock_graph = MagicMock()
        mock_graph_class.return_value = mock_graph
        mock_graph.get_unread_emails.return_value = [
            {
                "id": "email-multi",
                "hasAttachments": True,
                "sender": {"emailAddress": {"address": "vendor@test.com"}},
                "subject": "Multiple attachments",
                "receivedDateTime": "2024-11-10T10:00:00Z",
            }
        ]
        mock_graph.get_attachments.return_value = [
            {
                "id": "att-1",
                "name": "invoice.pdf",
                "contentBytes": base64.b64encode(b"PDF1").decode(),
                "contentType": "application/pdf",
                "size": 100,
            },
            {
                "id": "att-2",
                "name": "receipt.pdf",
                "contentBytes": base64.b64encode(b"PDF2").decode(),
                "contentType": "application/pdf",
                "size": 200,
            },
        ]

        # Mock Blob Storage
        mock_blob_container = MagicMock()
        mock_blob_client = MagicMock()
        mock_blob_client.url = "https://storage.blob.core.windows.net/invoices/test.pdf"
        mock_blob_container.get_blob_client.return_value = mock_blob_client
        mock_blob_service.from_connection_string.return_value.get_container_client.return_value = mock_blob_container

        # Mock queue output
        mock_queue = Mock(spec=func.Out)
        queued_messages = []
        mock_queue.set = lambda msg: queued_messages.append(msg)

        # Execute function
        timer = Mock(spec=func.TimerRequest)
        main(timer, mock_queue)

        # Assertions
        assert len(queued_messages) == 2  # One message per attachment
        assert mock_blob_client.upload_blob.call_count == 2
        # mark_as_read temporarily disabled for security - requires Mail.ReadWrite permission
        # mock_graph.mark_as_read.assert_called_once()

    @patch("MailIngest.GraphAPIClient")
    def test_mail_ingest_disabled_by_flag(self, mock_graph_class, caplog):
        """Ensure the timer exits early when MAIL_INGEST_ENABLED disables it."""

        with patch.dict("os.environ", {"MAIL_INGEST_ENABLED": "false"}, clear=True):
            mock_queue = Mock(spec=func.Out)
            caplog.set_level(logging.INFO)
            timer = Mock(spec=func.TimerRequest)

            main(timer, mock_queue)

        mock_graph_class.assert_not_called()
        mock_queue.set.assert_not_called()
        assert "MailIngest disabled via MAIL_INGEST_ENABLED" in caplog.text

    @patch("MailIngest.GraphAPIClient")
    def test_mail_ingest_missing_settings_is_non_fatal(self, mock_graph_class, caplog):
        """Missing critical settings should warn and exit instead of throwing."""

        with patch.dict("os.environ", {}, clear=True):
            mock_queue = Mock(spec=func.Out)
            caplog.set_level(logging.WARNING)
            timer = Mock(spec=func.TimerRequest)

            main(timer, mock_queue)

        mock_graph_class.assert_not_called()
        mock_queue.set.assert_not_called()
        assert "missing required settings" in caplog.text
