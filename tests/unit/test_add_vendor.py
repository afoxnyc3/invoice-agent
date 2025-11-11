"""
Unit tests for AddVendor HTTP function.
"""
import json
from unittest.mock import Mock, patch, MagicMock
import azure.functions as func
from functions.AddVendor import main


class TestAddVendor:
    """Test suite for AddVendor function."""

    @patch.dict('os.environ', {'AzureWebJobsStorage': 'DefaultEndpointsProtocol=https;AccountName=test'})
    @patch('functions.AddVendor.TableServiceClient')
    def test_add_vendor_success(self, mock_table_service):
        """Test successful vendor creation."""
        # Mock table client
        mock_table_client = MagicMock()
        mock_table_service.from_connection_string.return_value.get_table_client.return_value = mock_table_client

        # Create request with valid vendor data
        req_body = {
            "vendor_domain": "adobe.com",
            "vendor_name": "Adobe Inc",
            "expense_dept": "IT",
            "gl_code": "6100",
            "allocation_schedule": "MONTHLY",
            "billing_party": "ACME Corp"
        }
        req = func.HttpRequest(
            method='POST',
            url='/api/AddVendor',
            body=json.dumps(req_body).encode('utf-8')
        )

        # Execute function
        response = main(req)

        # Assertions
        assert response.status_code == 201
        response_data = json.loads(response.get_body())
        assert response_data['status'] == 'success'
        assert response_data['vendor'] == 'Adobe Inc'
        mock_table_client.upsert_entity.assert_called_once()

        # Verify domain normalization
        call_args = mock_table_client.upsert_entity.call_args[0][0]
        assert call_args['RowKey'] == 'adobe_com'
        assert call_args['PartitionKey'] == 'Vendor'

    @patch('functions.AddVendor.TableServiceClient')
    def test_add_vendor_invalid_gl_code(self, mock_table_service):
        """Test validation fails with invalid GL code."""
        req_body = {
            "vendor_domain": "test.com",
            "vendor_name": "Test Corp",
            "expense_dept": "IT",
            "gl_code": "123",  # Invalid: only 3 digits
            "allocation_schedule": "MONTHLY",
            "billing_party": "ACME Corp"
        }
        req = func.HttpRequest(
            method='POST',
            url='/api/AddVendor',
            body=json.dumps(req_body).encode('utf-8')
        )

        response = main(req)

        assert response.status_code == 400
        response_data = json.loads(response.get_body())
        assert response_data['error'] == 'Validation failed'
        assert 'details' in response_data

    @patch('functions.AddVendor.TableServiceClient')
    def test_add_vendor_missing_required_field(self, mock_table_service):
        """Test validation fails with missing required field."""
        req_body = {
            "vendor_domain": "test.com",
            "vendor_name": "Test Corp",
            # Missing expense_dept
            "gl_code": "6100",
            "allocation_schedule": "MONTHLY",
            "billing_party": "ACME Corp"
        }
        req = func.HttpRequest(
            method='POST',
            url='/api/AddVendor',
            body=json.dumps(req_body).encode('utf-8')
        )

        response = main(req)

        assert response.status_code == 400
        response_data = json.loads(response.get_body())
        assert response_data['error'] == 'Validation failed'

    @patch.dict('os.environ', {'AzureWebJobsStorage': 'DefaultEndpointsProtocol=https;AccountName=test'})
    @patch('functions.AddVendor.TableServiceClient')
    def test_add_vendor_duplicate_update(self, mock_table_service):
        """Test upserting duplicate vendor (should update)."""
        mock_table_client = MagicMock()
        mock_table_service.from_connection_string.return_value.get_table_client.return_value = mock_table_client

        req_body = {
            "vendor_domain": "adobe.com",
            "vendor_name": "Adobe Inc Updated",
            "expense_dept": "SALES",
            "gl_code": "6200",
            "allocation_schedule": "ANNUAL",
            "billing_party": "New Entity"
        }
        req = func.HttpRequest(
            method='POST',
            url='/api/AddVendor',
            body=json.dumps(req_body).encode('utf-8')
        )

        response = main(req)

        assert response.status_code == 201
        mock_table_client.upsert_entity.assert_called_once()

    @patch.dict('os.environ', {'AzureWebJobsStorage': 'DefaultEndpointsProtocol=https;AccountName=test'})
    @patch('functions.AddVendor.TableServiceClient')
    def test_add_vendor_table_error(self, mock_table_service):
        """Test handling of table storage errors."""
        mock_table_client = MagicMock()
        mock_table_client.upsert_entity.side_effect = Exception("Table storage error")
        mock_table_service.from_connection_string.return_value.get_table_client.return_value = mock_table_client

        req_body = {
            "vendor_domain": "test.com",
            "vendor_name": "Test Corp",
            "expense_dept": "IT",
            "gl_code": "6100",
            "allocation_schedule": "MONTHLY",
            "billing_party": "ACME Corp"
        }
        req = func.HttpRequest(
            method='POST',
            url='/api/AddVendor',
            body=json.dumps(req_body).encode('utf-8')
        )

        response = main(req)

        assert response.status_code == 500
        response_data = json.loads(response.get_body())
        assert 'error' in response_data

    @patch.dict('os.environ', {'AzureWebJobsStorage': 'DefaultEndpointsProtocol=https;AccountName=test'})
    @patch('functions.AddVendor.TableServiceClient')
    def test_add_vendor_domain_normalization(self, mock_table_service):
        """Test domain normalization with various formats."""
        mock_table_client = MagicMock()
        mock_table_service.from_connection_string.return_value.get_table_client.return_value = mock_table_client

        test_cases = [
            ("Adobe.Com", "adobe_com"),
            ("TEST.CORP.COM", "test_corp_com"),
            ("simple.co", "simple_co"),
        ]

        for domain, expected_rowkey in test_cases:
            req_body = {
                "vendor_domain": domain,
                "vendor_name": "Test Vendor",
                "expense_dept": "IT",
                "gl_code": "6100",
                "allocation_schedule": "MONTHLY",
                "billing_party": "ACME Corp"
            }
            req = func.HttpRequest(
                method='POST',
                url='/api/AddVendor',
                body=json.dumps(req_body).encode('utf-8')
            )

            response = main(req)

            assert response.status_code == 201
            call_args = mock_table_client.upsert_entity.call_args[0][0]
            assert call_args['RowKey'] == expected_rowkey

    def test_add_vendor_invalid_json(self):
        """Test handling of invalid JSON in request body."""
        req = func.HttpRequest(
            method='POST',
            url='/api/AddVendor',
            body=b'invalid json{'
        )

        response = main(req)

        assert response.status_code == 500
        response_data = json.loads(response.get_body())
        assert 'error' in response_data
