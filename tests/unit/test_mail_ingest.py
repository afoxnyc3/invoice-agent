"""
Unit tests for MailIngest timer function.
"""

import base64
from unittest.mock import Mock, patch, MagicMock
import azure.functions as func
from MailIngest import main
from shared.models import RawMail


def _setup_config_mock(mock_config):
    """Helper to set up config mock with common properties."""
    mock_config.invoice_mailbox = "invoices@example.com"
    mock_config.graph_tenant_id = "test-tenant-id"
    mock_blob_container = MagicMock()
    mock_blob_client = MagicMock()
    mock_blob_client.url = "https://storage.blob.core.windows.net/invoices/test.pdf"
    mock_blob_container.get_blob_client.return_value = mock_blob_client
    mock_config.get_container_client.return_value = mock_blob_container
    return mock_blob_container, mock_blob_client


class TestMailIngest:
    """Test suite for MailIngest function."""

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
    @patch("MailIngest.config")
    def test_mail_ingest_with_attachment(self, mock_config, mock_graph_class):
        """Test successful email processing with attachment."""
        mock_blob_container, mock_blob_client = _setup_config_mock(mock_config)

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

        # Mock queue output
        mock_queue = Mock(spec=func.Out)
        queued_messages = []
        mock_queue.set = lambda msg: queued_messages.append(msg)

        # Execute function
        timer = Mock(spec=func.TimerRequest)
        main(timer, mock_queue)

        # Assertions
        assert len(queued_messages) == 1
        raw_mail = RawMail.model_validate_json(queued_messages[0])
        assert raw_mail.sender == "vendor@adobe.com"
        assert raw_mail.subject == "Invoice #12345"
        mock_blob_client.upload_blob.assert_called_once()

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
    @patch("MailIngest.config")
    def test_mail_ingest_without_attachment(self, mock_config, mock_graph_class):
        """Test email without attachment is skipped."""
        _setup_config_mock(mock_config)

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
        mock_graph.get_attachments.assert_not_called()

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
    @patch("MailIngest.config")
    def test_mail_ingest_multiple_emails(self, mock_config, mock_graph_class):
        """Test processing multiple emails."""
        mock_blob_container, mock_blob_client = _setup_config_mock(mock_config)

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

        # Mock queue output
        mock_queue = Mock(spec=func.Out)
        queued_messages = []
        mock_queue.set = lambda msg: queued_messages.append(msg)

        # Execute function
        timer = Mock(spec=func.TimerRequest)
        main(timer, mock_queue)

        # Assertions
        assert len(queued_messages) == 2
        raw_mail_1 = RawMail.model_validate_json(queued_messages[0])
        raw_mail_2 = RawMail.model_validate_json(queued_messages[1])
        assert raw_mail_1.sender == "vendor1@test.com"
        assert raw_mail_2.sender == "vendor2@test.com"

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
    @patch("MailIngest.config")
    def test_mail_ingest_graph_api_error(self, mock_config, mock_graph_class):
        """Test handling of Graph API errors."""
        _setup_config_mock(mock_config)

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
    @patch("MailIngest.GraphAPIClient")
    @patch("MailIngest.config")
    def test_mail_ingest_no_emails(self, mock_config, mock_graph_class):
        """Test when mailbox has no unread emails."""
        _setup_config_mock(mock_config)

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
    @patch("MailIngest.config")
    def test_mail_ingest_multiple_attachments(self, mock_config, mock_graph_class):
        """Test email with multiple attachments."""
        mock_blob_container, mock_blob_client = _setup_config_mock(mock_config)

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
