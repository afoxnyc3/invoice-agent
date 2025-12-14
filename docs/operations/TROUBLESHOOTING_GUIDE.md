# Troubleshooting Guide

**Last Updated:** November 13, 2025

Common issues and solutions for the Invoice Agent. This guide covers diagnosis, investigation, and resolution steps.

## Table of Contents
- [Function-Level Errors](#function-level-errors)
- [Queue Troubleshooting](#queue-troubleshooting)
- [Authentication & Secrets](#authentication--secrets)
- [Storage Issues](#storage-issues)
- [Performance Problems](#performance-problems)
- [Data Issues](#data-issues)
- [Teams Notifications](#teams-notifications)
- [How to Read Logs](#how-to-read-logs)

---

## Function-Level Errors

### MailIngest Function Not Running

**Symptom:** Timer trigger isn't executing every 5 minutes

**Diagnosis:**
```bash
# Check function app status
az functionapp show \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "state"

# Expected: "Running"

# Check timer trigger configuration
az functionapp function show \
  --name MailIngest \
  --functionapp-name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod
```

**Root Causes & Solutions:**

| Cause | Sign | Solution |
|-------|------|----------|
| Function App stopped | State is "Stopped" | `az functionapp start --name func-invoice-agent-prod --resource-group rg-invoice-agent-prod` |
| Timer schedule disabled | Timer trigger missing from function.json | Redeploy from main branch |
| App Service Plan scale issue | High CPU/memory | Upgrade plan: `az appservice plan update --sku P2V2 ...` |
| Graph API token expired | Logs show "Unauthorized" | Cycle managed identity: `az identity show ...` |

**Check Logs:**
```bash
az functionapp log tail \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --filter "MailIngest" | head -20
```

---

### ExtractEnrich Returns 500 Error

**Symptom:** Queue messages not being processed, function failures in logs

**Diagnosis:**
```bash
# Get recent function executions
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "
    requests
    | where name == 'ExtractEnrich' and timestamp > ago(1h)
    | summarize count(), failures = sumif(success == false) by resultCode
  " \
  --resource-group rg-invoice-agent-prod

# Get detailed error logs
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "
    exceptions
    | where outerMessage contains 'ExtractEnrich'
    | order by timestamp desc
    | limit 10
  " \
  --resource-group rg-invoice-agent-prod
```

**Common Issues:**

| Error Message | Cause | Fix |
|---------------|-------|-----|
| "ValidationError: vendor_name required" | RawMail queue message malformed | Check MailIngest sender parsing |
| "KeyError: 'AzureWebJobsStorage'" | Missing connection string | Add to Function App settings: `az functionapp config appsettings set ...` |
| "TableNotFound: VendorMaster" | Table doesn't exist | Create: `az storage table create --name VendorMaster ...` |
| "Vendor not found in [vendor_domain]" | Vendor missing from table | Add vendor via AddVendor endpoint or seed script |

**Debug ExtractEnrich Locally:**
```bash
# Start local functions
cd src && func start

# Send test message to raw-mail queue (Azure Storage Explorer)
# Message should contain JSON matching RawMail model

# Check function logs for processing
```

---

### PostToAP Returns 401 or 403

**Symptom:** "Unauthorized" or "Forbidden" when sending to AP mailbox

**Diagnosis:**
```bash
# Check Graph API permissions
az functionapp config show \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "identity"

# Verify service principal has Mail.Send permission
# See: [AZURE_SETUP.md](../AZURE_SETUP.md#step-3-grant-graph-api-permissions)

# Check managed identity status
az identity show \
  --name mi-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod
```

**Solutions:**

1. **Check Token Expiration**
   ```bash
   # Tokens auto-refresh, but verify in logs
   az functionapp log tail --name func-invoice-agent-prod | grep -i "token"
   ```

2. **Verify Service Principal Permissions**
   ```bash
   # Re-assign Graph API permissions
   az ad sp app-role assign-grant \
     --id "sp-invoice-agent-prod" \
     --api "Microsoft Graph" \
     --role "Mail.Send" \
     --resource-group rg-invoice-agent-prod
   ```

3. **Check Mailbox Access**
   ```bash
   # Verify function app can read the mailbox
   # Go to shared mailbox → Settings → Delegates
   # Ensure service principal is listed as delegate with Send As permission
   ```

---

### Notify Function Silently Failing

**Symptom:** Teams webhooks not posting, no errors in logs

**Diagnosis:**
```bash
# Check webhook URL configuration
az functionapp config appsettings list \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  | grep -i "webhook"

# Expected: TEAMS_WEBHOOK_URL set to valid webhook

# Check if messages are in notify queue
az storage queue metadata show \
  --account-name stinvoiceagentprod \
  --name notify
```

**Solutions:**

1. **Regenerate Webhook URL**
   - Go to Teams Channel → Connectors → Incoming Webhook
   - Delete old webhook, create new one
   - Update `TEAMS_WEBHOOK_URL` setting

2. **Test Webhook Directly**
   ```bash
   WEBHOOK_URL=$(az functionapp config appsettings list \
     --name func-invoice-agent-prod \
     --query "[?name=='TEAMS_WEBHOOK_URL'].value" -o tsv)

   curl -X POST $WEBHOOK_URL \
     -H 'Content-Type: application/json' \
     -d '{
       "@type": "MessageCard",
       "@context": "https://schema.org/extensions",
       "summary": "Test",
       "themeColor": "0078D4",
       "sections": [{
         "activityTitle": "Invoice Agent Test",
         "text": "Webhook is working"
       }]
     }'
   ```

3. **Check Notify Queue Depth**
   ```bash
   az storage queue metadata show \
     --account-name stinvoiceagentprod \
     --name notify

   # If ApproximateMessageCount > 100, queue is backing up
   ```

---

## Queue Troubleshooting

### Messages Stuck in Queue

**Symptom:** Queue message count keeps growing, functions aren't processing

**Diagnosis:**
```bash
# Check queue depths
for queue in raw-mail to-post notify; do
  echo "$queue:"
  az storage queue metadata show \
    --account-name stinvoiceagentprod \
    --name $queue \
    --query "ApproximateMessageCount"
done

# Check for poison queue messages
az storage queue list \
  --account-name stinvoiceagentprod \
  --query "[].name" | grep poison
```

**Root Causes & Solutions:**

| Cause | Indicator | Solution |
|-------|-----------|----------|
| Downstream function crashed | raw-mail growing, to-post empty | Redeploy ExtractEnrich function |
| Function timeout | Messages in queue, no logs | Increase function timeout: `az functionapp config show ... --query "functionAppScaleLimit"` |
| Authentication failure | Errors in logs, queue growing | Check secrets/credentials |
| Poison queue threshold reached | Messages moving to poison queue | Manually process & delete |

**Clear Messages from Queue:**
```bash
# View first message
az storage message peek \
  --account-name stinvoiceagentprod \
  --queue-name raw-mail

# Delete all messages from a queue (careful!)
az storage queue delete \
  --account-name stinvoiceagentprod \
  --name raw-mail
```

### Poison Queue Processing

**Symptom:** Messages in raw-mail-poison, to-post-poison, or notify-poison queues

**Investigation:**
```bash
# View poison queue messages
az storage message get \
  --account-name stinvoiceagentprod \
  --queue-name raw-mail-poison

# Decode message (base64)
# Copy base64 content from above, then:
echo "base64_content_here" | base64 -d | jq .
```

**Remediation Steps:**

1. **Analyze the message** - Is it malformed or a real error?
2. **Fix the root cause** - Update code or data if needed
3. **Reprocess the message**:
   ```bash
   # Get the message content
   MSG=$(az storage message get \
     --account-name stinvoiceagentprod \
     --queue-name raw-mail-poison \
     --query "[0].content" -o tsv)

   # Base64 decode
   DECODED=$(echo "$MSG" | base64 -d)

   # Put back in main queue
   az storage message put \
     --account-name stinvoiceagentprod \
     --queue-name raw-mail \
     --message "$DECODED"

   # Delete from poison queue
   az storage message delete \
     --account-name stinvoiceagentprod \
     --queue-name raw-mail-poison \
     --id "message-id" \
     --pop-receipt "receipt"
   ```

---

## Authentication & Secrets

### "Unauthorized" or "Forbidden" Errors

**Diagnosis:**
```bash
# Check what secrets are set
az functionapp config appsettings list \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "[].name" | grep -E "KEY|SECRET|TOKEN|PASSWORD"

# Expected to see: AzureWebJobsStorage, INVOICE_MAILBOX, TEAMS_WEBHOOK_URL, etc.
```

**Common Auth Issues:**

| Error | Cause | Solution |
|-------|-------|----------|
| "Invalid connection string" | Wrong/corrupted storage key | Regenerate storage account key |
| "Certificate not found" | Service principal certificate expired | Renew in Azure AD |
| "OAuth token invalid" | Graph API token expired | Restart function app to refresh |
| "Access denied to mailbox" | Service principal not delegated | Add delegate with Send As permission |

**Rotate Secrets:**
```bash
# Storage account key
az storage account keys renew \
  --account-name stinvoiceagentprod \
  --key primary \
  --resource-group rg-invoice-agent-prod

# Update function app setting
NEW_CONN=$(az storage account show-connection-string \
  --name stinvoiceagentprod \
  --resource-group rg-invoice-agent-prod \
  --query connectionString -o tsv)

az functionapp config appsettings set \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --settings AzureWebJobsStorage="$NEW_CONN"
```

---

## Storage Issues

### Table Storage Errors

**"TableNotFound" Exception**

```bash
# Check if table exists
az storage table list \
  --account-name stinvoiceagentprod

# Create missing table
az storage table create \
  --account-name stinvoiceagentprod \
  --name VendorMaster  # or InvoiceTransactions
```

**"The remote server returned an error"**

```bash
# Check storage account connectivity
az storage account show \
  --name stinvoiceagentprod \
  --query "primaryEndpoints"

# Test with az storage command
az storage entity show \
  --account-name stinvoiceagentprod \
  --table-name VendorMaster \
  --partition-key "Vendor" \
  --row-key "adobe_com"
```

### Blob Storage Issues

**Cannot Access Invoice Files**

```bash
# Check blob container exists
az storage container list \
  --account-name stinvoiceagentprod

# Check blob URL permissions
az storage blob exists \
  --account-name stinvoiceagentprod \
  --container-name invoices \
  --name "sample.pdf"

# Generate SAS URL for testing
az storage blob generate-sas \
  --account-name stinvoiceagentprod \
  --container-name invoices \
  --name "sample.pdf" \
  --permissions racwd \
  --expiry "2025-12-13"
```

---

## Performance Problems

### Slow Invoice Processing

**Symptom:** Functions taking >60 seconds, SLA being missed

**Diagnosis:**
```bash
# Check function duration metrics
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "
    requests
    | where name in ('MailIngest', 'ExtractEnrich', 'PostToAP', 'Notify')
    | summarize avg_duration = avg(duration), max_duration = max(duration) by name
  " \
  --resource-group rg-invoice-agent-prod

# Check cold start impact
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "
    traces
    | where message contains 'Cold start'
    | summarize count()
  " \
  --resource-group rg-invoice-agent-prod
```

**Bottleneck Analysis:**

| Phase | Typical | Flag If | Fix |
|-------|---------|---------|-----|
| MailIngest | 2-3 sec | >5 sec | Check Graph API latency |
| ExtractEnrich | 1-2 sec | >5 sec | Check VendorMaster table size |
| PostToAP | 5-8 sec | >15 sec | Check Graph API rate limits |
| Notify | 1-2 sec | >5 sec | Check Teams webhook response |

**Optimization:**

1. **Enable Premium Tier**
   ```bash
   az appservice plan update \
     --name asp-invoice-agent-prod \
     --resource-group rg-invoice-agent-prod \
     --sku P1V2  # Better performance, keeps warm
   ```

2. **Check Graph API Throttling**
   ```bash
   # Look for "429 Too Many Requests" in logs
   az monitor app-insights query \
     --app ai-invoice-agent-prod \
     --analytics-query "
       requests
       | where resultCode == '429'
     "
   ```

3. **Analyze VendorMaster Table Performance**
   ```bash
   # If table has >10,000 entities, consider indexing/partitioning
   # Current pattern: PartitionKey="Vendor", RowKey="domain"
   # This is optimal for 100-1000 vendors
   ```

---

## Data Issues

### Unknown Vendor Rate High (>20%)

**Symptom:** Many invoices marked as "unknown" vendor

**Investigation:**
```bash
# Check vendor count
az storage entity query \
  --account-name stinvoiceagentprod \
  --table-name VendorMaster \
  --select "VendorName,RowKey" | wc -l

# Export all vendor domains
az storage entity query \
  --account-name stinvoiceagentprod \
  --table-name VendorMaster \
  --select "RowKey" \
  --output tsv > vendors_current.txt
```

**Solutions:**

1. **Add Missing Vendors**
   ```bash
   # Use AddVendor endpoint
   curl -X POST https://func-invoice-agent-prod.azurewebsites.net/api/AddVendor \
     -H "Content-Type: application/json" \
     -d '{
       "vendor_name": "New Vendor",
       "vendor_domain": "newvendor.com",
       "expense_dept": "IT",
       "gl_code": "6100",
       "allocation_schedule": "MONTHLY",
       "billing_party": "Company HQ"
     }'
   ```

2. **Check Domain Normalization**
   ```bash
   # Domains are stored as lowercase with dots replaced by underscores
   # adobe.com becomes adobe_com
   # aws.amazon.com becomes aws_amazon_com

   # If sender uses uppercase or subdomain, it won't match
   # Solution: Update vendor lookup logic in ExtractEnrich
   ```

### Duplicate Invoices Detected

**Symptom:** Same invoice processed multiple times

**Analysis:**
```bash
# Check InvoiceTransactions for duplicates
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "
    customEvents
    | where name == 'InvoiceProcessed'
    | summarize count() by tostring(customDimensions.transaction_id)
    | where count_ > 1
  "
```

**Root Causes:**

| Cause | Sign | Solution |
|-------|------|----------|
| Email marked unread by mistake | Same transaction_id, different timestamps | Implement idempotency key |
| Message retry after timeout | Duplicate in to-post queue | Check function timeout settings |
| Manual requeue | Exact duplicate with same timestamp | Implement duplicate detection by message ID |

---

## Teams Notifications

### Teams Messages Not Appearing

**Symptom:** Webhook receives 200/202 OK but no message in channel

**Diagnosis:**
```bash
# Test webhook with Power Automate Adaptive Card format
WEBHOOK=$(az functionapp config appsettings list \
  --name func-invoice-agent-prod \
  --query "[?name=='TEAMS_WEBHOOK_URL'].value" -o tsv)

# Use utility script (recommended)
python scripts/power-automate/test_webhook.py "$WEBHOOK" --message "Test notification"

# Or with curl (Power Automate Adaptive Card envelope format)
curl -X POST "$WEBHOOK" \
  -H 'Content-Type: application/json' \
  -d '{
    "type": "message",
    "attachments": [{
      "contentType": "application/vnd.microsoft.card.adaptive",
      "contentUrl": null,
      "content": {
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [{"type": "TextBlock", "text": "Test message", "wrap": true}]
      }
    }]
  }'
```

**Solutions:**

1. **Check Webhook Format (Power Automate)**
   - System uses Adaptive Cards v1.4 wrapped in Power Automate message envelope
   - Required: `type: "message"`, `attachments` array, `contentType`, `contentUrl: null`, `content`
   - See `src/Notify/__init__.py` for exact format

2. **Check Power Automate Flow Configuration**
   - In "Post card in a chat or channel" action, use Expression (not literal string):
     ```
     string(triggerBody()?['attachments']?[0]?['content'])
     ```
   - Common error: expression stored as literal string without `@` prefix

3. **Verify Channel Permissions**
   - Flow must have access to the target Team/Channel
   - Check Power Automate flow run history for errors

4. **Validate Webhook URL**
   - Must be HTTPS
   - Power Automate format: `https://prod-XX.westus.logic.azure.com:443/workflows/...`
   - Check Key Vault secret `teams-webhook-url` has correct value

---

## How to Read Logs

### Finding Logs in Application Insights

**Query by Function:**
```bash
# View MailIngest logs
az monitor app-insights trace show \
  --app ai-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  | jq '.[] | select(.message | contains("MailIngest"))'
```

**View Recent Errors:**
```bash
# Last 10 errors
az monitor app-insights trace show \
  --app ai-invoice-agent-prod \
  --severity error \
  --limit 10 \
  --resource-group rg-invoice-agent-prod
```

**Stream Live Logs:**
```bash
# Real-time function logs
az functionapp log tail \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod
```

### Log Format & Meaning

```
2025-11-13T14:23:45.123Z [INFO]  [MailIngest] Checking mailbox for new emails
                         ↑        ↑    ↑           ↑
                       Time      Level Function    Message

2025-11-13T14:23:46.456Z [ERROR] [ExtractEnrich] ValidationError: vendor_name required
                                  ↑                ↑
                              Function            Error Type
```

**Log Levels:**
- `[ERROR]` - Function failed, manual investigation needed
- `[WARNING]` - Unusual but recoverable (vendor not found, etc.)
- `[INFO]` - Normal operation, function completed
- `[DEBUG]` - Detailed diagnostic info (only in local/dev)

### Correlation IDs

Every transaction has a ULID (transaction_id) that appears in all related logs:

```bash
# Find all logs for transaction
TRANSACTION_ID="01JCK3Q7H8ZVXN3BARC9GWAEZM"

az monitor app-insights trace show \
  --app ai-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  | jq ".[] | select(.customDimensions.transaction_id == \"$TRANSACTION_ID\")"

# Will show: MailIngest → ExtractEnrich → PostToAP → Notify logs
```

---

## When to Escalate

**Escalate if:**
- Deployment fails after 3 attempts
- Error rate remains >5% after 15 minutes
- Data corruption suspected
- Unable to remediate within 1 hour
- Multiple functions failing simultaneously

**Escalation Contact:** On-call engineer (Slack: #invoice-agent-oncall)

---

**More Help:** See [Operations Playbook](OPERATIONS_PLAYBOOK.md) for daily monitoring tasks.
