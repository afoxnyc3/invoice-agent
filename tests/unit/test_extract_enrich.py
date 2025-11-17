"""
Unit tests for ExtractEnrich queue function.
"""

from unittest.mock import Mock, patch, MagicMock
import azure.functions as func
from functions.ExtractEnrich import main


class TestExtractEnrich:
    """Test suite for ExtractEnrich function."""

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test",
            "INVOICE_MAILBOX": "invoices@example.com",
            "FUNCTION_APP_URL": "https://test-func.azurewebsites.net",
        },
    )
    @patch("functions.ExtractEnrich.TableServiceClient")
    def test_extract_enrich_known_vendor(self, mock_table_service):
        """Test successful enrichment with known vendor."""
        # Mock table client with query_entities for vendor lookup
        mock_table_client = MagicMock()
        mock_table_service.from_connection_string.return_value.get_table_client.return_value = mock_table_client
        mock_table_client.query_entities.return_value = [
            {
                "PartitionKey": "Vendor",
                "RowKey": "adobe",
                "VendorName": "Adobe",
                "ExpenseDept": "IT",
                "GLCode": "6100",
                "AllocationSchedule": "1",
                "ProductCategory": "Direct",
                "Active": True,
            }
        ]

        # Mock queue message with vendor_name provided
        raw_mail_json = """
        {
            "id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
            "sender": "billing@adobe.com",
            "subject": "Invoice #12345",
            "blob_url": "https://storage.blob.core.windows.net/invoices/test.pdf",
            "received_at": "2024-11-10T10:00:00Z",
            "vendor_name": "Adobe"
        }
        """
        msg = Mock(spec=func.QueueMessage)
        msg.get_body.return_value = raw_mail_json.encode()

        # Mock queue outputs
        to_post_queue = Mock(spec=func.Out)
        notify_queue = Mock(spec=func.Out)
        queued_messages = []
        to_post_queue.set = lambda m: queued_messages.append(m)

        # Execute function
        main(msg, to_post_queue, notify_queue)

        # Assertions
        assert len(queued_messages) == 1
        enriched_data = queued_messages[0]
        assert "Adobe" in enriched_data
        assert "6100" in enriched_data
        assert "IT" in enriched_data
        assert "enriched" in enriched_data

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test",
            "INVOICE_MAILBOX": "invoices@example.com",
            "FUNCTION_APP_URL": "https://test-func.azurewebsites.net",
        },
    )
    @patch("functions.ExtractEnrich.GraphAPIClient")
    @patch("functions.ExtractEnrich.TableServiceClient")
    def test_extract_enrich_unknown_vendor(self, mock_table_service, mock_graph_class):
        """Test unknown vendor triggers registration email."""
        # Mock table client to return empty list (vendor not found)
        mock_table_client = MagicMock()
        mock_table_service.from_connection_string.return_value.get_table_client.return_value = mock_table_client
        mock_table_client.query_entities.return_value = []

        # Mock Graph API client
        mock_graph = MagicMock()
        mock_graph_class.return_value = mock_graph

        # Mock queue message with unknown vendor
        raw_mail_json = """
        {
            "id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
            "sender": "billing@example.com",
            "subject": "Invoice #99999",
            "blob_url": "https://storage.blob.core.windows.net/invoices/test.pdf",
            "received_at": "2024-11-10T10:00:00Z",
            "vendor_name": "Unknown Vendor Corp"
        }
        """
        msg = Mock(spec=func.QueueMessage)
        msg.get_body.return_value = raw_mail_json.encode()

        # Mock queue outputs
        to_post_queue = Mock(spec=func.Out)
        notify_queue = Mock(spec=func.Out)
        queued_messages = []
        to_post_queue.set = lambda m: queued_messages.append(m)

        # Execute function
        main(msg, to_post_queue, notify_queue)

        # Assertions
        assert len(queued_messages) == 1  # Message should be queued with unknown status
        enriched_data = queued_messages[0]
        assert "unknown" in enriched_data
        mock_graph.send_email.assert_called_once()
        call_args = mock_graph.send_email.call_args
        assert call_args.kwargs["to_address"] == "billing@example.com"
        assert call_args.kwargs["from_address"] == "invoices@example.com"

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test",
            "INVOICE_MAILBOX": "invoices@example.com",
            "GRAPH_TENANT_ID": "test-tenant",
            "GRAPH_CLIENT_ID": "test-client",
            "GRAPH_CLIENT_SECRET": "test-secret",
            "FUNCTION_APP_URL": "https://test-func.azurewebsites.net",
        },
    )
    @patch("functions.ExtractEnrich.GraphAPIClient")
    @patch("functions.ExtractEnrich.TableServiceClient")
    def test_extract_enrich_reseller_vendor(self, mock_table_service, mock_graph_class):
        """Test reseller vendor is flagged for manual review."""
        # Mock GraphAPIClient
        mock_graph = MagicMock()
        mock_graph_class.return_value = mock_graph

        # Mock table client to return a reseller vendor
        mock_table_client = MagicMock()
        mock_table_service.from_connection_string.return_value.get_table_client.return_value = mock_table_client
        mock_table_client.query_entities.return_value = [
            {
                "VendorName": "Myriad360",
                "ExpenseDept": "Hardware - Operations",
                "GLCode": "6215",
                "AllocationSchedule": "NA",
                "ProductCategory": "Reseller",
                "Active": True,
            }
        ]

        # Mock queue message
        raw_mail_json = """
        {
            "id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
            "sender": "billing@example.com",
            "subject": "Invoice",
            "blob_url": "https://storage.blob.core.windows.net/invoices/test.pdf",
            "received_at": "2024-11-10T10:00:00Z",
            "vendor_name": "Myriad360"
        }
        """
        msg = Mock(spec=func.QueueMessage)
        msg.get_body.return_value = raw_mail_json.encode()

        to_post_queue = Mock(spec=func.Out)
        notify_queue = Mock(spec=func.Out)
        queued_messages = []
        to_post_queue.set = lambda m: queued_messages.append(m)

        # Execute function
        main(msg, to_post_queue, notify_queue)

        # Assertions - reseller should be flagged as unknown for manual review
        assert len(queued_messages) == 1
        enriched_data = queued_messages[0]
        assert "unknown" in enriched_data

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test",
            "INVOICE_MAILBOX": "invoices@example.com",
        },
    )
    def test_extract_enrich_invalid_message(self):
        """Test handling of invalid queue message."""
        # Invalid JSON message
        msg = Mock(spec=func.QueueMessage)
        msg.get_body.return_value = b"invalid json{"

        to_post_queue = Mock(spec=func.Out)
        notify_queue = Mock(spec=func.Out)

        # Execute function - should raise exception
        try:
            main(msg, to_post_queue, notify_queue)
            assert False, "Expected exception to be raised"
        except Exception:
            pass  # Expected

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test",
            "INVOICE_MAILBOX": "invoices@example.com",
            "GRAPH_TENANT_ID": "test-tenant",
            "GRAPH_CLIENT_ID": "test-client",
            "GRAPH_CLIENT_SECRET": "test-secret",
            "FUNCTION_APP_URL": "https://test-func.azurewebsites.net",
        },
    )
    @patch("functions.ExtractEnrich.TableServiceClient")
    def test_extract_enrich_case_insensitive_matching(self, mock_table_service):
        """Test vendor name matching is case-insensitive."""
        # Mock table client
        mock_table_client = MagicMock()
        mock_table_service.from_connection_string.return_value.get_table_client.return_value = mock_table_client
        mock_table_client.query_entities.return_value = [
            {
                "RowKey": "microsoft",
                "VendorName": "Microsoft",
                "ExpenseDept": "IT",
                "GLCode": "6200",
                "AllocationSchedule": "3",
                "ProductCategory": "Direct",
                "Active": True,
            }
        ]

        # Test with different case
        raw_mail_json = """
        {
            "id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
            "sender": "billing@example.com",
            "subject": "Invoice",
            "blob_url": "https://storage.blob.core.windows.net/invoices/test.pdf",
            "received_at": "2024-11-10T10:00:00Z",
            "vendor_name": "MICROSOFT"
        }
        """
        msg = Mock(spec=func.QueueMessage)
        msg.get_body.return_value = raw_mail_json.encode()

        to_post_queue = Mock(spec=func.Out)
        notify_queue = Mock(spec=func.Out)
        queued_messages = []
        to_post_queue.set = lambda m: queued_messages.append(m)

        main(msg, to_post_queue, notify_queue)

        # Should match despite case difference
        assert len(queued_messages) == 1
        enriched_data = queued_messages[0]
        assert "Microsoft" in enriched_data
        assert "enriched" in enriched_data
