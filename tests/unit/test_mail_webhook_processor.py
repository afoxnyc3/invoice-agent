"""
Unit tests for MailWebhookProcessor queue function.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
import azure.functions as func
from MailWebhookProcessor import main


def _setup_config_mock(mock_config):
    """Helper to set up config mock with common properties."""
    mock_config.invoice_mailbox = "invoices@example.com"
    mock_blob_container = MagicMock()
    mock_blob_client = MagicMock()
    mock_blob_client.url = "https://storage.blob.core.windows.net/invoices/test.pdf"
    mock_blob_container.get_blob_client.return_value = mock_blob_client
    mock_config.get_container_client.return_value = mock_blob_container
    return mock_blob_container, mock_blob_client


def _create_queue_message(notification: dict) -> Mock:
    """Create a mock QueueMessage with given notification data."""
    msg = Mock(spec=func.QueueMessage)
    msg.get_body.return_value = json.dumps(notification).encode("utf-8")
    return msg


def _create_valid_notification() -> dict:
    """Create a valid webhook notification."""
    return {
        "id": "notification-123",
        "resource": "users/user@example.com/messages/msg-456",
        "changeType": "created",
    }


def _create_valid_email() -> dict:
    """Create a valid email response from Graph API."""
    return {
        "id": "msg-456",
        "hasAttachments": True,
        "sender": {"emailAddress": {"address": "vendor@adobe.com"}},
        "subject": "Invoice #12345",
        "receivedDateTime": "2024-11-10T10:00:00Z",
    }


class TestMailWebhookProcessor:
    """Test suite for MailWebhookProcessor function."""

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
    @patch("MailWebhookProcessor.process_email_attachments")
    @patch("MailWebhookProcessor.should_skip_email")
    @patch("MailWebhookProcessor.parse_webhook_resource")
    @patch("MailWebhookProcessor.GraphAPIClient")
    @patch("MailWebhookProcessor.config")
    def test_valid_notification_with_attachments(
        self,
        mock_config,
        mock_graph_class,
        mock_parse_resource,
        mock_should_skip,
        mock_process_attachments,
    ):
        """Test successful processing of valid notification with attachments."""
        mock_blob_container, _ = _setup_config_mock(mock_config)

        # Setup mocks
        mock_parse_resource.return_value = ("user@example.com", "msg-456")
        mock_graph = MagicMock()
        mock_graph_class.return_value = mock_graph
        mock_graph.get_email.return_value = _create_valid_email()
        mock_should_skip.return_value = (False, None)
        mock_process_attachments.return_value = 1

        # Create queue message and output
        msg = _create_queue_message(_create_valid_notification())
        mock_queue = Mock(spec=func.Out)

        # Execute
        main(msg, mock_queue)

        # Assertions
        mock_graph.get_email.assert_called_once_with("user@example.com", "msg-456")
        mock_process_attachments.assert_called_once()
        mock_graph.mark_as_read.assert_called_once_with("user@example.com", "msg-456")

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
    def test_missing_resource_field_raises(self):
        """Test that missing resource field raises ValueError."""
        notification = {"id": "notification-123", "changeType": "created"}
        msg = _create_queue_message(notification)
        mock_queue = Mock(spec=func.Out)

        with pytest.raises(ValueError, match="Notification missing resource field"):
            main(msg, mock_queue)

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
    @patch("MailWebhookProcessor.parse_webhook_resource")
    @patch("MailWebhookProcessor.GraphAPIClient")
    @patch("MailWebhookProcessor.config")
    def test_email_not_found_raises(self, mock_config, mock_graph_class, mock_parse_resource):
        """Test that missing email raises ValueError."""
        _setup_config_mock(mock_config)
        mock_parse_resource.return_value = ("user@example.com", "msg-456")
        mock_graph = MagicMock()
        mock_graph_class.return_value = mock_graph
        mock_graph.get_email.return_value = None

        msg = _create_queue_message(_create_valid_notification())
        mock_queue = Mock(spec=func.Out)

        with pytest.raises(ValueError, match="Email msg-456 not found"):
            main(msg, mock_queue)

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
    @patch("MailWebhookProcessor.should_skip_email")
    @patch("MailWebhookProcessor.parse_webhook_resource")
    @patch("MailWebhookProcessor.GraphAPIClient")
    @patch("MailWebhookProcessor.config")
    def test_should_skip_email_raises(self, mock_config, mock_graph_class, mock_parse_resource, mock_should_skip):
        """Test that email loop prevention raises ValueError."""
        _setup_config_mock(mock_config)
        mock_parse_resource.return_value = ("user@example.com", "msg-456")
        mock_graph = MagicMock()
        mock_graph_class.return_value = mock_graph
        mock_graph.get_email.return_value = _create_valid_email()
        mock_should_skip.return_value = (True, "Email from system mailbox")

        msg = _create_queue_message(_create_valid_notification())
        mock_queue = Mock(spec=func.Out)

        with pytest.raises(ValueError, match="Skipping email msg-456"):
            main(msg, mock_queue)

        # Email should be marked as read before raising
        mock_graph.mark_as_read.assert_called_once()

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
    @patch("MailWebhookProcessor.should_skip_email")
    @patch("MailWebhookProcessor.parse_webhook_resource")
    @patch("MailWebhookProcessor.GraphAPIClient")
    @patch("MailWebhookProcessor.config")
    def test_no_attachments_raises(self, mock_config, mock_graph_class, mock_parse_resource, mock_should_skip):
        """Test that email without attachments raises ValueError."""
        _setup_config_mock(mock_config)
        mock_parse_resource.return_value = ("user@example.com", "msg-456")
        mock_graph = MagicMock()
        mock_graph_class.return_value = mock_graph
        email = _create_valid_email()
        email["hasAttachments"] = False
        mock_graph.get_email.return_value = email
        mock_should_skip.return_value = (False, None)

        msg = _create_queue_message(_create_valid_notification())
        mock_queue = Mock(spec=func.Out)

        with pytest.raises(ValueError, match="Email msg-456 has no attachments"):
            main(msg, mock_queue)

        # Email should be marked as read before raising
        mock_graph.mark_as_read.assert_called_once()

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
    @patch("MailWebhookProcessor.parse_webhook_resource")
    @patch("MailWebhookProcessor.GraphAPIClient")
    @patch("MailWebhookProcessor.config")
    def test_graph_api_error_propagates(self, mock_config, mock_graph_class, mock_parse_resource):
        """Test that Graph API errors propagate correctly."""
        _setup_config_mock(mock_config)
        mock_parse_resource.return_value = ("user@example.com", "msg-456")
        mock_graph = MagicMock()
        mock_graph_class.return_value = mock_graph
        mock_graph.get_email.side_effect = Exception("Graph API connection failed")

        msg = _create_queue_message(_create_valid_notification())
        mock_queue = Mock(spec=func.Out)

        with pytest.raises(Exception, match="Graph API connection failed"):
            main(msg, mock_queue)

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
    def test_invalid_json_raises(self):
        """Test that invalid JSON raises JSONDecodeError."""
        msg = Mock(spec=func.QueueMessage)
        msg.get_body.return_value = b"not valid json"
        mock_queue = Mock(spec=func.Out)

        with pytest.raises(json.JSONDecodeError):
            main(msg, mock_queue)

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
    @patch("MailWebhookProcessor.parse_webhook_resource")
    @patch("MailWebhookProcessor.config")
    def test_parse_webhook_resource_error(self, mock_config, mock_parse_resource):
        """Test that invalid resource path raises ValueError."""
        _setup_config_mock(mock_config)
        mock_parse_resource.side_effect = ValueError("Invalid resource path")

        msg = _create_queue_message(_create_valid_notification())
        mock_queue = Mock(spec=func.Out)

        with pytest.raises(ValueError, match="Invalid resource path"):
            main(msg, mock_queue)

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
    @patch("MailWebhookProcessor.process_email_attachments")
    @patch("MailWebhookProcessor.should_skip_email")
    @patch("MailWebhookProcessor.parse_webhook_resource")
    @patch("MailWebhookProcessor.GraphAPIClient")
    @patch("MailWebhookProcessor.config")
    def test_pdf_extraction_success(
        self,
        mock_config,
        mock_graph_class,
        mock_parse_resource,
        mock_should_skip,
        mock_process_attachments,
    ):
        """Test successful PDF vendor extraction path."""
        mock_blob_container, _ = _setup_config_mock(mock_config)
        mock_parse_resource.return_value = ("user@example.com", "msg-456")
        mock_graph = MagicMock()
        mock_graph_class.return_value = mock_graph
        mock_graph.get_email.return_value = _create_valid_email()
        mock_should_skip.return_value = (False, None)
        mock_process_attachments.return_value = 2  # Two attachments processed

        msg = _create_queue_message(_create_valid_notification())
        mock_queue = Mock(spec=func.Out)

        main(msg, mock_queue)

        # Verify processing was called with all required args
        mock_process_attachments.assert_called_once()
        args = mock_process_attachments.call_args
        assert args[0][0] == _create_valid_email()  # email
        assert args[0][1] == mock_graph  # graph client
        assert args[0][2] == "user@example.com"  # mailbox
        assert args[0][3] == mock_blob_container  # blob container
        assert args[0][4] == mock_queue  # queue output

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
    @patch("MailWebhookProcessor.process_email_attachments")
    @patch("MailWebhookProcessor.should_skip_email")
    @patch("MailWebhookProcessor.parse_webhook_resource")
    @patch("MailWebhookProcessor.GraphAPIClient")
    @patch("MailWebhookProcessor.config")
    def test_pdf_extraction_fallback(
        self,
        mock_config,
        mock_graph_class,
        mock_parse_resource,
        mock_should_skip,
        mock_process_attachments,
    ):
        """Test PDF extraction fallback when extraction fails (graceful degradation)."""
        mock_blob_container, _ = _setup_config_mock(mock_config)
        mock_parse_resource.return_value = ("user@example.com", "msg-456")
        mock_graph = MagicMock()
        mock_graph_class.return_value = mock_graph
        mock_graph.get_email.return_value = _create_valid_email()
        mock_should_skip.return_value = (False, None)
        # process_email_attachments handles PDF extraction internally
        # and falls back to email domain if extraction fails
        mock_process_attachments.return_value = 1

        msg = _create_queue_message(_create_valid_notification())
        mock_queue = Mock(spec=func.Out)

        # Should complete without error even if PDF extraction failed internally
        main(msg, mock_queue)

        mock_process_attachments.assert_called_once()
        mock_graph.mark_as_read.assert_called_once()

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
    @patch("MailWebhookProcessor.process_email_attachments")
    @patch("MailWebhookProcessor.should_skip_email")
    @patch("MailWebhookProcessor.parse_webhook_resource")
    @patch("MailWebhookProcessor.GraphAPIClient")
    @patch("MailWebhookProcessor.config")
    def test_mark_as_read_called(
        self,
        mock_config,
        mock_graph_class,
        mock_parse_resource,
        mock_should_skip,
        mock_process_attachments,
    ):
        """Test that email is marked as read after successful processing."""
        _setup_config_mock(mock_config)
        mock_parse_resource.return_value = ("user@example.com", "msg-456")
        mock_graph = MagicMock()
        mock_graph_class.return_value = mock_graph
        mock_graph.get_email.return_value = _create_valid_email()
        mock_should_skip.return_value = (False, None)
        mock_process_attachments.return_value = 1

        msg = _create_queue_message(_create_valid_notification())
        mock_queue = Mock(spec=func.Out)

        main(msg, mock_queue)

        # Verify mark_as_read was called with correct arguments
        mock_graph.mark_as_read.assert_called_once_with("user@example.com", "msg-456")

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
    @patch("MailWebhookProcessor.process_email_attachments")
    @patch("MailWebhookProcessor.should_skip_email")
    @patch("MailWebhookProcessor.parse_webhook_resource")
    @patch("MailWebhookProcessor.GraphAPIClient")
    @patch("MailWebhookProcessor.config")
    def test_queue_output_format(
        self,
        mock_config,
        mock_graph_class,
        mock_parse_resource,
        mock_should_skip,
        mock_process_attachments,
    ):
        """Test that queue output is passed to process_email_attachments."""
        mock_blob_container, _ = _setup_config_mock(mock_config)
        mock_parse_resource.return_value = ("user@example.com", "msg-456")
        mock_graph = MagicMock()
        mock_graph_class.return_value = mock_graph
        mock_graph.get_email.return_value = _create_valid_email()
        mock_should_skip.return_value = (False, None)
        mock_process_attachments.return_value = 1

        msg = _create_queue_message(_create_valid_notification())
        mock_queue = Mock(spec=func.Out)

        main(msg, mock_queue)

        # Verify queue output was passed to process_email_attachments
        call_args = mock_process_attachments.call_args[0]
        assert call_args[4] == mock_queue  # Last positional arg is queue output
