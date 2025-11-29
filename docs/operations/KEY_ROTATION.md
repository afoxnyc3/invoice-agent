# Key Rotation Procedures

**Last Updated:** November 29, 2025

Step-by-step procedures for rotating secrets and credentials used by Invoice Agent. Regular rotation reduces the impact of credential compromise and satisfies compliance requirements.

## Table of Contents
- [Overview](#overview)
- [Graph API Client Secret](#graph-api-client-secret)
- [Azure OpenAI API Key](#azure-openai-api-key)
- [Teams Webhook URL](#teams-webhook-url)
- [Verification Checklist](#verification-checklist)
- [Rollback Procedures](#rollback-procedures)
- [Rotation Schedule](#rotation-schedule)

---

## Overview

### Secrets Inventory

| Secret | App Setting | Rotation Frequency | Owner |
|--------|-------------|-------------------|-------|
| Graph API Client Secret | `GRAPH_CLIENT_SECRET` | 90 days | DevOps |
| Azure OpenAI API Key | `AZURE_OPENAI_API_KEY` | 90 days | DevOps |
| Teams Webhook URL | `TEAMS_WEBHOOK_URL` | 180 days | Ops |

### Prerequisites

- Azure CLI installed and authenticated (`az login`)
- Appropriate permissions:
  - **Azure AD**: Application Administrator or owner of the app registration
  - **Azure OpenAI**: Contributor on the OpenAI resource
  - **Function App**: Contributor on the resource group
  - **Key Vault**: Key Vault Secrets Officer (if using Key Vault references)

### Environment Variables

```bash
# Set these for your environment
export RESOURCE_GROUP="rg-invoice-agent-prod"
export FUNC_NAME="func-invoice-agent-prod"
export KEYVAULT_NAME="kv-invoice-agent-prod"
```

---

## Graph API Client Secret

**Owner:** DevOps Engineer
**Duration:** 15-20 minutes
**Frequency:** Every 90 days

### Step 1: Create New Secret in Azure AD

**Option A: Azure Portal**

1. Go to [Azure Portal](https://portal.azure.com) → **Azure Active Directory** → **App registrations**
2. Find and select the Invoice Agent app registration
3. Navigate to **Certificates & secrets** → **Client secrets**
4. Click **+ New client secret**
5. Set description: `invoice-agent-prod-YYYYMMDD`
6. Set expiration: 90 days (recommended) or custom
7. Click **Add**
8. **IMPORTANT:** Copy the secret value immediately (it won't be shown again)

**Option B: Azure CLI**

```bash
# Get the app registration ID
APP_ID=$(az ad app list --display-name "invoice-agent-prod" --query "[0].appId" -o tsv)

# Create new client secret (90 days expiry)
END_DATE=$(date -v+90d +%Y-%m-%d 2>/dev/null || date -d "+90 days" +%Y-%m-%d)

NEW_SECRET=$(az ad app credential reset \
  --id "$APP_ID" \
  --append \
  --display-name "invoice-agent-prod-$(date +%Y%m%d)" \
  --end-date "$END_DATE" \
  --query "password" -o tsv)

echo "New secret created. Store securely."
```

### Step 2: Update Key Vault (If Using Key Vault References)

```bash
# Update secret in Key Vault
az keyvault secret set \
  --vault-name "$KEYVAULT_NAME" \
  --name "graph-client-secret" \
  --value "$NEW_SECRET"

echo "Key Vault secret updated"
```

### Step 3: Update Function App Settings

```bash
# If using direct app settings (not Key Vault reference):
az functionapp config appsettings set \
  --name "$FUNC_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --settings GRAPH_CLIENT_SECRET="$NEW_SECRET" \
  --output none

echo "Function App settings updated"
```

### Step 4: Restart Function App

```bash
# Restart to pick up new credentials
az functionapp restart \
  --name "$FUNC_NAME" \
  --resource-group "$RESOURCE_GROUP"

echo "Function App restarted. Waiting 60 seconds for initialization..."
sleep 60
```

### Step 5: Verify Graph API Access

```bash
# Check function logs for authentication errors
az functionapp log tail \
  --name "$FUNC_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --timeout 30 2>&1 | grep -i "auth\|unauthorized\|token" || echo "No auth errors found"

# Test health endpoint
HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  "https://${FUNC_NAME}.azurewebsites.net/api/health")

if [ "$HEALTH_STATUS" = "200" ]; then
  echo "✅ Health check passed"
else
  echo "❌ Health check failed with status $HEALTH_STATUS"
fi
```

### Step 6: Remove Old Secret (After Grace Period)

Wait 24-48 hours before removing the old secret to ensure no issues:

```bash
# List all credentials
az ad app credential list --id "$APP_ID" --query "[].{keyId:keyId, displayName:displayName, endDateTime:endDateTime}"

# Delete old credential by keyId
az ad app credential delete --id "$APP_ID" --key-id "OLD_KEY_ID_HERE"

echo "Old secret removed"
```

---

## Azure OpenAI API Key

**Owner:** DevOps Engineer
**Duration:** 10-15 minutes
**Frequency:** Every 90 days

### Step 1: Regenerate Key in Azure Portal

1. Go to [Azure Portal](https://portal.azure.com) → **Azure OpenAI** resource
2. Navigate to **Keys and Endpoint** under Resource Management
3. Click **Regenerate Key1** or **Regenerate Key2**
   - **Tip:** Use the alternate key (Key2) if Key1 is currently in use
4. Confirm regeneration
5. Copy the new key value

**Using Azure CLI:**

```bash
# Get OpenAI resource name
OPENAI_RESOURCE="oai-invoice-agent-prod"

# Regenerate key1 (use key2 if key1 is active)
az cognitiveservices account keys regenerate \
  --name "$OPENAI_RESOURCE" \
  --resource-group "$RESOURCE_GROUP" \
  --key-name key1

# Get the new key
NEW_OPENAI_KEY=$(az cognitiveservices account keys list \
  --name "$OPENAI_RESOURCE" \
  --resource-group "$RESOURCE_GROUP" \
  --query "key1" -o tsv)

echo "New OpenAI key generated"
```

### Step 2: Update Key Vault (If Using Key Vault References)

```bash
az keyvault secret set \
  --vault-name "$KEYVAULT_NAME" \
  --name "azure-openai-api-key" \
  --value "$NEW_OPENAI_KEY"

echo "Key Vault secret updated"
```

### Step 3: Update Function App Settings

```bash
# If using direct app settings:
az functionapp config appsettings set \
  --name "$FUNC_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --settings AZURE_OPENAI_API_KEY="$NEW_OPENAI_KEY" \
  --output none

echo "Function App settings updated"
```

### Step 4: Restart Function App

```bash
az functionapp restart \
  --name "$FUNC_NAME" \
  --resource-group "$RESOURCE_GROUP"

echo "Function App restarted. Waiting 60 seconds..."
sleep 60
```

### Step 5: Verify OpenAI Access

```bash
# Test PDF extraction endpoint indirectly via logs
az functionapp log tail \
  --name "$FUNC_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --timeout 30 2>&1 | grep -i "openai\|extraction\|vendor" || echo "Check logs manually"

# Monitor Application Insights for OpenAI errors
az monitor app-insights query \
  --app "ai-invoice-agent-prod" \
  --resource-group "$RESOURCE_GROUP" \
  --analytics-query "
    traces
    | where timestamp > ago(5m)
    | where message contains 'OpenAI' or message contains 'extraction'
    | project timestamp, message, severityLevel
    | order by timestamp desc
    | take 10
  " 2>/dev/null || echo "Check Application Insights manually"
```

---

## Teams Webhook URL

**Owner:** Ops Engineer
**Duration:** 10 minutes
**Frequency:** Every 180 days

### Step 1: Create New Webhook in Teams

1. Open **Microsoft Teams**
2. Go to the target channel (e.g., #invoice-automation)
3. Click **...** (More options) → **Connectors**
4. Find **Incoming Webhook** → Click **Configure**
5. If updating existing: Click **Manage** on existing webhook
6. Either regenerate URL or create new webhook
7. Name: `Invoice Agent Notifications`
8. Upload icon (optional)
9. Click **Create** / **Save**
10. **Copy the webhook URL**

### Step 2: Update Function App Settings

```bash
NEW_WEBHOOK="https://outlook.office.com/webhook/YOUR-NEW-WEBHOOK-URL"

az functionapp config appsettings set \
  --name "$FUNC_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --settings TEAMS_WEBHOOK_URL="$NEW_WEBHOOK" \
  --output none

echo "Teams webhook updated"
```

### Step 3: Test New Webhook

```bash
# Send test message
curl -X POST "$NEW_WEBHOOK" \
  -H "Content-Type: application/json" \
  -d '{
    "@type": "MessageCard",
    "@context": "http://schema.org/extensions",
    "themeColor": "00FF00",
    "summary": "Webhook Test",
    "sections": [{
      "activityTitle": "✅ Webhook Rotation Test",
      "activitySubtitle": "Invoice Agent",
      "text": "New webhook is working correctly."
    }]
  }'

# Expected: Returns "1" (success)
echo ""
echo "Check Teams channel for test message"
```

### Step 4: Remove Old Webhook

1. In Teams, go to **Connectors** → **Manage**
2. Find the old webhook configuration
3. Click **Remove** to delete it

---

## Verification Checklist

After any key rotation, verify the following:

### Immediate Checks (Within 5 minutes)

- [ ] Function App restarted successfully
- [ ] Health endpoint returns 200: `curl https://${FUNC_NAME}.azurewebsites.net/api/health`
- [ ] No authentication errors in logs
- [ ] Functions runtime responsive: `/admin/host/status`

### Functional Checks (Within 1 hour)

- [ ] **Graph API**: Send test email to invoice mailbox, verify it's processed
- [ ] **OpenAI**: Check logs for successful vendor extraction from PDF
- [ ] **Teams**: Verify notifications appearing in channel

### Monitoring Checks (24 hours)

- [ ] No elevated error rates in Application Insights
- [ ] Queue processing continuing normally
- [ ] No alerts triggered

### Verification Commands

```bash
# 1. Health check
curl -s "https://${FUNC_NAME}.azurewebsites.net/api/health" | jq .

# 2. Functions runtime status
curl -s "https://${FUNC_NAME}.azurewebsites.net/admin/host/status" \
  -H "x-functions-key: YOUR_ADMIN_KEY" | jq .

# 3. Check for errors in last hour
az monitor app-insights query \
  --app "ai-invoice-agent-prod" \
  --resource-group "$RESOURCE_GROUP" \
  --analytics-query "
    exceptions
    | where timestamp > ago(1h)
    | summarize count() by type
    | order by count_ desc
  "

# 4. Check queue depths (should be low/zero if processing normally)
az storage queue list \
  --account-name "stinvoiceagentprod" \
  --query "[].{name:name, approximateMessageCount:approximateMessageCount}"
```

---

## Rollback Procedures

If rotation causes issues, follow these rollback steps:

### Graph API Client Secret Rollback

If you haven't deleted the old secret yet:

```bash
# Get the old secret value from your secure backup
OLD_SECRET="your-backed-up-old-secret"

# Revert Function App setting
az functionapp config appsettings set \
  --name "$FUNC_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --settings GRAPH_CLIENT_SECRET="$OLD_SECRET" \
  --output none

# Restart
az functionapp restart \
  --name "$FUNC_NAME" \
  --resource-group "$RESOURCE_GROUP"

# Delete the new (broken) secret from Azure AD
az ad app credential delete --id "$APP_ID" --key-id "NEW_KEY_ID"
```

### Azure OpenAI API Key Rollback

Azure OpenAI has two keys (key1, key2). If you rotated key1:

```bash
# Switch to key2
BACKUP_KEY=$(az cognitiveservices account keys list \
  --name "$OPENAI_RESOURCE" \
  --resource-group "$RESOURCE_GROUP" \
  --query "key2" -o tsv)

az functionapp config appsettings set \
  --name "$FUNC_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --settings AZURE_OPENAI_API_KEY="$BACKUP_KEY" \
  --output none

az functionapp restart \
  --name "$FUNC_NAME" \
  --resource-group "$RESOURCE_GROUP"
```

### Teams Webhook Rollback

If you still have the old webhook URL:

```bash
az functionapp config appsettings set \
  --name "$FUNC_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --settings TEAMS_WEBHOOK_URL="$OLD_WEBHOOK_URL" \
  --output none

# No restart needed for Teams webhook (used on-demand)
```

### Emergency: Complete Credential Reset

If credentials are compromised and need immediate invalidation:

```bash
# 1. Invalidate ALL Graph API secrets
az ad app credential list --id "$APP_ID" --query "[].keyId" -o tsv | \
  xargs -I {} az ad app credential delete --id "$APP_ID" --key-id {}

# 2. Create new secret immediately
NEW_SECRET=$(az ad app credential reset --id "$APP_ID" --query "password" -o tsv)

# 3. Update and restart
az functionapp config appsettings set \
  --name "$FUNC_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --settings GRAPH_CLIENT_SECRET="$NEW_SECRET" \
  --output none

az functionapp restart \
  --name "$FUNC_NAME" \
  --resource-group "$RESOURCE_GROUP"
```

---

## Rotation Schedule

### Recommended Schedule

| Month | Week 1 | Week 2 | Week 3 | Week 4 |
|-------|--------|--------|--------|--------|
| Jan, Apr, Jul, Oct | Graph API Secret | - | Azure OpenAI Key | - |
| Feb, May, Aug, Nov | - | - | - | - |
| Mar, Jun, Sep, Dec | - | Teams Webhook | - | - |

### Calendar Reminders

Set up calendar reminders 2 weeks before each rotation:

- **Graph API**: Every 90 days
- **Azure OpenAI**: Every 90 days
- **Teams Webhook**: Every 180 days

### Automation (Future Enhancement)

Consider implementing Azure Automation runbooks for:
- Automatic secret rotation via Azure AD
- Pre-rotation health checks
- Post-rotation verification
- Slack/Teams notification of upcoming rotations

---

## Related Documentation

- [Security Procedures](SECURITY_PROCEDURES.md) - Comprehensive security operations
- [Incident Response](INCIDENT_RESPONSE.md) - Security incident handling
- [Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md) - Common issues and fixes
- [Deployment Guide](../DEPLOYMENT_GUIDE.md) - Deployment procedures

---

**Document Owner:** DevOps Team
**Review Frequency:** Quarterly
**Next Review:** Q1 2026
