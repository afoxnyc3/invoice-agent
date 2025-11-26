# Vendor Management Guide

## Overview

The Invoice Agent processes invoices by matching sender email domains to vendors in the **VendorMaster** table. This guide covers all aspects of vendor data management, including seeding, updates, validation, and troubleshooting.

## Current Vendor Count

- **Total Vendors:** 25
- **Last Updated:** November 12, 2025
- **Storage:** Azure Table Storage - `VendorMaster` table
- **Location:** `stinvoiceagentdev` storage account (dev), `stinvoiceagentprod` (prod)

## Quick Reference: All Vendors

| # | Vendor Name | Email Domain | GL Code | Department | Billing Party | Schedule |
|---|---|---|---|---|---|---|
| 1 | Adobe Inc | adobe.com | 6100 | IT | Company HQ | MONTHLY |
| 2 | ADP | adp.com | 6610 | HR | Company HQ | MONTHLY |
| 3 | Amazon Business | amazon.com | 6710 | OPERATIONS | Company HQ | MONTHLY |
| 4 | AT&T | att.com | 6140 | IT | Company Branch | MONTHLY |
| 5 | Amazon Web Services | aws.amazon.com | 6110 | IT | Company HQ | MONTHLY |
| 6 | DocuSign | docusign.com | 6500 | LEGAL | Company HQ | ANNUAL |
| 7 | Dropbox | dropbox.com | 6130 | IT | Company HQ | ANNUAL |
| 8 | FedEx | fedex.com | 6700 | OPERATIONS | Company HQ | MONTHLY |
| 9 | Google Workspace | google.com | 6100 | IT | Company Branch | MONTHLY |
| 10 | Grainger | grainger.com | 6800 | FACILITIES | Company HQ | MONTHLY |
| 11 | Home Depot | homedepot.com | 6810 | FACILITIES | Company HQ | MONTHLY |
| 12 | HubSpot | hubspot.com | 6300 | MARKETING | Company HQ | MONTHLY |
| 13 | Indeed | indeed.com | 6620 | HR | Company HQ | MONTHLY |
| 14 | QuickBooks | intuit.com | 6400 | FINANCE | Company HQ | ANNUAL |
| 15 | LinkedIn | linkedin.com | 6620 | HR | Company HQ | ANNUAL |
| 16 | Microsoft Corporation | microsoft.com | 6100 | IT | Company HQ | ANNUAL |
| 17 | Oracle | oracle.com | 6110 | IT | Company HQ | ANNUAL |
| 18 | Salesforce | salesforce.com | 6200 | SALES | Company HQ | ANNUAL |
| 19 | ServiceNow | servicenow.com | 6150 | IT | Company HQ | ANNUAL |
| 20 | Slack Technologies | slack.com | 6120 | IT | Company HQ | MONTHLY |
| 21 | Staples | staples.com | 6710 | OPERATIONS | Company HQ | MONTHLY |
| 22 | UPS | ups.com | 6700 | OPERATIONS | Company HQ | MONTHLY |
| 23 | Verizon | verizon.com | 6140 | IT | Company HQ | MONTHLY |
| 24 | Workday | workday.com | 6600 | HR | Company HQ | ANNUAL |
| 25 | Zoom Video Communications | zoom.us | 6120 | IT | Company HQ | MONTHLY |

---

## Initial Setup

### Prerequisites
- Azure CLI installed and authenticated
- Storage account created (`stinvoiceagentdev` or `stinvoiceagentprod`)
- `VendorMaster` table created
- Python 3.11+ with `azure-data-tables` installed

### Step 1: Prepare Vendor CSV File

Create `infrastructure/data/vendors.csv` with the following structure:

```csv
vendor_name,email_domain,expense_dept,allocation_schedule,gl_code,billing_party,notes
Adobe Inc,adobe.com,IT,MONTHLY,6100,Company HQ,Creative Cloud subscriptions
```

**Required Fields:**
- `vendor_name`: Display name of the vendor
- `email_domain`: Email domain (matches invoice sender domain)
- `expense_dept`: Valid values: IT, SALES, HR, FINANCE, LEGAL, MARKETING, OPERATIONS, FACILITIES
- `allocation_schedule`: Valid values: MONTHLY, ANNUAL, QUARTERLY, WEEKLY
- `gl_code`: Exactly 4 digits (e.g., 6100)
- `billing_party`: Entity responsible for payment
- `notes`: Optional description

### Step 2: Create VendorMaster Table

```bash
# Get connection string
STORAGE_ACCOUNT="stinvoiceagentdev"
CONNECTION_STRING=$(az storage account show-connection-string \
  --name $STORAGE_ACCOUNT \
  --resource-group rg-invoice-agent-dev \
  --query connectionString -o tsv)

# Create table
az storage table create \
  --name VendorMaster \
  --connection-string "$CONNECTION_STRING"
```

