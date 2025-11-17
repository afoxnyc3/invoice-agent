"""
AddVendor HTTP function - Register new vendors in VendorMaster table.
"""

import json
import os
import logging
from datetime import datetime
import azure.functions as func
from azure.data.tables import TableServiceClient
from azure.core.exceptions import ResourceExistsError
from pydantic import ValidationError
from shared.models import VendorMaster

logger = logging.getLogger(__name__)


def main(req: func.HttpRequest) -> func.HttpResponse:
    """Add vendor to VendorMaster table via HTTP POST."""
    try:
        data = req.get_json()
        # Normalize vendor name to RowKey format (lowercase, spaces/hyphens to underscores)
        vendor_name = data.get("vendor_name", "").strip()
        row_key = vendor_name.lower().replace(" ", "_").replace("-", "_")

        # Map snake_case API fields to PascalCase model fields
        vendor_data = {
            "RowKey": row_key,
            "VendorName": vendor_name,
            "ExpenseDept": data.get("expense_dept"),
            "AllocationSchedule": data.get("allocation_schedule"),
            "GLCode": data.get("gl_code"),
            "ProductCategory": data.get("product_category", "Direct"),
            "VenueRequired": data.get("venue_required", False),
            "UpdatedAt": datetime.utcnow().isoformat() + "Z",
        }
        vendor = VendorMaster(**vendor_data)

        table_client = TableServiceClient.from_connection_string(os.environ["AzureWebJobsStorage"]).get_table_client(
            "VendorMaster"
        )

        table_client.create_entity(vendor.model_dump())
        logger.info(f"Added vendor: {vendor.VendorName} ({vendor.RowKey})")
        return func.HttpResponse(
            json.dumps({"status": "success", "vendor": vendor.VendorName}),
            status_code=201,
        )
    except ValidationError as e:
        errors = [{"field": err["loc"][0] if err["loc"] else "unknown", "message": err["msg"]} for err in e.errors()]
        return func.HttpResponse(
            json.dumps({"error": "Validation failed", "details": errors}),
            status_code=400,
        )
    except ResourceExistsError as e:
        logger.warning(f"Vendor already exists: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": "Vendor already exists"}),
            status_code=400,
        )
    except Exception as e:
        logger.error(f"Failed to add vendor: {str(e)}")
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500)
