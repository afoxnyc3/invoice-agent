"""
Integration tests for vendor management via AddVendor HTTP endpoint.

Tests vendor creation, updates, validation, and error handling
through the HTTP API.
"""

import pytest
import json
from unittest.mock import MagicMock

from AddVendor import main as add_vendor_main


@pytest.mark.integration
def test_add_new_vendor_success(
    storage_helper,
    test_tables,
    mock_environment,
):
    """
    Test successfully adding a new vendor via HTTP POST.

    Validates vendor is created in VendorMaster table with correct fields.
    """
    # Prepare HTTP request
    vendor_data = {
        "vendor_domain": "newvendor.com",
        "vendor_name": "New Vendor Inc",
        "expense_dept": "SALES",
        "allocation_schedule": "ANNUAL",
        "gl_code": "7200",
        "billing_party": "Sales Division",
    }

    mock_req = MagicMock()
    mock_req.get_json.return_value = vendor_data

    # Call AddVendor function
    response = add_vendor_main(mock_req)

    # Validate response
    assert response.status_code == 201
    response_data = json.loads(response.get_body())
    assert response_data["status"] == "success"
    assert response_data["vendor"] == "New Vendor Inc"

    # Validate vendor in table
    entity = storage_helper.get_entity("VendorMaster", "Vendor", "newvendor_com")
    assert entity is not None
    assert entity["VendorName"] == "New Vendor Inc"
    assert entity["ExpenseDept"] == "SALES"
    assert entity["GLCode"] == "7200"
    assert entity["AllocationScheduleNumber"] == "ANNUAL"
    assert entity["BillingParty"] == "Sales Division"
    assert entity["Active"] is True
    assert "UpdatedAt" in entity


@pytest.mark.integration
def test_update_existing_vendor(
    storage_helper,
    test_tables,
    sample_vendors,
    mock_environment,
):
    """
    Test updating an existing vendor via HTTP POST (upsert).

    Validates vendor fields are updated correctly.
    """
    # Update Adobe's GL code
    vendor_data = {
        "vendor_domain": "adobe.com",
        "vendor_name": "Adobe Inc (Updated)",
        "expense_dept": "IT",
        "allocation_schedule": "QUARTERLY",
        "gl_code": "6150",  # Changed from 6100
        "billing_party": "Company HQ",
    }

    mock_req = MagicMock()
    mock_req.get_json.return_value = vendor_data

    # Call AddVendor function
    response = add_vendor_main(mock_req)

    # Validate response
    assert response.status_code == 201
    response_data = json.loads(response.get_body())
    assert response_data["status"] == "success"

    # Validate updated vendor in table
    entity = storage_helper.get_entity("VendorMaster", "Vendor", "adobe_com")
    assert entity is not None
    assert entity["VendorName"] == "Adobe Inc (Updated)"
    assert entity["GLCode"] == "6150"  # Updated
    assert entity["AllocationScheduleNumber"] == "QUARTERLY"  # Updated


@pytest.mark.integration
def test_add_vendor_missing_required_fields(
    storage_helper,
    test_tables,
    mock_environment,
):
    """
    Test validation error when required fields are missing.

    Expected: 400 Bad Request with validation error details.
    """
    # Missing gl_code and vendor_name
    vendor_data = {
        "vendor_domain": "incomplete.com",
        "expense_dept": "IT",
        "allocation_schedule": "MONTHLY",
        "billing_party": "Company HQ",
    }

    mock_req = MagicMock()
    mock_req.get_json.return_value = vendor_data

    # Call AddVendor function
    response = add_vendor_main(mock_req)

    # Validate error response
    assert response.status_code == 400
    response_data = json.loads(response.get_body())
    assert response_data["error"] == "Validation failed"
    assert "details" in response_data
    assert len(response_data["details"]) > 0


@pytest.mark.integration
def test_add_vendor_invalid_gl_code(
    storage_helper,
    test_tables,
    mock_environment,
):
    """
    Test validation error when GL code is not 4 digits.

    Expected: 400 Bad Request with GL code validation error.
    """
    # GL code is not 4 digits
    vendor_data = {
        "vendor_domain": "badgl.com",
        "vendor_name": "Bad GL Vendor",
        "expense_dept": "IT",
        "allocation_schedule": "MONTHLY",
        "gl_code": "123",  # Invalid: only 3 digits
        "billing_party": "Company HQ",
    }

    mock_req = MagicMock()
    mock_req.get_json.return_value = vendor_data

    # Call AddVendor function
    response = add_vendor_main(mock_req)

    # Validate error response
    assert response.status_code == 400
    response_data = json.loads(response.get_body())
    assert response_data["error"] == "Validation failed"

    # Check GL code not in table
    entity = storage_helper.get_entity("VendorMaster", "Vendor", "badgl_com")
    assert entity is None


@pytest.mark.integration
def test_add_vendor_non_numeric_gl_code(
    storage_helper,
    test_tables,
    mock_environment,
):
    """
    Test validation error when GL code contains non-numeric characters.

    Expected: 400 Bad Request with validation error.
    """
    vendor_data = {
        "vendor_domain": "alpha.com",
        "vendor_name": "Alpha Vendor",
        "expense_dept": "IT",
        "allocation_schedule": "MONTHLY",
        "gl_code": "ABCD",  # Invalid: not numeric
        "billing_party": "Company HQ",
    }

    mock_req = MagicMock()
    mock_req.get_json.return_value = vendor_data

    # Call AddVendor function
    response = add_vendor_main(mock_req)

    # Validate error response
    assert response.status_code == 400


