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
    # Clean vendor name for row key (lowercase, replace spaces/dots)
    row_key = vendor_data['email_domain'].lower().replace('.', '_').replace(' ', '_')

    return {
        'PartitionKey': 'Vendor',
        'RowKey': row_key,
        'VendorName': vendor_data['vendor_name'],
        'ExpenseDept': vendor_data['expense_dept'],
        'AllocationScheduleNumber': vendor_data['allocation_schedule'],
        'GLCode': vendor_data['gl_code'],
        'BillingParty': vendor_data['billing_party'],
        'Active': True,
        'UpdatedAt': datetime.utcnow().isoformat(),
        'Notes': vendor_data.get('notes', '')
    }


def seed_vendors_from_csv(csv_path: str, connection_string: str):
    """Load vendors from CSV file into Table Storage."""
    table_client = get_table_client(connection_string, 'VendorMaster')

    with open(csv_path, 'r') as f:
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
            'vendor_name': 'Adobe Inc',
            'email_domain': 'adobe.com',
            'expense_dept': 'IT',
            'allocation_schedule': 'MONTHLY',
            'gl_code': '6100',
            'billing_party': 'Chelsea Piers NY',
            'notes': 'Creative Cloud subscriptions'
        },
        {
            'vendor_name': 'Microsoft Corporation',
            'email_domain': 'microsoft.com',
            'expense_dept': 'IT',
            'allocation_schedule': 'ANNUAL',
            'gl_code': '6100',
            'billing_party': 'Chelsea Piers NY',
            'notes': 'Office 365, Azure services'
        },
        {
            'vendor_name': 'Amazon Web Services',
            'email_domain': 'aws.amazon.com',
            'expense_dept': 'IT',
            'allocation_schedule': 'MONTHLY',
            'gl_code': '6110',
            'billing_party': 'Chelsea Piers NY',
            'notes': 'Cloud infrastructure'
        },
        {
            'vendor_name': 'Salesforce',
            'email_domain': 'salesforce.com',
            'expense_dept': 'SALES',
            'allocation_schedule': 'ANNUAL',
            'gl_code': '6200',
            'billing_party': 'Chelsea Piers NY',
            'notes': 'CRM platform'
        },
        {
            'vendor_name': 'Zoom Video Communications',
            'email_domain': 'zoom.us',
            'expense_dept': 'IT',
            'allocation_schedule': 'MONTHLY',
            'gl_code': '6120',
            'billing_party': 'Chelsea Piers NY',
            'notes': 'Video conferencing'
        },
        {
            'vendor_name': 'Slack Technologies',
            'email_domain': 'slack.com',
            'expense_dept': 'IT',
            'allocation_schedule': 'MONTHLY',
            'gl_code': '6120',
            'billing_party': 'Chelsea Piers NY',
            'notes': 'Team collaboration'
        },
        {
            'vendor_name': 'Google Workspace',
            'email_domain': 'google.com',
            'expense_dept': 'IT',
            'allocation_schedule': 'MONTHLY',
            'gl_code': '6100',
            'billing_party': 'Chelsea Piers CT',
            'notes': 'Email and productivity suite'
        },
        {
            'vendor_name': 'Dropbox',
            'email_domain': 'dropbox.com',
            'expense_dept': 'IT',
            'allocation_schedule': 'ANNUAL',
            'gl_code': '6130',
            'billing_party': 'Chelsea Piers NY',
            'notes': 'File storage and sharing'
        },
        {
            'vendor_name': 'HubSpot',
            'email_domain': 'hubspot.com',
            'expense_dept': 'MARKETING',
            'allocation_schedule': 'MONTHLY',
            'gl_code': '6300',
            'billing_party': 'Chelsea Piers NY',
            'notes': 'Marketing automation'
        },
        {
            'vendor_name': 'QuickBooks',
            'email_domain': 'intuit.com',
            'expense_dept': 'FINANCE',
            'allocation_schedule': 'ANNUAL',
            'gl_code': '6400',
            'billing_party': 'Chelsea Piers NY',
            'notes': 'Accounting software'
        }
    ]

    # Create CSV file
    csv_path = 'data/vendors.csv'
    os.makedirs('data', exist_ok=True)

    with open(csv_path, 'w', newline='') as f:
        fieldnames = ['vendor_name', 'email_domain', 'expense_dept',
                     'allocation_schedule', 'gl_code', 'billing_party', 'notes']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(default_vendors)

    print(f"Created default vendor CSV at {csv_path}")
    return csv_path


def main():
    """Main execution function."""
    # Get connection string from environment or command line
    if len(sys.argv) > 1:
        connection_string = sys.argv[1]
    else:
        connection_string = os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
        if not connection_string:
            print("❌ Error: No connection string provided")
            print("Usage: python seed_vendors.py <connection_string>")
            print("Or set AZURE_STORAGE_CONNECTION_STRING environment variable")
            sys.exit(1)

    # Check for CSV file
    csv_path = 'data/vendors.csv'
    if not os.path.exists(csv_path):
        print("CSV file not found, creating default vendors...")
        csv_path = create_default_vendors()

    # Seed vendors
    print(f"Seeding vendors from {csv_path}...")
    seed_vendors_from_csv(csv_path, connection_string)

    # Verify seeding
    table_client = get_table_client(connection_string, 'VendorMaster')
    vendors = list(table_client.query_entities("PartitionKey eq 'Vendor'"))
    print(f"\n✅ Total vendors in table: {len(vendors)}")

    # Display sample vendors
    print("\nSample vendors:")
    for vendor in vendors[:5]:
        print(f"  - {vendor['VendorName']} ({vendor['RowKey']}) - GL: {vendor['GLCode']}")


if __name__ == "__main__":
    main()