### Step 3: Seed Initial Vendors

```bash
# Run seed script
cd src
python3 ../infrastructure/scripts/seed_vendors.py "$CONNECTION_STRING"
```

**Expected Output:**
```
✅ Added vendor: Adobe Inc
✅ Added vendor: Microsoft Corporation
...
✅ Total vendors in table: 25
```

---

## Adding New Vendors

### Method 1: Manual Entry (Single Vendor)

```python
#!/usr/bin/env python3
"""Add a single vendor"""

from azure.data.tables import TableServiceClient
from datetime import datetime

connection_string = "your-connection-string"
table_client = TableServiceClient.from_connection_string(
    connection_string
).get_table_client('VendorMaster')

# Prepare vendor data
vendor = {
    'PartitionKey': 'Vendor',
    'RowKey': 'new-vendor_com',  # lowercase, no dots/spaces
    'VendorName': 'New Vendor Inc',
    'ExpenseDept': 'IT',
    'AllocationScheduleNumber': 'MONTHLY',
    'GLCode': '6100',
    'BillingParty': 'Company HQ',
    'Active': True,
    'UpdatedAt': datetime.utcnow().isoformat(),
    'Notes': 'New vendor added'
}

# Insert vendor
table_client.create_entity(vendor)
print(f"✅ Added: {vendor['VendorName']}")
```

### Method 2: Batch Update (Multiple Vendors)

1. Add new vendors to `infrastructure/data/vendors.csv`
2. Run the seed script again (it skips duplicates):

```bash
python3 infrastructure/scripts/seed_vendors.py "$CONNECTION_STRING"
```

### Method 3: Using Azure Portal

1. Go to Storage Account → Tables → VendorMaster
2. Click "Add Entity"
3. Fill in fields:
   - PartitionKey: `Vendor`
   - RowKey: `vendor-domain_com` (lowercase, underscores)
   - Other properties: Use Add Property button

---

## Updating Existing Vendors

### Update via Python

```python
#!/usr/bin/env python3
"""Update an existing vendor"""

from azure.data.tables import TableServiceClient
from datetime import datetime

connection_string = "your-connection-string"
table_client = TableServiceClient.from_connection_string(
    connection_string
).get_table_client('VendorMaster')

# Get existing vendor
vendor = table_client.get_entity(
    partition_key='Vendor',
    row_key='adobe_com'
)

# Update fields
vendor['GLCode'] = '6105'  # New GL code
vendor['ExpenseDept'] = 'MARKETING'  # New department
vendor['UpdatedAt'] = datetime.utcnow().isoformat()

# Save changes
table_client.update_entity(vendor, mode='REPLACE')
print(f"✅ Updated: {vendor['VendorName']}")
```

### Update via Azure Portal

1. Go to Storage Account → Tables → VendorMaster
2. Find vendor by RowKey (domain)
3. Click Edit
4. Modify fields
5. Click Update

---

## Querying Vendors

### List All Vendors

```python
from azure.data.tables import TableServiceClient

connection_string = "your-connection-string"
table_client = TableServiceClient.from_connection_string(
    connection_string
).get_table_client('VendorMaster')

# Get all vendors
vendors = list(table_client.query_entities("PartitionKey eq 'Vendor'"))
print(f"Total vendors: {len(vendors)}")

for vendor in vendors:
    print(f"  - {vendor['VendorName']} ({vendor['RowKey']})")
```

### Search by Domain

```python
# Get specific vendor
vendor = table_client.get_entity(
    partition_key='Vendor',
    row_key='adobe_com'
)
print(f"Vendor: {vendor['VendorName']}")
print(f"GL Code: {vendor['GLCode']}")
```

### Filter by Department

```python
# Get all IT vendors
it_vendors = table_client.query_entities(
    "PartitionKey eq 'Vendor' and ExpenseDept eq 'IT'"
)
for vendor in it_vendors:
    print(f"  - {vendor['VendorName']}")
```

### Filter by Active Status

```python
# Get active vendors only
active_vendors = table_client.query_entities(
    "PartitionKey eq 'Vendor' and Active eq true"
)
```

---

## Validation Rules

### Email Domain (RowKey)
- **Format:** Lowercase with underscores replacing dots
- **Example:** `adobe.com` → `adobe_com`
- **Validation:**
  ```
  ✅ adobe_com
  ✅ aws_amazon_com
  ❌ Adobe.com (not lowercase)
  ❌ adobe.com (dots not replaced)
  ❌ adobe com (spaces not allowed)
  ```

