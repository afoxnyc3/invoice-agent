#!/usr/bin/env python3
"""List all vendors with their RowKeys"""

import os
from azure.data.tables import TableServiceClient

# Get connection string
conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
if not conn_str:
    print("Set AZURE_STORAGE_CONNECTION_STRING first")
    exit(1)

# Connect to table
service = TableServiceClient.from_connection_string(conn_str)
table = service.get_table_client("VendorMaster")

# List all vendors
print("All vendors in VendorMaster table:")
print("=" * 70)
print(f"{'RowKey':<30} | {'VendorName':<30}")
print("-" * 70)

vendors = table.query_entities("PartitionKey eq 'Vendor'")
for vendor in vendors:
    print(f"{vendor['RowKey']:<30} | {vendor['VendorName']:<30}")

print("=" * 70)
print("\nNote: RowKey is the normalized lookup key (lowercase, no spaces)")
