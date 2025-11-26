#!/bin/bash
# Easy vendor seeding script for Invoice Agent

echo "🌱 Seeding VendorMaster Table..."
echo "================================"

# Get connection string from Azure
echo "📡 Retrieving storage connection string..."
CONNECTION_STRING=$(az storage account show-connection-string \
  --name stinvoiceagentprod \
  --resource-group rg-invoice-agent-prod \
  --query connectionString -o tsv)

if [ -z "$CONNECTION_STRING" ]; then
  echo "❌ Error: Could not retrieve connection string"
  echo "Make sure you're logged into Azure: az login"
  exit 1
fi

echo "✅ Connection string retrieved"

# Run the seeding script
echo "🚀 Running vendor seeding..."
cd infrastructure/scripts

export AZURE_STORAGE_CONNECTION_STRING="$CONNECTION_STRING"
python seed_vendors.py

echo ""
echo "✅ Vendor seeding complete!"