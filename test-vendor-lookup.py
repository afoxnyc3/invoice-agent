#!/usr/bin/env python3
"""Test vendor lookup functionality"""

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

# Test vendor lookups
test_vendors = ["microsoft", "aws", "amazon web services", "dell"]

print("Testing vendor lookups:")
print("=" * 50)

for vendor in test_vendors:
    normalized = vendor.lower().replace(" ", "")
    try:
        entity = table.get_entity("Vendor", normalized)
        print(f"✅ Found '{vendor}' -> {entity['VendorName']}")
        print(f"   GL Code: {entity['GLCode']}")
        print(f"   Dept: {entity['ExpenseDept']}")
        print(f"   Schedule: {entity['AllocationSchedule']}")
        print()
    except:
        print(f"❌ Not found: '{vendor}' (normalized: {normalized})")
        print()
