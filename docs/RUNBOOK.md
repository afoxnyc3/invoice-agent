# Invoice Agent Testing Runbook

**Version:** 1.0.0
**Last Updated:** 2025-11-19
**Owner:** DevOps Team

## Table of Contents

- [Prerequisites](#prerequisites)
- [Environment Setup](#environment-setup)
- [Component Testing](#component-testing)
  - [1. Azure Infrastructure Tests](#1-azure-infrastructure-tests)
  - [2. Storage Account Tests](#2-storage-account-tests)
  - [3. Function App Tests](#3-function-app-tests)
  - [4. Microsoft Graph API Tests](#4-microsoft-graph-api-tests)
  - [5. Individual Function Tests](#5-individual-function-tests)
  - [6. Queue Flow Tests](#6-queue-flow-tests)
  - [7. End-to-End Tests](#7-end-to-end-tests)
- [Troubleshooting Decision Trees](#troubleshooting-decision-trees)
- [Performance Baselines](#performance-baselines)
- [Common Failure Scenarios](#common-failure-scenarios)

---

## Prerequisites

### Required Tools

```bash
# Azure CLI
az --version  # Required: 2.50.0 or higher

# Azure Functions Core Tools
func --version  # Required: 4.0.5000 or higher

# Python
python3 --version  # Required: 3.11 or higher

# jq (for JSON parsing)
jq --version

# curl
curl --version
```

### Authentication Setup

```bash
# Login to Azure
az login

# Set subscription
az account set --subscription "YOUR_SUBSCRIPTION_ID"

# Verify identity
az account show --query "user.name" -o tsv
```

### Environment Variables

```bash
# Export required variables
export RESOURCE_GROUP="rg-invoice-agent-prod"
export FUNCTION_APP="func-invoice-agent-prod"
export STORAGE_ACCOUNT="stinvoiceagentprod"
export APP_INSIGHTS="ai-invoice-agent-prod"
export INVOICE_MAILBOX="invoices@company.com"
export AP_EMAIL="ap@company.com"
```

---

## Environment Setup

### Verify Environment Configuration

```bash
# Test script: verify-environment.sh
#!/bin/bash

echo "=== Environment Configuration Check ==="

# Check Azure login
if az account show &>/dev/null; then
    echo "✅ Azure CLI authenticated"
    az account show --query "user.name" -o tsv
else
    echo "❌ Not logged into Azure. Run: az login"
    exit 1
fi

# Check resource group exists
if az group exists --name "$RESOURCE_GROUP" | grep -q true; then
    echo "✅ Resource group exists: $RESOURCE_GROUP"
else
    echo "❌ Resource group not found: $RESOURCE_GROUP"
    exit 1
fi

# Check function app exists
if az functionapp show --name "$FUNCTION_APP" --resource-group "$RESOURCE_GROUP" &>/dev/null; then
    echo "✅ Function App exists: $FUNCTION_APP"
else
    echo "❌ Function App not found: $FUNCTION_APP"
    exit 1
fi

# Check storage account exists
if az storage account show --name "$STORAGE_ACCOUNT" --resource-group "$RESOURCE_GROUP" &>/dev/null; then
    echo "✅ Storage Account exists: $STORAGE_ACCOUNT"
else
    echo "❌ Storage Account not found: $STORAGE_ACCOUNT"
    exit 1
fi

echo ""
echo "✅ All environment checks passed"
```

**Expected Output:**
```
✅ Azure CLI authenticated
user@company.com
✅ Resource group exists: rg-invoice-agent-prod
✅ Function App exists: func-invoice-agent-prod
✅ Storage Account exists: stinvoiceagentprod

✅ All environment checks passed
```

---

## Component Testing

### 1. Azure Infrastructure Tests

#### 1.1 Resource Group Status

```bash
# Check resource group and all resources
az group show --name "$RESOURCE_GROUP" --query "{Name:name, Location:location, State:properties.provisioningState}" -o table

# List all resources in group
az resource list --resource-group "$RESOURCE_GROUP" --query "[].{Name:name, Type:type, State:provisioningState}" -o table
```

**Expected Output:**
```
Name                      Location    State
------------------------  ----------  ---------
rg-invoice-agent-prod     eastus      Succeeded

Name                          Type                                          State
----------------------------  --------------------------------------------  ---------
func-invoice-agent-prod       Microsoft.Web/sites                          Succeeded
stinvoiceagentprod            Microsoft.Storage/storageAccounts            Succeeded
ai-invoice-agent-prod         Microsoft.Insights/components                Succeeded
asp-invoice-agent-prod        Microsoft.Web/serverfarms                    Succeeded
```

**Troubleshooting:**
- If State is not "Succeeded", check deployment logs
- If resources missing, redeploy infrastructure: `az deployment group create --template-file infrastructure/bicep/main.bicep`

---

#### 1.2 Network Connectivity

```bash
# Test connectivity to Function App
curl -s -o /dev/null -w "%{http_code}" "https://${FUNCTION_APP}.azurewebsites.net"

# Expected: 200 or 401 (401 means app is up but needs auth)

# Test storage account endpoint
curl -s -o /dev/null -w "%{http_code}" "https://${STORAGE_ACCOUNT}.blob.core.windows.net"

# Expected: 400 (endpoint exists but requires auth headers)
```

**Expected Output:**
```
200  # Function App
400  # Storage Account
```

---

### 2. Storage Account Tests

#### 2.1 Verify Tables Exist

```bash
# List all tables
az storage table list \
  --account-name "$STORAGE_ACCOUNT" \
  --query "[].name" -o tsv

# Expected tables:
# - VendorMaster
# - InvoiceTransactions
```

**Expected Output:**
```
InvoiceTransactions
VendorMaster
```

**Troubleshooting:**
```bash
# Create missing tables
az storage table create --name VendorMaster --account-name "$STORAGE_ACCOUNT"
az storage table create --name InvoiceTransactions --account-name "$STORAGE_ACCOUNT"
```

---

#### 2.2 Verify Queues Exist

```bash
# List all queues
az storage queue list \
  --account-name "$STORAGE_ACCOUNT" \
  --query "[].name" -o tsv

# Expected queues:
# - raw-mail
# - to-post
# - notify
# - raw-mail-poison
# - to-post-poison
# - notify-poison
```

**Expected Output:**
```
notify
notify-poison
raw-mail
raw-mail-poison
to-post
to-post-poison
```

---

#### 2.3 Check Queue Depths

```bash
# Script: check-queue-depths.sh
#!/bin/bash

echo "Queue Depths at $(date)"
echo "================================"

for queue in raw-mail to-post notify raw-mail-poison to-post-poison notify-poison; do
    count=$(az storage queue metadata show \
      --name "$queue" \
      --account-name "$STORAGE_ACCOUNT" \
      --query "approximateMessagesCount" -o tsv 2>/dev/null || echo "0")

    printf "%-20s : %5s messages\n" "$queue" "$count"
done
```

**Expected Output:**
```
Queue Depths at Tue Nov 19 14:30:00 EST 2025
================================
raw-mail             :     0 messages
to-post              :     0 messages
notify               :     0 messages
raw-mail-poison      :     0 messages
to-post-poison       :     0 messages
notify-poison        :     0 messages
```

**Thresholds:**
- Normal: 0-10 messages
- Elevated: 10-100 messages (check processing)
- Critical: >100 messages (investigate immediately)
- Poison queues: Should always be 0

---

#### 2.4 Verify Blob Container

```bash
# Check invoices container exists
az storage container exists \
  --name invoices \
  --account-name "$STORAGE_ACCOUNT" \
  --query "exists" -o tsv

# Expected: true

# List recent blobs (last 10)
az storage blob list \
  --container-name invoices \
  --account-name "$STORAGE_ACCOUNT" \
  --query "[].{Name:name, Size:properties.contentLength, Modified:properties.lastModified}" \
  --output table \
  | head -15
```

---

#### 2.5 VendorMaster Data Check

```bash
# Count vendors in VendorMaster
az storage entity query \
  --table-name VendorMaster \
  --account-name "$STORAGE_ACCOUNT" \
  --filter "PartitionKey eq 'Vendor' and Active eq true" \
  --select "VendorName" \
  --query "length(items)" -o tsv

# Expected: At least 9 vendors (MVP set)

# List all active vendors
az storage entity query \
  --table-name VendorMaster \
  --account-name "$STORAGE_ACCOUNT" \
  --filter "PartitionKey eq 'Vendor' and Active eq true" \
  --select "VendorName,GLCode,ExpenseDept" \
  --output table
```

**Expected Output:**
```
9

VendorName              GLCode    ExpenseDept
----------------------  --------  ---------------------
Amazon Web Services     7110      Cloud
Amazon Business         6215      Hardware - Operations
Microsoft               7112      M365 Suite
FRSecure                7112      CyberSecurity
Mimecast                7112      CyberSecurity
1Password               7112      CyberSecurity
EasyDmarc               7112      CyberSecurity
Autocad                 7112      Software - Facilities
Dell                    6215      Hardware - Operations
```

**Troubleshooting:**
```bash
# Seed vendors if missing
cd infrastructure/scripts
python seed_vendors.py "$(az storage account show-connection-string --name $STORAGE_ACCOUNT --query connectionString -o tsv)"
```

---

### 3. Function App Tests

#### 3.1 Function App Health

```bash
# Check Function App status
az functionapp show \
  --name "$FUNCTION_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --query "{State:state, DefaultHostName:defaultHostName, EnabledHostNames:enabledHostNames}" \
  -o table

# Expected State: "Running"
```

**Expected Output:**
```
State    DefaultHostName                            EnabledHostNames
-------  -----------------------------------------  ------------------
Running  func-invoice-agent-prod.azurewebsites.net  [...]
```

---

#### 3.2 Function App Settings Validation

```bash
# Check critical app settings exist
REQUIRED_SETTINGS=(
    "AzureWebJobsStorage"
    "APPLICATIONINSIGHTS_CONNECTION_STRING"
    "INVOICE_MAILBOX"
    "AP_EMAIL_ADDRESS"
    "TEAMS_WEBHOOK_URL"
)

echo "Checking required app settings..."
for setting in "${REQUIRED_SETTINGS[@]}"; do
    value=$(az functionapp config appsettings list \
      --name "$FUNCTION_APP" \
      --resource-group "$RESOURCE_GROUP" \
      --query "[?name=='$setting'].value | [0]" -o tsv)

    if [ -n "$value" ]; then
        echo "✅ $setting is set"
    else
        echo "❌ $setting is MISSING"
    fi
done
```

**Expected Output:**
```
✅ AzureWebJobsStorage is set
✅ APPLICATIONINSIGHTS_CONNECTION_STRING is set
✅ INVOICE_MAILBOX is set
✅ AP_EMAIL_ADDRESS is set
✅ TEAMS_WEBHOOK_URL is set
```

---

#### 3.3 List All Functions

```bash
# List deployed functions
az functionapp function list \
  --name "$FUNCTION_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --query "[].{Name:name, Type:properties.config.bindings[0].type}" \
  -o table
```

**Expected Output:**
```
Name            Type
--------------  ------------
AddVendor       httpTrigger
ExtractEnrich   queueTrigger
MailIngest      timerTrigger
Notify          queueTrigger
PostToAP        queueTrigger
```

---

### 4. Microsoft Graph API Tests

#### 4.1 Test Graph API Authentication

```bash
# Use the grant_mailbox_access.py script to verify
cd /Users/alex/dev/invoice-agent/scripts

python3 grant_mailbox_access.py --verify
```

**Expected Output:**
```
✅ Successfully authenticated to Microsoft Graph API
✅ Mailbox access verified for: invoices@company.com
✅ Can read mailbox folders
```

---

#### 4.2 Check Mailbox Unread Count

```bash
# Run check script
cd /Users/alex/dev/invoice-agent/scripts

python3 << 'EOF'
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent / "src"))

from shared.graph_client import GraphAPIClient

client = GraphAPIClient()
mailbox = os.environ["INVOICE_MAILBOX"]
emails = client.get_unread_emails(mailbox, max_results=10)

print(f"Unread emails in {mailbox}: {len(emails)}")
for email in emails[:5]:
    print(f"  - From: {email['sender']['emailAddress']['address']}")
    print(f"    Subject: {email['subject']}")
    print(f"    Attachments: {email.get('hasAttachments', False)}")
EOF
```

**Expected Output:**
```
Unread emails in invoices@company.com: 3
  - From: vendor1@example.com
    Subject: Invoice #12345
    Attachments: True
```

---

### 5. Individual Function Tests

#### 5.1 MailIngest Function

**Trigger Timer Function Manually:**

```bash
# Get function key
FUNCTION_KEY=$(az functionapp function keys list \
  --name "$FUNCTION_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --function-name MailIngest \
  --query "default" -o tsv)

# Trigger function via admin endpoint
curl -X POST \
  "https://${FUNCTION_APP}.azurewebsites.net/admin/functions/MailIngest" \
  -H "x-functions-key: $FUNCTION_KEY" \
  -H "Content-Type: application/json" \
  -d '{}'

# Expected: 202 Accepted
```

**Check Execution in Application Insights:**

```bash
# Query recent MailIngest executions
az monitor app-insights query \
  --app "$APP_INSIGHTS" \
  --resource-group "$RESOURCE_GROUP" \
  --analytics-query "
    requests
    | where timestamp > ago(10m)
    | where operation_Name == 'MailIngest'
    | project timestamp, success, duration, resultCode
    | order by timestamp desc
    | take 5
  " \
  --output table
```

**Expected Output:**
```
Timestamp                  Success    Duration    ResultCode
-------------------------  ---------  ----------  ----------
2025-11-19T14:35:22.123Z   True       2341        200
```

**Verify Queue Message Created:**

```bash
# Check raw-mail queue for new messages
az storage message peek \
  --queue-name raw-mail \
  --account-name "$STORAGE_ACCOUNT" \
  --num-messages 1
```

---

#### 5.2 ExtractEnrich Function

**Test by Adding Message to Queue:**

```bash
# Create test message
TEST_MESSAGE=$(cat <<EOF
{
  "id": "01TEST123456789ABCDEFGHIJK",
  "sender": "billing@microsoft.com",
  "subject": "Invoice #M-12345",
  "blob_url": "https://stinvoiceagentprod.blob.core.windows.net/invoices/test.pdf",
  "received_at": "2025-11-19T14:00:00Z",
  "original_message_id": "AAA123456789"
}
EOF
)

# Base64 encode message
ENCODED_MSG=$(echo -n "$TEST_MESSAGE" | base64)

# Put message in queue
az storage message put \
  --queue-name raw-mail \
  --account-name "$STORAGE_ACCOUNT" \
  --content "$ENCODED_MSG"

# Wait 5 seconds for processing
sleep 5

# Check to-post queue for enriched message
az storage message peek \
  --queue-name to-post \
  --account-name "$STORAGE_ACCOUNT" \
  --num-messages 1
```

**Expected Output:**
```
{
  "content": "eyJpZCI6IjAxVEVTVDEyMzQ1Njc4OUFCQyIsInZlbmRvcl9uYW1lIjoiTWljcm9zb2Z0IiwiZXhwZW5zZV9kZXB0IjoiTTM2NSBTdWl0ZSIsImdsX2NvZGUiOiI3MTEyIiwiYWxsb2NhdGlvbl9zY2hlZHVsZSI6IjMiLCJiaWxsaW5nX3BhcnR5IjoiQ29tcGFueSBIUSIsInN0YXR1cyI6ImVucmljaGVkIn0=",
  "dequeueCount": 0,
  "expirationTime": "...",
  "id": "...",
  "insertionTime": "...",
  "popReceipt": null,
  "timeNextVisible": "..."
}
```

**Decode and Verify:**

```bash
# Decode message content
echo "BASE64_CONTENT_HERE" | base64 -d | jq .
```

**Expected Enriched Data:**
```json
{
  "id": "01TEST123456789ABCDEFGHIJK",
  "vendor_name": "Microsoft",
  "expense_dept": "M365 Suite",
  "gl_code": "7112",
  "allocation_schedule": "3",
  "billing_party": "Company HQ",
  "blob_url": "https://stinvoiceagentprod.blob.core.windows.net/invoices/test.pdf",
  "original_message_id": "AAA123456789",
  "status": "enriched"
}
```

---

#### 5.3 PostToAP Function

**Monitor Execution:**

```bash
# Query PostToAP executions
az monitor app-insights query \
  --app "$APP_INSIGHTS" \
  --resource-group "$RESOURCE_GROUP" \
  --analytics-query "
    requests
    | where timestamp > ago(10m)
    | where operation_Name == 'PostToAP'
    | project timestamp, success, duration, customDimensions.transaction_id
    | order by timestamp desc
  " \
  --output table
```

**Check InvoiceTransactions Table:**

```bash
# Query recent transactions
az storage entity query \
  --table-name InvoiceTransactions \
  --account-name "$STORAGE_ACCOUNT" \
  --filter "PartitionKey eq '$(date +%Y%m)'" \
  --select "RowKey,VendorName,Status,ProcessedAt" \
  --output table \
  | tail -10
```

---

#### 5.4 Notify Function

**Test Teams Webhook Directly:**

```bash
# Get webhook URL from app settings
WEBHOOK_URL=$(az functionapp config appsettings list \
  --name "$FUNCTION_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --query "[?name=='TEAMS_WEBHOOK_URL'].value | [0]" -o tsv)

# Send test notification
curl -X POST "$WEBHOOK_URL" \
  -H 'Content-Type: application/json' \
  -d '{
    "@type": "MessageCard",
    "@context": "https://schema.org/extensions",
    "summary": "Test Notification",
    "themeColor": "0078D4",
    "sections": [{
      "activityTitle": "Invoice Agent Test",
      "text": "This is a test notification from the runbook"
    }]
  }'

# Expected: 1 (success)
```

---

#### 5.5 AddVendor Function (HTTP Endpoint)

**Test Add Vendor API:**

```bash
# Get function URL
FUNCTION_URL="https://${FUNCTION_APP}.azurewebsites.net/api/AddVendor"

# Get function key
FUNCTION_KEY=$(az functionapp function keys list \
  --name "$FUNCTION_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --function-name AddVendor \
  --query "default" -o tsv)

# Add test vendor
curl -X POST "$FUNCTION_URL?code=$FUNCTION_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "vendor_name": "Test Vendor Inc",
    "vendor_domain": "testvendor.com",
    "expense_dept": "IT",
    "gl_code": "7112",
    "allocation_schedule": "MONTHLY",
    "billing_party": "Company HQ"
  }'

# Expected: 201 Created with JSON response
```

**Expected Response:**
```json
{
  "status": "success",
  "message": "Vendor added successfully",
  "vendor_name": "Test Vendor Inc",
  "row_key": "testvendor_com"
}
```

**Verify Vendor Added:**

```bash
az storage entity show \
  --table-name VendorMaster \
  --account-name "$STORAGE_ACCOUNT" \
  --partition-key "Vendor" \
  --row-key "testvendor_com" \
  --output table
```

---

### 6. Queue Flow Tests

#### 6.1 Verify Queue Triggers Are Active

```bash
# Check function runtime status
az functionapp show \
  --name "$FUNCTION_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --query "state" -o tsv

# Expected: Running

# Stream function logs to see queue processing
az functionapp log tail \
  --name "$FUNCTION_APP" \
  --resource-group "$RESOURCE_GROUP"

# Let it run for 30 seconds, then Ctrl+C
```

---

#### 6.2 Test Queue Message Retry Logic

```bash
# Put malformed message in queue (should retry then poison)
MALFORMED_MSG='{"invalid": "json without required fields"}'
ENCODED=$(echo -n "$MALFORMED_MSG" | base64)

az storage message put \
  --queue-name raw-mail \
  --account-name "$STORAGE_ACCOUNT" \
  --content "$ENCODED"

# Wait 2 minutes for retries
sleep 120

# Check poison queue
az storage queue metadata show \
  --name raw-mail-poison \
  --account-name "$STORAGE_ACCOUNT" \
  --query "approximateMessagesCount" -o tsv

# Expected: 1 (message moved to poison queue after retries)
```

---

### 7. End-to-End Tests

#### 7.1 Full Pipeline Test

**Prerequisites:**
- Test email account configured
- Access to invoice mailbox
- Access to AP mailbox

**Test Script:**

```bash
#!/bin/bash
# End-to-end pipeline test

set -e

echo "=== Invoice Agent End-to-End Test ==="
echo "Start time: $(date)"
echo ""

# Step 1: Send test invoice email
echo "1. Sending test invoice email to $INVOICE_MAILBOX..."

# Use verify_test_emails.py script
cd /Users/alex/dev/invoice-agent/scripts
python3 verify_test_emails.py --send-test

echo "   ✅ Test email sent"
echo ""

# Step 2: Wait for MailIngest (runs every 5 min, max wait 6 min)
echo "2. Waiting for MailIngest to process (max 6 minutes)..."
sleep 360

# Step 3: Check raw-mail queue
echo "3. Checking raw-mail queue..."
RAW_COUNT=$(az storage queue metadata show \
  --name raw-mail \
  --account-name "$STORAGE_ACCOUNT" \
  --query "approximateMessagesCount" -o tsv)

echo "   raw-mail queue: $RAW_COUNT messages"

# Step 4: Wait for ExtractEnrich processing
echo "4. Waiting for ExtractEnrich (30 seconds)..."
sleep 30

# Step 5: Check to-post queue
echo "5. Checking to-post queue..."
POST_COUNT=$(az storage queue metadata show \
  --name to-post \
  --account-name "$STORAGE_ACCOUNT" \
  --query "approximateMessagesCount" -o tsv)

echo "   to-post queue: $POST_COUNT messages"

# Step 6: Wait for PostToAP
echo "6. Waiting for PostToAP (30 seconds)..."
sleep 30

# Step 7: Check InvoiceTransactions
echo "7. Checking InvoiceTransactions table..."
TX_COUNT=$(az storage entity query \
  --table-name InvoiceTransactions \
  --account-name "$STORAGE_ACCOUNT" \
  --filter "PartitionKey eq '$(date +%Y%m)' and Subject co 'Test Invoice'" \
  --select "RowKey" \
  --query "length(items)" -o tsv)

echo "   Transactions with 'Test Invoice': $TX_COUNT"

# Step 8: Check AP mailbox
echo "8. Checking AP mailbox..."
cd /Users/alex/dev/invoice-agent/scripts

python3 << 'EOF'
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent / "src"))
from shared.graph_client import GraphAPIClient

client = GraphAPIClient()
ap_mailbox = os.environ["AP_EMAIL_ADDRESS"]
emails = client.get_unread_emails(ap_mailbox, max_results=10)
test_emails = [e for e in emails if "Test Invoice" in e.get("subject", "")]
print(f"   AP mailbox test emails: {len(test_emails)}")
EOF

# Step 9: Check Teams notification (manual verification)
echo ""
echo "9. Check Teams channel for notification (manual verification)"
echo ""

echo "=== Test Complete ==="
echo "End time: $(date)"
```

**Expected Timeline:**
```
T+0:00   - Test email sent
T+0:00-6:00 - MailIngest picks up email (timer trigger every 5 min)
T+6:00   - Email processed, blob uploaded, raw-mail queued
T+6:05   - ExtractEnrich processes, vendor enriched, to-post queued
T+6:10   - PostToAP sends email to AP, transaction logged, notify queued
T+6:15   - Notify posts to Teams
```

**Success Criteria:**
- Test email appears in AP mailbox: ✅
- Transaction logged in InvoiceTransactions: ✅
- Teams notification received: ✅
- All queues empty at end: ✅
- No poison queue messages: ✅

---

#### 7.2 Performance Test

**Test 10 Concurrent Invoices:**

```bash
#!/bin/bash
# Performance test: 10 concurrent invoices

echo "Performance Test - 10 Concurrent Invoices"
echo "Start time: $(date)"

START_TIME=$(date +%s)

# Send 10 test emails
for i in {1..10}; do
    echo "Sending invoice $i..."
    # Use your email sending script here
    sleep 1
done

# Wait for processing (max 2 minutes per invoice target)
echo "Waiting for processing (10 minutes max)..."
sleep 600

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
echo "=== Performance Results ==="
echo "Total time: $DURATION seconds"
echo "Average per invoice: $((DURATION / 10)) seconds"

# Check results
TX_COUNT=$(az storage entity query \
  --table-name InvoiceTransactions \
  --account-name "$STORAGE_ACCOUNT" \
  --filter "PartitionKey eq '$(date +%Y%m)'" \
  --select "RowKey" \
  --query "length(items)" -o tsv)

echo "Transactions logged: $TX_COUNT"
echo ""

if [ $DURATION -lt 600 ] && [ "$TX_COUNT" -eq 10 ]; then
    echo "✅ Performance test PASSED"
else
    echo "❌ Performance test FAILED"
fi
```

**Performance Baselines:**
- Single invoice: <60 seconds (SLO target)
- 10 concurrent: <120 seconds total (parallel processing)
- 50 concurrent: <300 seconds total (with scaling)

---

## Troubleshooting Decision Trees

### Decision Tree 1: Emails Not Being Processed

```
Is MailIngest function running?
├─ NO → Check Function App state
│       └─ Stopped → Start: az functionapp start --name $FUNCTION_APP --resource-group $RESOURCE_GROUP
│       └─ Error → Check logs: az functionapp log tail
│
└─ YES → Are there unread emails in mailbox?
         ├─ NO → Wait for next email or send test
         │
         └─ YES → Check Graph API authentication
                  ├─ Failed → Verify service principal permissions
                  │           └─ Fix: scripts/grant_mailbox_access.py
                  │
                  └─ OK → Check raw-mail queue
                           ├─ Empty → MailIngest not queuing (check function logs)
                           └─ Has messages → ExtractEnrich issue (see Decision Tree 2)
```

### Decision Tree 2: Queue Processing Stuck

```
Which queue has messages?
├─ raw-mail → Is ExtractEnrich running?
│             ├─ NO → Check function state, restart if needed
│             └─ YES → Check for errors in Application Insights
│                      └─ Vendor lookup failing? → Check VendorMaster table
│
├─ to-post → Is PostToAP running?
│            ├─ NO → Check function state
│            └─ YES → Check Graph API auth for sending
│                     └─ 401/403 → Verify Mail.Send permission
│
└─ notify → Is Notify running?
            ├─ NO → Check function state
            └─ YES → Check Teams webhook URL
                     └─ Test: curl -X POST $WEBHOOK_URL -d '{...}'
```

### Decision Tree 3: High Error Rate

```
What is the error rate?
├─ >5% → CRITICAL: Check Application Insights for error type
│        ├─ Graph API 429 → Throttling (reduce frequency)
│        ├─ Storage 503 → Storage throttling (check limits)
│        ├─ 401/403 → Auth failure (rotate credentials)
│        └─ 500 → Function code error (check stack trace)
│
├─ 1-5% → WARNING: Investigate specific failures
│         └─ Check which function is failing most
│
└─ <1% → Normal: Monitor for trends
```

---

## Performance Baselines

### Expected Metrics (Production)

| Metric | Target | Warning | Critical |
|--------|--------|---------|----------|
| End-to-end latency | <60s | 60-90s | >90s |
| MailIngest duration | <5s | 5-10s | >10s |
| ExtractEnrich duration | <3s | 3-5s | >5s |
| PostToAP duration | <10s | 10-20s | >20s |
| Notify duration | <2s | 2-5s | >5s |
| Error rate | <1% | 1-5% | >5% |
| Vendor match rate | >80% | 70-80% | <70% |
| Queue depth (normal) | 0-10 | 10-100 | >100 |
| Poison queue | 0 | 1-5 | >5 |

### Measure Current Performance

```bash
# Query performance metrics
az monitor app-insights query \
  --app "$APP_INSIGHTS" \
  --resource-group "$RESOURCE_GROUP" \
  --analytics-query "
    requests
    | where timestamp > ago(24h)
    | summarize
        AvgDuration = round(avg(duration)/1000, 2),
        P95Duration = round(percentile(duration, 95)/1000, 2),
        P99Duration = round(percentile(duration, 99)/1000, 2),
        SuccessRate = round(countif(success == true) * 100.0 / count(), 2),
        Count = count()
      by operation_Name
    | order by Count desc
  " \
  --output table
```

---

## Common Failure Scenarios

### Scenario 1: Function App Not Starting

**Symptoms:**
- State shows "Stopped"
- HTTP requests return 503

**Resolution:**
```bash
# Start function app
az functionapp start --name "$FUNCTION_APP" --resource-group "$RESOURCE_GROUP"

# Verify state
az functionapp show --name "$FUNCTION_APP" --resource-group "$RESOURCE_GROUP" --query "state" -o tsv
```

---

### Scenario 2: VendorMaster Empty

**Symptoms:**
- All invoices marked as "unknown"
- High unknown vendor rate

**Resolution:**
```bash
# Seed vendors
cd /Users/alex/dev/invoice-agent/infrastructure/scripts

CONN_STR=$(az storage account show-connection-string \
  --name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --query connectionString -o tsv)

python3 seed_vendors.py "$CONN_STR"
```

---

### Scenario 3: Graph API Authentication Failure

**Symptoms:**
- "Unauthorized" errors in logs
- MailIngest or PostToAP failing

**Resolution:**
```bash
# Check managed identity
az functionapp identity show \
  --name "$FUNCTION_APP" \
  --resource-group "$RESOURCE_GROUP"

# Verify Graph API permissions
cd /Users/alex/dev/invoice-agent/scripts
python3 grant_mailbox_access.py --verify

# If failed, re-grant permissions
python3 grant_mailbox_access.py --grant
```

---

### Scenario 4: Teams Webhook Not Working

**Symptoms:**
- No notifications in Teams
- Notify function succeeds but no cards appear

**Resolution:**
```bash
# Get webhook URL
WEBHOOK=$(az functionapp config appsettings list \
  --name "$FUNCTION_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --query "[?name=='TEAMS_WEBHOOK_URL'].value | [0]" -o tsv)

# Test webhook
curl -X POST "$WEBHOOK" \
  -H 'Content-Type: application/json' \
  -d '{
    "@type": "MessageCard",
    "summary": "Test",
    "themeColor": "0078D4",
    "sections": [{"activityTitle": "Webhook Test", "text": "Testing connectivity"}]
  }'

# Expected: 1

# If fails, regenerate webhook in Teams:
# 1. Go to Teams channel → Connectors
# 2. Remove old "Incoming Webhook"
# 3. Add new "Incoming Webhook"
# 4. Update app setting:
az functionapp config appsettings set \
  --name "$FUNCTION_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --settings "TEAMS_WEBHOOK_URL=NEW_WEBHOOK_URL"
```

---

### Scenario 5: Poison Queue Messages

**Symptoms:**
- Messages in *-poison queues
- Same transaction retrying repeatedly

**Resolution:**
```bash
# View poison queue messages
az storage message get \
  --queue-name raw-mail-poison \
  --account-name "$STORAGE_ACCOUNT" \
  --num-messages 5

# Analyze the message
# Decode base64 content, identify the issue

# Fix root cause (code bug, data issue, etc.)

# Reprocess or delete
# Delete:
az storage queue clear \
  --name raw-mail-poison \
  --account-name "$STORAGE_ACCOUNT"
```

---

## Quick Reference Commands

```bash
# Restart Function App
az functionapp restart --name "$FUNCTION_APP" --resource-group "$RESOURCE_GROUP"

# View live logs
az functionapp log tail --name "$FUNCTION_APP" --resource-group "$RESOURCE_GROUP"

# Check recent errors
az monitor app-insights query --app "$APP_INSIGHTS" --resource-group "$RESOURCE_GROUP" \
  --analytics-query "exceptions | where timestamp > ago(1h) | take 10" --output table

# Clear queue
az storage queue clear --name raw-mail --account-name "$STORAGE_ACCOUNT"

# Check transaction count
az storage entity query --table-name InvoiceTransactions --account-name "$STORAGE_ACCOUNT" \
  --filter "PartitionKey eq '$(date +%Y%m)'" --select "RowKey" --query "length(items)"
```

---

**Last Updated:** 2025-11-19
**Next Review:** 2025-12-19