### GL Code
- **Format:** Exactly 4 digits
- **Validation:**
  ```
  ✅ 6100
  ✅ 6710
  ❌ 61 (too short)
  ❌ 61000 (too long)
  ❌ 610A (contains letters)
  ```

### Expense Department
- **Valid Values:**
  - `IT` - Information Technology
  - `SALES` - Sales Department
  - `HR` - Human Resources
  - `FINANCE` - Finance Department
  - `LEGAL` - Legal Department
  - `MARKETING` - Marketing Department
  - `OPERATIONS` - Operations
  - `FACILITIES` - Facilities Management

### Allocation Schedule
- **Valid Values:**
  - `MONTHLY` - Billed monthly
  - `ANNUAL` - Billed annually
  - `QUARTERLY` - Billed quarterly
  - `WEEKLY` - Billed weekly

### Billing Party
- **Valid Values:** Any text (typically company entity names)
- **Examples:**
  - `Company HQ`
  - `Company Branch`
  - `Chelsea Piers NY`
  - `Chelsea Piers CT`

---

## Deactivating Vendors

Instead of deleting, set the `Active` flag to `false`:

```python
vendor = table_client.get_entity('Vendor', 'old-vendor_com')
vendor['Active'] = False
vendor['UpdatedAt'] = datetime.utcnow().isoformat()
table_client.update_entity(vendor, mode='REPLACE')
print(f"❌ Deactivated: {vendor['VendorName']}")
```

**Note:** ExtractEnrich ignores `Active` flag; you'll need to update the function if you want to enforce this.

---

## Vendor Matching Logic

### How Email Domains Are Normalized

The system extracts the domain from invoice sender email and normalizes it:

```python
def extract_domain(email: str) -> str:
    """Extract and normalize domain from email"""
    domain = email.split('@')[1].lower()  # Get domain and lowercase
    domain = domain.replace('.', '_')      # Replace dots with underscores
    domain = domain.replace(' ', '_')      # Replace spaces with underscores
    return domain

# Examples:
extract_domain("invoice@adobe.com")        # → "adobe_com"
extract_domain("BILLING@MICROSOFT.COM")    # → "microsoft_com"
extract_domain("support@aws.amazon.com")   # → "aws_amazon_com"
```

### Unknown Vendor Handling

When an invoice arrives from an unknown vendor:

1. **Email extraction fails** - ExtractEnrich logs warning
2. **Vendor lookup fails** - No matching RowKey in VendorMaster
3. **Notification sent** - ExtractEnrich sends registration email to requestor
4. **Processing stops** - Invoice not routed to AP (must be manually registered first)

---

## Weekly Update Process

### 1. Review Unknown Vendors

Check logs for unknown vendor notifications:

```bash
# Query recent unknown vendor attempts
az monitor app-insights query \
  --app ai-invoice-agent-dev \
  --analytics-query "
    customEvents
    | where name == 'UnknownVendor'
    | summarize count() by tostring(customDimensions.vendor_domain)
    | order by count_ desc
  "
```

### 2. Gather Vendor Information

For each new vendor, collect:
- Email domain used in invoices
- Vendor display name
- Department/cost center
- GL code
- Billing party
- Invoice frequency (MONTHLY/ANNUAL/etc)

### 3. Add to Vendor Master

```bash
# Option A: Manual entry
python3 add_single_vendor.py

# Option B: Batch update
# 1. Add rows to infrastructure/data/vendors.csv
# 2. Run: python3 infrastructure/scripts/seed_vendors.py "$CONNECTION_STRING"
```

### 4. Validate Changes

```python
# Verify new vendors loaded
vendors = list(table_client.query_entities("PartitionKey eq 'Vendor'"))
print(f"Total vendors: {len(vendors)}")

# Test vendor lookup with test emails
test_emails = [
    "invoice@new-vendor.com",
    "billing@another-vendor.com"
]
for email in test_emails:
    domain = extract_domain(email)
    try:
        vendor = table_client.get_entity('Vendor', domain)
        print(f"✅ {email} → {vendor['VendorName']}")
    except:
        print(f"❌ {email} → Not found")
```

---

## Performance Tuning

### Vendor Lookup Performance
- **Current:** <10ms per lookup (Table Storage is very fast)
- **Optimization:** Vendors are looked up by PartitionKey + RowKey (best case)
- **Scaling:** Supports >10,000 vendors without performance degradation

### Query Performance
- ✅ Use: `PartitionKey eq 'Vendor'` (fast, partition scan)
- ✅ Use: `PartitionKey eq 'Vendor' and ExpenseDept eq 'IT'` (fast with index)
- ❌ Avoid: Complex filters without PartitionKey (full table scan)

