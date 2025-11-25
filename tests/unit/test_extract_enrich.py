"""
Unit tests for ExtractEnrich queue function.
"""

from unittest.mock import Mock, patch, MagicMock
import azure.functions as func
from azure.core.exceptions import ResourceExistsError
from ExtractEnrich import main


class TestExtractEnrich:
    """Test suite for ExtractEnrich function."""

    def _setup_table_mocks(self, mock_table_service, vendor_results=None, tx_results=None):
        """Helper to set up separate mocks for VendorMaster and InvoiceTransactions tables."""
        vendor_client = MagicMock()
        tx_client = MagicMock()

        vendor_client.query_entities.return_value = vendor_results if vendor_results else []
        tx_client.query_entities.return_value = tx_results if tx_results else []

        def get_table_client(table_name):
            if table_name == "VendorMaster":
                return vendor_client
            elif table_name == "InvoiceTransactions":
                return tx_client
            return MagicMock()

        mock_table_service.from_connection_string.return_value.get_table_client.side_effect = get_table_client
        return vendor_client, tx_client

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test",
            "INVOICE_MAILBOX": "invoices@example.com",
            "FUNCTION_APP_URL": "https://test-func.azurewebsites.net",
        },
    )
    @patch("ExtractEnrich.TableServiceClient")
    def test_extract_enrich_known_vendor(self, mock_table_service):
        """Test successful enrichment with known vendor."""
        # Set up separate table client mocks
        vendor_data = [
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
        self._setup_table_mocks(mock_table_service, vendor_results=vendor_data, tx_results=[])

        # Mock queue message with vendor_name provided
        raw_mail_json = """
        {
            "id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
            "sender": "billing@adobe.com",
            "subject": "Invoice #12345",
            "blob_url": "https://storage.blob.core.windows.net/invoices/test.pdf",
            "received_at": "2024-11-10T10:00:00Z",
            "original_message_id": "graph-message-id-123",
            "vendor_name": "Adobe"
        }
        """
        msg = Mock(spec=func.QueueMessage)
        msg.get_body.return_value = raw_mail_json.encode()

        # Mock queue outputs
        to_post_queue = Mock(spec=func.Out)
        _notify_queue = Mock(spec=func.Out)  # noqa: F841 - intentionally unused
        queued_messages = []
        to_post_queue.set = lambda m: queued_messages.append(m)

        # Execute function
        main(msg, to_post_queue)

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
    @patch("ExtractEnrich.GraphAPIClient")
    @patch("ExtractEnrich.TableServiceClient")
    def test_extract_enrich_unknown_vendor(self, mock_table_service, mock_graph_class):
        """Test unknown vendor triggers registration email and returns without queueing."""
        # Set up separate table client mocks (no vendor, no existing tx)
        _vendor_client, tx_client = self._setup_table_mocks(mock_table_service, vendor_results=[], tx_results=[])

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
            "original_message_id": "graph-message-id-456",
            "vendor_name": "Unknown Vendor Corp"
        }
        """
        msg = Mock(spec=func.QueueMessage)
        msg.get_body.return_value = raw_mail_json.encode()

        # Mock queue outputs
        to_post_queue = Mock(spec=func.Out)
        _notify_queue = Mock(spec=func.Out)  # noqa: F841 - intentionally unused
        queued_messages = []
        to_post_queue.set = lambda m: queued_messages.append(m)

        # Execute function
        main(msg, to_post_queue)

        # Assertions - unknown vendor records transaction and sends email, but no queue message
        assert len(queued_messages) == 0  # No message queued for unknown vendors
        tx_client.create_entity.assert_called_once()  # Transaction recorded
        mock_graph.send_email.assert_called_once()  # Registration email sent
        call_args = mock_graph.send_email.call_args
        assert call_args.kwargs["to_address"] == "billing@example.com"
        assert call_args.kwargs["from_address"] == "invoices@example.com"

    @patch.dict(
        "os.environ",
        {
            "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test",
            "INVOICE_MAILBOX": "invoices@example.com",
            "FUNCTION_APP_URL": "https://test-func.azurewebsites.net",
        },
    )
    @patch("ExtractEnrich.GraphAPIClient")
    @patch("ExtractEnrich.TableServiceClient")
    def test_extract_enrich_unknown_vendor_race_condition(self, mock_table_service, mock_graph_class):
        """Test race condition: second instance doesn't send duplicate email."""
        # Set up separate table client mocks
        _vendor_client, tx_client = self._setup_table_mocks(mock_table_service, vendor_results=[], tx_results=[])
        # Simulate race condition: create_entity fails with ResourceExistsError
        tx_client.create_entity.side_effect = ResourceExistsError("Entity already exists")

        # Mock Graph API client
        mock_graph = MagicMock()
        mock_graph_class.return_value = mock_graph

        # Mock queue message
        raw_mail_json = """
        {
            "id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
            "sender": "billing@example.com",
            "subject": "Invoice #99999",
            "blob_url": "https://storage.blob.core.windows.net/invoices/test.pdf",
            "received_at": "2024-11-10T10:00:00Z",
            "original_message_id": "graph-message-id-456",
            "vendor_name": "Unknown Vendor Corp"
        }
        """
        msg = Mock(spec=func.QueueMessage)
        msg.get_body.return_value = raw_mail_json.encode()

        to_post_queue = Mock(spec=func.Out)
        queued_messages = []
        to_post_queue.set = lambda m: queued_messages.append(m)

        # Execute function
        main(msg, to_post_queue)

        # Assertions - second instance should not send email
        assert len(queued_messages) == 0
        tx_client.create_entity.assert_called_once()  # Attempt was made
        mock_graph.send_email.assert_not_called()  # But email was NOT sent

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
    @patch("ExtractEnrich.GraphAPIClient")
    @patch("ExtractEnrich.TableServiceClient")
    def test_extract_enrich_reseller_vendor(self, mock_table_service, mock_graph_class):
        """Test reseller vendor is flagged for manual review."""
        # Mock GraphAPIClient
        mock_graph = MagicMock()
        mock_graph_class.return_value = mock_graph

        # Set up table mocks with reseller vendor
        vendor_data = [
            {
                "RowKey": "myriad360",
                "VendorName": "Myriad360",
                "ExpenseDept": "Hardware - Operations",
                "GLCode": "6215",
                "AllocationSchedule": "NA",
                "ProductCategory": "Reseller",
                "Active": True,
            }
        ]
        self._setup_table_mocks(mock_table_service, vendor_results=vendor_data, tx_results=[])

        # Mock queue message
        raw_mail_json = """
        {
            "id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
            "sender": "billing@example.com",
            "subject": "Invoice",
            "blob_url": "https://storage.blob.core.windows.net/invoices/test.pdf",
            "received_at": "2024-11-10T10:00:00Z",
            "original_message_id": "graph-message-id-789",
            "vendor_name": "Myriad360"
        }
        """
        msg = Mock(spec=func.QueueMessage)
        msg.get_body.return_value = raw_mail_json.encode()

        to_post_queue = Mock(spec=func.Out)
        _notify_queue = Mock(spec=func.Out)  # noqa: F841 - intentionally unused
        queued_messages = []
        to_post_queue.set = lambda m: queued_messages.append(m)

        # Execute function
        main(msg, to_post_queue)

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
        _notify_queue = Mock(spec=func.Out)  # noqa: F841 - intentionally unused

        # Execute function - should raise exception
        try:
            main(msg, to_post_queue)
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
    @patch("ExtractEnrich.TableServiceClient")
    def test_extract_enrich_case_insensitive_matching(self, mock_table_service):
        """Test vendor name matching is case-insensitive."""
        # Set up table mocks
        vendor_data = [
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
        self._setup_table_mocks(mock_table_service, vendor_results=vendor_data, tx_results=[])

        # Test with different case
        raw_mail_json = """
        {
            "id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
            "sender": "billing@example.com",
            "subject": "Invoice",
            "blob_url": "https://storage.blob.core.windows.net/invoices/test.pdf",
            "received_at": "2024-11-10T10:00:00Z",
            "original_message_id": "graph-message-id-abc",
            "vendor_name": "MICROSOFT"
        }
        """
        msg = Mock(spec=func.QueueMessage)
        msg.get_body.return_value = raw_mail_json.encode()

        to_post_queue = Mock(spec=func.Out)
        _notify_queue = Mock(spec=func.Out)  # noqa: F841 - intentionally unused
        queued_messages = []
        to_post_queue.set = lambda m: queued_messages.append(m)

        main(msg, to_post_queue)

        # Should match despite case difference
        assert len(queued_messages) == 1
        enriched_data = queued_messages[0]
        assert "Microsoft" in enriched_data
        assert "enriched" in enriched_data
