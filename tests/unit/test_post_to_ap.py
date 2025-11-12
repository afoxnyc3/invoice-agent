"""
Unit tests for PostToAP queue function.
"""

import base64
from unittest.mock import Mock, patch, MagicMock
import azure.functions as func
from functions.PostToAP import main


class TestPostToAP:
    """Test suite for PostToAP function."""

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test",
            "INVOICE_MAILBOX": "invoices@example.com",
            "AP_EMAIL_ADDRESS": "ap@example.com",
        },
    )
    @patch("functions.PostToAP.GraphAPIClient")
    @patch("functions.PostToAP.TableServiceClient")
    @patch("functions.PostToAP.BlobServiceClient")
    def test_post_to_ap_success(self, mock_blob_service, mock_table_service, mock_graph_class):
        """Test successful AP posting with all components."""
        # Mock blob client
        mock_blob_client = MagicMock()
        mock_blob_client.download_blob.return_value.readall.return_value = b"PDF content"
        mock_blob_service.from_connection_string.return_value.get_blob_client.return_value = mock_blob_client

        # Mock table client
        mock_table_client = MagicMock()
        mock_table_service.from_connection_string.return_value.get_table_client.return_value = mock_table_client

        # Mock Graph API client
        mock_graph = MagicMock()
        mock_graph_class.return_value = mock_graph

        # Mock queue message
        enriched_json = """
        {
            "id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
            "vendor_name": "Adobe Inc",
            "expense_dept": "IT",
            "gl_code": "6100",
            "allocation_schedule": "MONTHLY",
            "billing_party": "ACME Corp",
            "blob_url": "https://storage.blob.core.windows.net/invoices/123/invoice.pdf",
            "status": "enriched"
        }
        """
        msg = Mock(spec=func.QueueMessage)
        msg.get_body.return_value = enriched_json.encode()

        # Mock queue output
        mock_queue = Mock(spec=func.Out)
        notifications = []
        mock_queue.set = lambda m: notifications.append(m)

        # Execute function
        main(msg, mock_queue)

        # Assertions - Email sent
        mock_graph.send_email.assert_called_once()
        call_args = mock_graph.send_email.call_args
        assert call_args.kwargs["to_address"] == "ap@example.com"
        assert call_args.kwargs["from_address"] == "invoices@example.com"
        assert "Adobe Inc" in call_args.kwargs["subject"]
        assert "6100" in call_args.kwargs["subject"]
        assert len(call_args.kwargs["attachments"]) == 1

        # Assertions - Transaction logged
        mock_table_client.upsert_entity.assert_called_once()

        # Assertions - Notification queued
        assert len(notifications) == 1
        assert "success" in notifications[0]
        assert "Adobe Inc" in notifications[0]

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test",
            "INVOICE_MAILBOX": "invoices@example.com",
            "AP_EMAIL_ADDRESS": "ap@example.com",
        },
    )
    @patch("functions.PostToAP.GraphAPIClient")
    @patch("functions.PostToAP.TableServiceClient")
    @patch("functions.PostToAP.BlobServiceClient")
    def test_post_to_ap_email_content(self, mock_blob_service, mock_table_service, mock_graph_class):
        """Test AP email contains all required metadata."""
        # Mock blob client
        mock_blob_client = MagicMock()
        mock_blob_client.download_blob.return_value.readall.return_value = b"PDF"
        mock_blob_service.from_connection_string.return_value.get_blob_client.return_value = mock_blob_client

        # Mock table client
        mock_table_client = MagicMock()
        mock_table_service.from_connection_string.return_value.get_table_client.return_value = mock_table_client

        # Mock Graph API
        mock_graph = MagicMock()
        mock_graph_class.return_value = mock_graph

        # Mock queue message
        enriched_json = """
        {
            "id": "TESTID123",
            "vendor_name": "Test Vendor",
            "expense_dept": "SALES",
            "gl_code": "7200",
            "allocation_schedule": "QUARTERLY",
            "billing_party": "Test Entity",
            "blob_url": "https://storage.blob.core.windows.net/invoices/test.pdf",
            "status": "enriched"
        }
        """
        msg = Mock(spec=func.QueueMessage)
        msg.get_body.return_value = enriched_json.encode()

        mock_queue = Mock(spec=func.Out)
        mock_queue.set = lambda m: None

        # Execute function
        main(msg, mock_queue)

        # Verify email body content
        call_args = mock_graph.send_email.call_args
        body = call_args.kwargs["body"]
        assert "TESTID123" in body
        assert "Test Vendor" in body
        assert "7200" in body
        assert "SALES" in body
        assert "QUARTERLY" in body
        assert "Test Entity" in body

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test",
            "INVOICE_MAILBOX": "invoices@example.com",
            "AP_EMAIL_ADDRESS": "ap@example.com",
        },
    )
    @patch("functions.PostToAP.GraphAPIClient")
    @patch("functions.PostToAP.TableServiceClient")
    @patch("functions.PostToAP.BlobServiceClient")
    def test_post_to_ap_attachment_format(self, mock_blob_service, mock_table_service, mock_graph_class):
        """Test PDF attachment is properly encoded."""
        # Mock blob client with specific content
        test_pdf = b"%PDF-1.4 test content"
        mock_blob_client = MagicMock()
        mock_blob_client.download_blob.return_value.readall.return_value = test_pdf
        mock_blob_service.from_connection_string.return_value.get_blob_client.return_value = mock_blob_client

        # Mock table client
        mock_table_client = MagicMock()
        mock_table_service.from_connection_string.return_value.get_table_client.return_value = mock_table_client

        # Mock Graph API
        mock_graph = MagicMock()
        mock_graph_class.return_value = mock_graph

        enriched_json = """
        {
            "id": "TESTID",
            "vendor_name": "Vendor",
            "expense_dept": "IT",
            "gl_code": "6100",
            "allocation_schedule": "MONTHLY",
            "billing_party": "Test",
            "blob_url": "https://storage.blob.core.windows.net/invoices/test.pdf",
            "status": "enriched"
        }
        """
        msg = Mock(spec=func.QueueMessage)
        msg.get_body.return_value = enriched_json.encode()

        mock_queue = Mock(spec=func.Out)
        mock_queue.set = lambda m: None

        # Execute function
        main(msg, mock_queue)

        # Verify attachment
        call_args = mock_graph.send_email.call_args
        attachments = call_args.kwargs["attachments"]
        assert len(attachments) == 1
        assert attachments[0]["name"] == "invoice_TESTID.pdf"
        assert attachments[0]["contentType"] == "application/pdf"
        # Verify content is base64 encoded
        assert attachments[0]["contentBytes"] == base64.b64encode(test_pdf).decode()

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test",
            "INVOICE_MAILBOX": "invoices@example.com",
            "AP_EMAIL_ADDRESS": "ap@example.com",
        },
    )
    @patch("functions.PostToAP.BlobServiceClient")
    def test_post_to_ap_blob_download_error(self, mock_blob_service):
        """Test handling of blob download errors."""
        # Mock blob client to raise exception
        mock_blob_client = MagicMock()
        mock_blob_client.download_blob.side_effect = Exception("Blob not found")
        mock_blob_service.from_connection_string.return_value.get_blob_client.return_value = mock_blob_client

        enriched_json = """
        {
            "id": "TEST",
            "vendor_name": "Vendor",
            "expense_dept": "IT",
            "gl_code": "6100",
            "allocation_schedule": "MONTHLY",
            "billing_party": "Test",
            "blob_url": "https://storage.blob.core.windows.net/invoices/missing.pdf",
            "status": "enriched"
        }
        """
        msg = Mock(spec=func.QueueMessage)
        msg.get_body.return_value = enriched_json.encode()

        mock_queue = Mock(spec=func.Out)

        # Execute function - should raise exception
        try:
            main(msg, mock_queue)
            assert False, "Expected exception to be raised"
        except Exception as e:
            assert "Blob not found" in str(e)

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test",
            "INVOICE_MAILBOX": "invoices@example.com",
            "AP_EMAIL_ADDRESS": "ap@example.com",
        },
    )
    @patch("functions.PostToAP.GraphAPIClient")
    @patch("functions.PostToAP.TableServiceClient")
    @patch("functions.PostToAP.BlobServiceClient")
    def test_post_to_ap_transaction_logging(self, mock_blob_service, mock_table_service, mock_graph_class):
        """Test transaction is logged with correct partition key format."""
        # Mock blob client
        mock_blob_client = MagicMock()
        mock_blob_client.download_blob.return_value.readall.return_value = b"PDF"
        mock_blob_service.from_connection_string.return_value.get_blob_client.return_value = mock_blob_client

        # Mock table client
        mock_table_client = MagicMock()
        mock_table_service.from_connection_string.return_value.get_table_client.return_value = mock_table_client

        # Mock Graph API
        mock_graph = MagicMock()
        mock_graph_class.return_value = mock_graph

        enriched_json = """
        {
            "id": "TXNID",
            "vendor_name": "Vendor",
            "expense_dept": "IT",
            "gl_code": "6100",
            "allocation_schedule": "MONTHLY",
            "billing_party": "Test",
            "blob_url": "https://storage.blob.core.windows.net/invoices/test.pdf",
            "status": "enriched"
        }
        """
        msg = Mock(spec=func.QueueMessage)
        msg.get_body.return_value = enriched_json.encode()

        mock_queue = Mock(spec=func.Out)
        mock_queue.set = lambda m: None

        # Execute function
        main(msg, mock_queue)

        # Verify transaction logging
        mock_table_client.upsert_entity.assert_called_once()
        transaction_data = mock_table_client.upsert_entity.call_args[0][0]
        # PartitionKey should be YYYYMM format
        assert len(transaction_data["PartitionKey"]) == 6
        assert transaction_data["PartitionKey"].isdigit()
        assert transaction_data["RowKey"] == "TXNID"
        assert transaction_data["VendorName"] == "Vendor"
        assert transaction_data["GLCode"] == "6100"
        assert transaction_data["Status"] == "processed"