---

## Troubleshooting

### Issue: "Unknown Vendor" Emails Keep Coming

**Cause:** Vendor hasn't been added to VendorMaster table

**Solution:**
1. Check email domain in unknown vendor notification
2. Normalize domain (lowercase, dots → underscores)
3. Add vendor to VendorMaster
4. Reprocess invoice

### Issue: Vendor Lookup Returns Wrong Entity

**Cause:** Duplicate entries or wrong RowKey format

**Solution:**
```python
# Find duplicates
vendors = list(table_client.query_entities(
    "PartitionKey eq 'Vendor' and RowKey eq 'adobe_com'"
))
print(f"Found {len(vendors)} entries")

# Delete duplicates and recreate
for vendor in vendors:
    table_client.delete_entity(vendor)
```

### Issue: Email Domain Not Matching

**Common Mistakes:**
- Using `adobe.com` instead of `adobe_com`
- Using uppercase: `Adobe_COM` instead of `adobe_com`
- Including spaces: `adobe _com` instead of `adobe_com`

**Correct Format:**
```
✅ adobe_com
✅ aws_amazon_com
✅ zoom_us
✅ intuit_com
```

### Issue: GL Code Validation Fails

**Valid Format:**
- Exactly 4 digits
- No letters or special characters
- Examples: `6100`, `6200`, `6710`

**Invalid Examples:**
- `610` (too short)
- `61000` (too long)
- `610A` (contains letter)
- `61-00` (contains hyphen)

---

## Reporting & Monitoring

### Vendor Statistics

```python
from azure.data.tables import TableServiceClient

def get_vendor_stats(connection_string: str):
    table_client = TableServiceClient.from_connection_string(
        connection_string
    ).get_table_client('VendorMaster')

    vendors = list(table_client.query_entities("PartitionKey eq 'Vendor'"))

    # Group by department
    by_dept = {}
    for vendor in vendors:
        dept = vendor.get('ExpenseDept', 'UNKNOWN')
        by_dept[dept] = by_dept.get(dept, 0) + 1

    # Group by billing party
    by_billing = {}
    for vendor in vendors:
        party = vendor.get('BillingParty', 'UNKNOWN')
        by_billing[party] = by_billing.get(party, 0) + 1

    print(f"Total Vendors: {len(vendors)}")
    print(f"\nBy Department:")
    for dept, count in sorted(by_dept.items()):
        print(f"  {dept}: {count}")
    print(f"\nBy Billing Party:")
    for party, count in sorted(by_billing.items()):
        print(f"  {party}: {count}")

# Run stats
get_vendor_stats("your-connection-string")
```

**Expected Output:**
```
Total Vendors: 25

By Department:
  FACILITIES: 2
  FINANCE: 1
  HR: 4
  IT: 11
  LEGAL: 1
  MARKETING: 1
  OPERATIONS: 3
  SALES: 1

By Billing Party:
  Company Branch: 2
  Company HQ: 23
```

---

## Disaster Recovery

### Backup Vendors

```bash
# Export all vendors to CSV
python3 << 'EOF'
from azure.data.tables import TableServiceClient
import csv

connection_string = "your-connection-string"
table_client = TableServiceClient.from_connection_string(
    connection_string
).get_table_client('VendorMaster')

vendors = list(table_client.query_entities("PartitionKey eq 'Vendor'"))

with open(f'vendors_backup_{datetime.now().isoformat()}.csv', 'w') as f:
    writer = csv.DictWriter(f, fieldnames=[
        'vendor_name', 'email_domain', 'expense_dept',
        'allocation_schedule', 'gl_code', 'billing_party'
    ])
    writer.writeheader()
    for vendor in vendors:
        writer.writerow({
            'vendor_name': vendor['VendorName'],
            'email_domain': vendor['RowKey'].replace('_', '.'),
            'expense_dept': vendor['ExpenseDept'],
            'allocation_schedule': vendor['AllocationScheduleNumber'],
            'gl_code': vendor['GLCode'],
            'billing_party': vendor['BillingParty']
        })
print(f"✅ Backed up {len(vendors)} vendors")
EOF
```

### Restore from Backup

```bash
# Run seed script with backup CSV
python3 infrastructure/scripts/seed_vendors.py "$CONNECTION_STRING"
```

---

## Related Documentation

- [Architecture](ARCHITECTURE.md) - System design and data flow
- [Infrastructure Setup](AZURE_SETUP.md) - Azure deployment guide
- [Function Specifications](SPEC.md) - Technical details
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues

---

**Last Updated:** November 12, 2025
**Owner:** Alex Fox, Invoice Agent Team
**Status:** Production Ready
