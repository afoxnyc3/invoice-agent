"""
Unit tests for ExtractEnrich queue function.
"""
from unittest.mock import Mock, patch, MagicMock
import azure.functions as func
from functions.ExtractEnrich import main


class TestExtractEnrich:
    """Test suite for ExtractEnrich function."""

    @patch.dict('os.environ', {
        'AzureWebJobsStorage': 'DefaultEndpointsProtocol=https;AccountName=test',
        'INVOICE_MAILBOX': 'invoices@example.com',
        'FUNCTION_APP_URL': 'https://test-func.azurewebsites.net'
    })
    @patch('functions.ExtractEnrich.TableServiceClient')
    def test_extract_enrich_known_vendor(self, mock_table_service):
        """Test successful enrichment with known vendor."""
        # Mock table client
        mock_table_client = MagicMock()
        mock_table_service.from_connection_string.return_value.get_table_client.return_value = mock_table_client
        mock_table_client.get_entity.return_value = {
            'PartitionKey': 'Vendor',
            'RowKey': 'adobe_com',
            'VendorName': 'Adobe Inc',
            'ExpenseDept': 'IT',
            'GLCode': '6100',
            'AllocationScheduleNumber': 'MONTHLY',
            'BillingParty': 'ACME Corp'
        }

        # Mock queue message
        raw_mail_json = '''
        {
            "id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
            "sender": "billing@adobe.com",
            "subject": "Invoice #12345",
            "blob_url": "https://storage.blob.core.windows.net/invoices/test.pdf",
            "received_at": "2024-11-10T10:00:00Z"
        }
        '''
        msg = Mock(spec=func.QueueMessage)
        msg.get_body.return_value = raw_mail_json.encode()

        # Mock queue output
        mock_queue = Mock(spec=func.Out)
        queued_messages = []
        mock_queue.set = lambda m: queued_messages.append(m)

        # Execute function
        main(msg, mock_queue)

        # Assertions
        assert len(queued_messages) == 1
        enriched_data = queued_messages[0]
        assert 'Adobe Inc' in enriched_data
        assert '6100' in enriched_data
        assert 'IT' in enriched_data
        assert 'enriched' in enriched_data
        mock_table_client.get_entity.assert_called_once_with(
            partition_key='Vendor',
            row_key='adobe_com'
        )

    @patch.dict('os.environ', {
        'AzureWebJobsStorage': 'DefaultEndpointsProtocol=https;AccountName=test',
        'INVOICE_MAILBOX': 'invoices@example.com',
        'FUNCTION_APP_URL': 'https://test-func.azurewebsites.net'
    })
    @patch('functions.ExtractEnrich.GraphAPIClient')
    @patch('functions.ExtractEnrich.TableServiceClient')
    def test_extract_enrich_unknown_vendor(self, mock_table_service, mock_graph_class):
        """Test unknown vendor triggers registration email."""
        # Mock table client to raise exception (vendor not found)
        mock_table_client = MagicMock()
        mock_table_service.from_connection_string.return_value.get_table_client.return_value = mock_table_client
        mock_table_client.get_entity.side_effect = Exception("Entity not found")

        # Mock Graph API client
        mock_graph = MagicMock()
        mock_graph_class.return_value = mock_graph

        # Mock queue message
        raw_mail_json = '''
        {
            "id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
            "sender": "billing@unknown-vendor.com",
            "subject": "Invoice #99999",
            "blob_url": "https://storage.blob.core.windows.net/invoices/test.pdf",
            "received_at": "2024-11-10T10:00:00Z"
        }
        '''
        msg = Mock(spec=func.QueueMessage)
        msg.get_body.return_value = raw_mail_json.encode()

        # Mock queue output
        mock_queue = Mock(spec=func.Out)
        queued_messages = []
        mock_queue.set = lambda m: queued_messages.append(m)

        # Execute function
        main(msg, mock_queue)

        # Assertions
        assert len(queued_messages) == 0  # No message queued for unknown vendor
        mock_graph.send_email.assert_called_once()
        call_args = mock_graph.send_email.call_args
        assert call_args.kwargs['to_address'] == 'billing@unknown-vendor.com'
        assert call_args.kwargs['from_address'] == 'invoices@example.com'
        assert 'Action Required' in call_args.kwargs['subject']
        assert 'unknown-vendor_com' in call_args.kwargs['body']

    @patch.dict('os.environ', {
        'AzureWebJobsStorage': 'DefaultEndpointsProtocol=https;AccountName=test',
        'INVOICE_MAILBOX': 'invoices@example.com'
    })
    @patch('functions.ExtractEnrich.TableServiceClient')
    def test_extract_enrich_table_lookup(self, mock_table_service):
        """Test vendor table lookup with correct partition and row keys."""
        # Mock table client
        mock_table_client = MagicMock()
        mock_table_service.from_connection_string.return_value.get_table_client.return_value = mock_table_client
        mock_table_client.get_entity.return_value = {
            'VendorName': 'Microsoft',
            'ExpenseDept': 'IT',
            'GLCode': '6200',
            'AllocationScheduleNumber': 'ANNUAL',
            'BillingParty': 'ACME Corp'
        }

        # Mock queue message
        raw_mail_json = '''
        {
            "id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
            "sender": "accounts@microsoft.com",
            "subject": "Invoice",
            "blob_url": "https://storage.blob.core.windows.net/invoices/test.pdf",
            "received_at": "2024-11-10T10:00:00Z"
        }
        '''
        msg = Mock(spec=func.QueueMessage)
        msg.get_body.return_value = raw_mail_json.encode()

        mock_queue = Mock(spec=func.Out)
        mock_queue.set = lambda m: None

        # Execute function
        main(msg, mock_queue)

        # Verify correct partition and row key
        mock_table_client.get_entity.assert_called_once_with(
            partition_key='Vendor',
            row_key='microsoft_com'
        )

    @patch.dict('os.environ', {
        'AzureWebJobsStorage': 'DefaultEndpointsProtocol=https;AccountName=test'
    })
    def test_extract_enrich_invalid_message(self):
        """Test handling of invalid queue message."""
        # Invalid JSON message
        msg = Mock(spec=func.QueueMessage)
        msg.get_body.return_value = b'invalid json{'

        mock_queue = Mock(spec=func.Out)

        # Execute function - should raise exception
        try:
            main(msg, mock_queue)
            assert False, "Expected exception to be raised"
        except Exception:
            pass  # Expected

    @patch.dict('os.environ', {
        'AzureWebJobsStorage': 'DefaultEndpointsProtocol=https;AccountName=test',
        'INVOICE_MAILBOX': 'invoices@example.com'
    })
    @patch('functions.ExtractEnrich.TableServiceClient')
    def test_extract_enrich_domain_normalization(self, mock_table_service):
        """Test email domain extraction and normalization."""
        # Mock table client
        mock_table_client = MagicMock()
        mock_table_service.from_connection_string.return_value.get_table_client.return_value = mock_table_client
        mock_table_client.get_entity.return_value = {
            'VendorName': 'Adobe',
            'ExpenseDept': 'IT',
            'GLCode': '6100',
            'AllocationScheduleNumber': 'MONTHLY',
            'BillingParty': 'Test'
        }

        test_cases = [
            ("billing@adobe.com", "adobe_com"),
            ("invoices@accounts.microsoft.com", "microsoft_com"),
            ("ap@subdomain.oracle.com", "oracle_com")
        ]

        for email, expected_domain in test_cases:
            raw_mail_json = f'''
            {{
                "id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
                "sender": "{email}",
                "subject": "Invoice",
                "blob_url": "https://storage.blob.core.windows.net/invoices/test.pdf",
                "received_at": "2024-11-10T10:00:00Z"
            }}
            '''
            msg = Mock(spec=func.QueueMessage)
            msg.get_body.return_value = raw_mail_json.encode()

            mock_queue = Mock(spec=func.Out)
            mock_queue.set = lambda m: None

            main(msg, mock_queue)

            # Verify normalized domain was used for lookup
            assert mock_table_client.get_entity.call_args.kwargs['row_key'] == expected_domain
            mock_table_client.get_entity.reset_mock()