@pytest.mark.integration
def test_add_vendor_domain_normalization(
    storage_helper,
    test_tables,
    mock_environment,
):
    """
    Test vendor domain is normalized to lowercase with underscores.

    Validates: example.com → example_com
    """
    vendor_data = {
        "vendor_domain": "Example.COM",  # Mixed case with dots
        "vendor_name": "Example Vendor",
        "expense_dept": "IT",
        "allocation_schedule": "MONTHLY",
        "gl_code": "6500",
        "billing_party": "Company HQ",
    }

    mock_req = MagicMock()
    mock_req.get_json.return_value = vendor_data

    # Call AddVendor function
    response = add_vendor_main(mock_req)

    # Validate response
    assert response.status_code == 201

    # Validate normalized RowKey
    entity = storage_helper.get_entity("VendorMaster", "Vendor", "example_com")
    assert entity is not None
    assert entity["VendorName"] == "Example Vendor"


@pytest.mark.integration
def test_add_multiple_vendors_batch(
    storage_helper,
    test_tables,
    mock_environment,
):
    """
    Test adding multiple vendors in sequence.

    Validates batch vendor registration workflow.
    """
    vendors = [
        {
            "vendor_domain": "vendor1.com",
            "vendor_name": "Vendor One",
            "expense_dept": "IT",
            "allocation_schedule": "MONTHLY",
            "gl_code": "6001",
            "billing_party": "Company HQ",
        },
        {
            "vendor_domain": "vendor2.com",
            "vendor_name": "Vendor Two",
            "expense_dept": "SALES",
            "allocation_schedule": "ANNUAL",
            "gl_code": "7001",
            "billing_party": "Sales Division",
        },
        {
            "vendor_domain": "vendor3.com",
            "vendor_name": "Vendor Three",
            "expense_dept": "HR",
            "allocation_schedule": "MONTHLY",
            "gl_code": "8001",
            "billing_party": "HR Department",
        },
    ]

    success_count = 0
    for vendor_data in vendors:
        mock_req = MagicMock()
        mock_req.get_json.return_value = vendor_data

        response = add_vendor_main(mock_req)
        if response.status_code == 201:
            success_count += 1

    # Validate all vendors added
    assert success_count == len(vendors)

    # Validate all in table
    entity1 = storage_helper.get_entity("VendorMaster", "Vendor", "vendor1_com")
    entity2 = storage_helper.get_entity("VendorMaster", "Vendor", "vendor2_com")
    entity3 = storage_helper.get_entity("VendorMaster", "Vendor", "vendor3_com")

    assert entity1 is not None
    assert entity2 is not None
    assert entity3 is not None


@pytest.mark.integration
def test_add_vendor_malformed_json(
    storage_helper,
    test_tables,
    mock_environment,
):
    """
    Test error handling when request contains malformed JSON.

    Expected: 500 Internal Server Error (handled gracefully).
    """
    mock_req = MagicMock()
    mock_req.get_json.side_effect = ValueError("Invalid JSON")

    # Call AddVendor function
    response = add_vendor_main(mock_req)

    # Validate error response
    assert response.status_code == 500
    response_data = json.loads(response.get_body())
    assert "error" in response_data


@pytest.mark.integration
def test_query_vendors_by_department(
    storage_helper,
    test_tables,
    sample_vendors,
):
    """
    Test querying vendors by department.

    Validates table query functionality for vendor management.
    """
    # Query all IT vendors
    filter_query = "ExpenseDept eq 'IT'"
    it_vendors = storage_helper.query_entities("VendorMaster", filter_query)
    it_vendor_list = list(it_vendors)

    # Should have at least 3 IT vendors from sample data
    assert len(it_vendor_list) >= 3

    # Validate all are IT department
    for vendor in it_vendor_list:
        assert vendor["ExpenseDept"] == "IT"


@pytest.mark.integration
def test_vendor_active_flag(
    storage_helper,
    test_tables,
    mock_environment,
):
    """
    Test vendor Active flag for soft delete functionality.

    Validates vendors can be marked inactive without deletion.
    """
    # Add vendor
    vendor_data = {
        "vendor_domain": "temporary.com",
        "vendor_name": "Temporary Vendor",
        "expense_dept": "IT",
        "allocation_schedule": "MONTHLY",
        "gl_code": "6999",
        "billing_party": "Company HQ",
    }

    mock_req = MagicMock()
    mock_req.get_json.return_value = vendor_data
    response = add_vendor_main(mock_req)
    assert response.status_code == 201

    # Verify vendor active
    entity = storage_helper.get_entity("VendorMaster", "Vendor", "temporary_com")
    assert entity["Active"] is True

    # Manually mark inactive (simulates deactivation workflow)
    entity["Active"] = False
    storage_helper.insert_entity("VendorMaster", entity)

    # Verify updated
    updated_entity = storage_helper.get_entity("VendorMaster", "Vendor", "temporary_com")
    assert updated_entity["Active"] is False
    assert updated_entity["VendorName"] == "Temporary Vendor"  # Still exists
