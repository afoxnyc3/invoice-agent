"""
Unit tests for AddVendor HTTP function.
"""

import json
from unittest.mock import Mock, patch, MagicMock
import azure.functions as func
from functions.AddVendor import main


class TestAddVendor:
    """Test suite for AddVendor function."""

    @patch.dict("os.environ", {"AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test"})
    @patch("functions.AddVendor.TableServiceClient")
    def test_add_vendor_success(self, mock_table_service):
        """Test successful vendor creation."""
        # Mock table client
        mock_table_client = MagicMock()
        mock_table_service.from_connection_string.return_value.get_table_client.return_value = mock_table_client

        # Create request with valid vendor data
        req_body = {
            "vendor_name": "Adobe",
            "expense_dept": "IT",
            "gl_code": "6100",
            "allocation_schedule": "1",
            "product_category": "Direct",
            "venue_required": False,
        }
        req = func.HttpRequest(method="POST", url="/api/AddVendor", body=json.dumps(req_body).encode("utf-8"))

        # Execute function
        response = main(req)

        # Assertions
        assert response.status_code == 201
        response_data = json.loads(response.get_body())
        assert response_data["status"] == "success"
        assert response_data["vendor"] == "Adobe"
        mock_table_client.create_entity.assert_called_once()

        # Verify vendor name normalization
        call_args = mock_table_client.create_entity.call_args[0][0]
        assert call_args["RowKey"] == "adobe"
        assert call_args["PartitionKey"] == "Vendor"
        assert call_args["VendorName"] == "Adobe"

    @patch("functions.AddVendor.TableServiceClient")
    def test_add_vendor_invalid_gl_code(self, mock_table_service):
        """Test validation fails with invalid GL code."""
        req_body = {
            "vendor_name": "Test Corp",
            "expense_dept": "IT",
            "gl_code": "123",  # Invalid: only 3 digits
            "allocation_schedule": "1",
            "product_category": "Direct",
        }
        req = func.HttpRequest(method="POST", url="/api/AddVendor", body=json.dumps(req_body).encode("utf-8"))

        response = main(req)

        assert response.status_code == 400
        response_data = json.loads(response.get_body())
        assert "error" in response_data

    @patch("functions.AddVendor.TableServiceClient")
    def test_add_vendor_missing_required_field(self, mock_table_service):
        """Test validation fails with missing required field."""
        req_body = {
            "vendor_name": "Test Corp",
            # Missing expense_dept
            "gl_code": "6100",
            "allocation_schedule": "1",
            "product_category": "Direct",
        }
        req = func.HttpRequest(method="POST", url="/api/AddVendor", body=json.dumps(req_body).encode("utf-8"))

        response = main(req)

        assert response.status_code == 400
        response_data = json.loads(response.get_body())
        assert "error" in response_data

    @patch.dict("os.environ", {"AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test"})
    @patch("functions.AddVendor.TableServiceClient")
    def test_add_vendor_duplicate_update(self, mock_table_service):
        """Test creating duplicate vendor (should fail with 400)."""
        mock_table_client = MagicMock()
        from azure.core.exceptions import ResourceExistsError

        mock_table_client.create_entity.side_effect = ResourceExistsError("Entity already exists")
        mock_table_service.from_connection_string.return_value.get_table_client.return_value = mock_table_client

        req_body = {
            "vendor_name": "Adobe",
            "expense_dept": "SALES",
            "gl_code": "6200",
            "allocation_schedule": "3",
            "product_category": "Direct",
        }
        req = func.HttpRequest(method="POST", url="/api/AddVendor", body=json.dumps(req_body).encode("utf-8"))

        response = main(req)

        assert response.status_code == 400

    @patch.dict("os.environ", {"AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test"})
    @patch("functions.AddVendor.TableServiceClient")
    def test_add_vendor_table_error(self, mock_table_service):
        """Test handling of table storage errors."""
        mock_table_client = MagicMock()
        mock_table_client.create_entity.side_effect = Exception("Table storage error")
        mock_table_service.from_connection_string.return_value.get_table_client.return_value = mock_table_client

        req_body = {
            "vendor_name": "Test Corp",
            "expense_dept": "IT",
            "gl_code": "6100",
            "allocation_schedule": "1",
            "product_category": "Direct",
        }
        req = func.HttpRequest(method="POST", url="/api/AddVendor", body=json.dumps(req_body).encode("utf-8"))

        response = main(req)

        assert response.status_code == 500
        response_data = json.loads(response.get_body())
        assert "error" in response_data

    @patch.dict("os.environ", {"AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test"})
    @patch("functions.AddVendor.TableServiceClient")
    def test_add_vendor_name_normalization(self, mock_table_service):
        """Test vendor name normalization with various formats."""
        mock_table_client = MagicMock()
        mock_table_service.from_connection_string.return_value.get_table_client.return_value = mock_table_client

        test_cases = [
            ("Adobe Inc", "adobe_inc"),
            ("Amazon Web Services", "amazon_web_services"),
            ("Test-Vendor Co", "test_vendor_co"),
        ]

        for vendor_name, expected_rowkey in test_cases:
            req_body = {
                "vendor_name": vendor_name,
                "expense_dept": "IT",
                "gl_code": "6100",
                "allocation_schedule": "1",
                "product_category": "Direct",
            }
            req = func.HttpRequest(method="POST", url="/api/AddVendor", body=json.dumps(req_body).encode("utf-8"))

            response = main(req)

            assert response.status_code == 201
            call_args = mock_table_client.create_entity.call_args[0][0]
            assert call_args["RowKey"] == expected_rowkey

    def test_add_vendor_invalid_json(self):
        """Test handling of invalid JSON in request body."""
        req = func.HttpRequest(method="POST", url="/api/AddVendor", body=b"invalid json{")

        response = main(req)

        assert response.status_code == 500
        response_data = json.loads(response.get_body())
        assert "error" in response_data
