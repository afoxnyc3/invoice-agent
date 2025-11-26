#!/usr/bin/env python3
"""
Seed script for VendorMaster table
Populates initial vendor data for invoice processing
"""

import os
import sys
import csv
from datetime import datetime
from azure.data.tables import TableServiceClient, TableEntity
from azure.core.exceptions import ResourceExistsError


def get_table_client(connection_string: str, table_name: str):
    """Get Table Storage client."""
    service_client = TableServiceClient.from_connection_string(connection_string)
    return service_client.get_table_client(table_name)


def create_vendor_entity(vendor_data: dict) -> TableEntity:
    """Create a vendor entity for Table Storage."""
    # Clean vendor name for row key (lowercase, replace spaces with underscores)
    row_key = vendor_data["vendor_name"].lower().replace(" ", "_").replace("-", "_")

    return {
        "PartitionKey": "Vendor",
        "RowKey": row_key,
        "VendorName": vendor_data["vendor_name"],
        "ProductCategory": vendor_data.get("product_category", "Direct"),
        "ExpenseDept": vendor_data["expense_dept"],
        "AllocationSchedule": vendor_data["allocation_schedule"],
        "GLCode": vendor_data["gl_code"],
        "VenueRequired": vendor_data.get("venue_required", False),
        "Active": True,
        "UpdatedAt": datetime.utcnow().isoformat(),
    }


def seed_vendors_from_csv(csv_path: str, connection_string: str):
    """Load vendors from CSV file into Table Storage."""
    service_client = TableServiceClient.from_connection_string(connection_string)

    # Create table if it doesn't exist
    try:
        table_client = service_client.create_table_if_not_exists("VendorMaster")
        print("✅ VendorMaster table created or already exists")
    except Exception as e:
        print(f"⚠️ Table creation: {e}")
        table_client = service_client.get_table_client("VendorMaster")

    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        vendors_added = 0
        vendors_skipped = 0

        for row in reader:
            vendor_entity = create_vendor_entity(row)

            try:
                table_client.create_entity(vendor_entity)
                vendors_added += 1
                print(f"✅ Added vendor: {row['vendor_name']}")
            except ResourceExistsError:
                vendors_skipped += 1
                print(f"⚠️ Vendor already exists: {row['vendor_name']}")
            except Exception as e:
                print(f"❌ Error adding vendor {row['vendor_name']}: {e}")

    print(f"\nSummary: {vendors_added} vendors added, {vendors_skipped} skipped")


def create_default_vendors():
    """Create default vendor data if CSV doesn't exist."""
    default_vendors = [
        {
            "vendor_name": "Amazon Web Services",
            "expense_dept": "Cloud",
            "allocation_schedule": "14",
            "gl_code": "7110",
            "product_category": "Direct",
            "venue_required": False,
        },
        {
            "vendor_name": "Amazon Business",
            "expense_dept": "Hardware - Operations",
            "allocation_schedule": "NA",
            "gl_code": "6215",
            "product_category": "Direct",
            "venue_required": True,
        },
        {
            "vendor_name": "Microsoft",
            "expense_dept": "M365 Suite",
            "allocation_schedule": "3",
            "gl_code": "7112",
            "product_category": "Direct",
            "venue_required": False,
        },
        {
            "vendor_name": "FRSecure",
            "expense_dept": "CyberSecurity",
            "allocation_schedule": "1",
            "gl_code": "7112",
            "product_category": "Direct",
            "venue_required": False,
        },
        {
            "vendor_name": "Mimecast",
            "expense_dept": "CyberSecurity",
            "allocation_schedule": "1",
            "gl_code": "7112",
            "product_category": "Direct",
            "venue_required": False,
        },
        {
            "vendor_name": "1Password",
            "expense_dept": "CyberSecurity",
            "allocation_schedule": "1",
            "gl_code": "7112",
            "product_category": "Direct",
            "venue_required": False,
        },
        {
            "vendor_name": "EasyDmarc",
            "expense_dept": "CyberSecurity",
            "allocation_schedule": "1",
            "gl_code": "7112",
            "product_category": "Direct",
            "venue_required": False,
        },
        {
            "vendor_name": "Autocad",
            "expense_dept": "Software - Facilities",
            "allocation_schedule": "1",
            "gl_code": "7112",
            "product_category": "Direct",
            "venue_required": False,
        },
        {
            "vendor_name": "Dell",
            "expense_dept": "Hardware - Operations",
            "allocation_schedule": "NA",
            "gl_code": "6215",
            "product_category": "Direct",
            "venue_required": True,
        },
    ]

    # Create CSV file
    csv_path = "infrastructure/data/vendors.csv"
    os.makedirs("infrastructure/data", exist_ok=True)

    with open(csv_path, "w", newline="") as f:
        fieldnames = [
            "vendor_name",
            "expense_dept",
            "allocation_schedule",
            "gl_code",
            "product_category",
            "venue_required",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(default_vendors)

    print(f"Created default vendor CSV at {csv_path}")
    return csv_path


def seed_vendors_directly(vendors_list: list, connection_string: str):
    """Seed vendors directly without CSV file."""
    service_client = TableServiceClient.from_connection_string(connection_string)

    # Create table if it doesn't exist
    try:
        table_client = service_client.create_table_if_not_exists("VendorMaster")
        print("✅ VendorMaster table created or already exists")
    except Exception as e:
        print(f"⚠️ Table creation: {e}")
        table_client = service_client.get_table_client("VendorMaster")

    vendors_added = 0
    vendors_skipped = 0

    for vendor_data in vendors_list:
        vendor_entity = create_vendor_entity(vendor_data)

        try:
            table_client.create_entity(vendor_entity)
            vendors_added += 1
            print(f"✅ Added vendor: {vendor_data['vendor_name']}")
        except ResourceExistsError:
            vendors_skipped += 1
            print(f"⚠️ Vendor already exists: {vendor_data['vendor_name']}")
        except Exception as e:
            print(f"❌ Error adding vendor {vendor_data['vendor_name']}: {e}")

    print(f"\nSummary: {vendors_added} vendors added, {vendors_skipped} skipped")
    return table_client


def main():
    """Main execution function."""
    # Get connection string from environment or command line
    if len(sys.argv) > 1:
        connection_string = sys.argv[1]
    else:
        connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        if not connection_string:
            print("❌ Error: No connection string provided")
            print("Usage: python seed_vendors.py <connection_string>")
            print("Or set AZURE_STORAGE_CONNECTION_STRING environment variable")
            sys.exit(1)

    # MVP vendors (9 vendors)
    mvp_vendors = [
        {
            "vendor_name": "Amazon Web Services",
            "expense_dept": "Cloud",
            "allocation_schedule": "14",
            "gl_code": "7110",
            "product_category": "Direct",
            "venue_required": False,
        },
        {
            "vendor_name": "Amazon Business",
            "expense_dept": "Hardware - Operations",
            "allocation_schedule": "NA",
            "gl_code": "6215",
            "product_category": "Direct",
            "venue_required": True,
        },
        {
            "vendor_name": "Microsoft",
            "expense_dept": "M365 Suite",
            "allocation_schedule": "3",
            "gl_code": "7112",
            "product_category": "Direct",
            "venue_required": False,
        },
        {
            "vendor_name": "FRSecure",
            "expense_dept": "CyberSecurity",
            "allocation_schedule": "1",
            "gl_code": "7112",
            "product_category": "Direct",
            "venue_required": False,
        },
        {
            "vendor_name": "Mimecast",
            "expense_dept": "CyberSecurity",
            "allocation_schedule": "1",
            "gl_code": "7112",
            "product_category": "Direct",
            "venue_required": False,
        },
        {
            "vendor_name": "1Password",
            "expense_dept": "CyberSecurity",
            "allocation_schedule": "1",
            "gl_code": "7112",
            "product_category": "Direct",
            "venue_required": False,
        },
        {
            "vendor_name": "EasyDmarc",
            "expense_dept": "CyberSecurity",
            "allocation_schedule": "1",
            "gl_code": "7112",
            "product_category": "Direct",
            "venue_required": False,
        },
        {
            "vendor_name": "Autocad",
            "expense_dept": "Software - Facilities",
            "allocation_schedule": "1",
            "gl_code": "7112",
            "product_category": "Direct",
            "venue_required": False,
        },
        {
            "vendor_name": "Dell",
            "expense_dept": "Hardware - Operations",
            "allocation_schedule": "NA",
            "gl_code": "6215",
            "product_category": "Direct",
            "venue_required": True,
        },
    ]

    # Seed vendors
    print(f"Seeding {len(mvp_vendors)} MVP vendors...")
    table_client = seed_vendors_directly(mvp_vendors, connection_string)

    # Verify seeding
    try:
        vendors = list(table_client.query_entities("PartitionKey eq 'Vendor' and Active eq true"))
        print(f"\n✅ Total vendors in table: {len(vendors)}")

        # Display all vendors
        print("\nAll seeded vendors:")
        for vendor in vendors:
            venue_str = " (Venue Required)" if vendor.get("VenueRequired") else ""
            print(
                f"  - {vendor['VendorName']:<30} | Dept: {vendor['ExpenseDept']:<25} | GL: {vendor['GLCode']} | Sched: {vendor['AllocationSchedule']:<2}{venue_str}"
            )
    except Exception as e:
        print(f"⚠️ Error verifying vendors: {e}")


if __name__ == "__main__":
    main()
