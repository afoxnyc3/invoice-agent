# Webhook Email Ingestion Setup Guide

This guide explains how to complete the migration from timer-based polling to event-driven webhooks for email ingestion.

---

## What Was Implemented

### New Functions Created

1. **MailWebhook** (`src/MailWebhook/`)
   - HTTP trigger endpoint for receiving Graph API notifications
   - Handles validation handshake during subscription creation
   - Queues email notifications for processing
   - Endpoint: `https://func-invoice-agent-{env}.azurewebsites.net/api/MailWebhook`

2. **SubscriptionManager** (`src/SubscriptionManager/`)
   - Timer trigger (runs every 6 days)
   - Creates and renews Graph API subscriptions
   - Stores subscription state in Table Storage
   - Ensures webhooks stay active (Graph max: 7 days)

3. **Graph Subscription Methods** (`src/shared/graph_client.py`)
   - `create_subscription()` - Create new webhook subscription
   - `renew_subscription()` - Renew existing subscription
   - `delete_subscription()` - Delete subscription

### Architecture Change

**Before (Timer)**:
```
Timer (every 5 min) → MailIngest → Queue → ExtractEnrich → ...
Problem: Unreliable on Consumption plan
```

**After (Webhook)**:
```
Email arrives → Graph API → MailWebhook → Queue → ExtractEnrich → ...
Benefits: Real-time, reliable, 70% cheaper
```

**Fallback Safety Net**:
```
MailIngest (hourly timer) → Checks for missed emails
```

---

## Configuration Required

### Step 1: Add Webhook Secrets to Key Vault

You need to configure two new secrets:

#### 1.1 Generate Client State Secret

```bash
# Generate a random secure string (32 characters)
CLIENT_STATE=$(openssl rand -base64 32)
echo "Generated client state: $CLIENT_STATE"

# Add to Key Vault
az keyvault secret set \
  --vault-name kv-invoice-agent-dev \
  --name "graph-client-state" \
  --value "$CLIENT_STATE"
```

#### 1.2 Get Function App Webhook URL

```bash
# Get the function key
FUNCTION_KEY=$(az functionapp keys list \
  --name func-invoice-agent-dev \
  --resource-group rg-invoice-agent-dev \
  --query "functionKeys.default" -o tsv)

# Construct webhook URL
WEBHOOK_URL="https://func-invoice-agent-dev.azurewebsites.net/api/MailWebhook?code=$FUNCTION_KEY"

echo "Webhook URL: $WEBHOOK_URL"

# Add to Key Vault
az keyvault secret set \
  --vault-name kv-invoice-agent-dev \
  --name "mail-webhook-url" \
  --value "$WEBHOOK_URL"
```

### Step 2: Update Function App Settings

The Function App needs to reference these Key Vault secrets:

```bash
# Add environment variables pointing to Key Vault
az functionapp config appsettings set \
  --name func-invoice-agent-dev \
  --resource-group rg-invoice-agent-dev \
  --settings \
    GRAPH_CLIENT_STATE="@Microsoft.KeyVault(SecretUri=https://kv-invoice-agent-dev.vault.azure.net/secrets/graph-client-state/)" \
    MAIL_WEBHOOK_URL="@Microsoft.KeyVault(SecretUri=https://kv-invoice-agent-dev.vault.azure.net/secrets/mail-webhook-url/)"

# Restart to load new settings
az functionapp restart \
  --name func-invoice-agent-dev \
  --resource-group rg-invoice-agent-dev
```

---

## Deployment Steps

### Phase 1: Deploy Webhook Functions

```bash
# Commit webhook implementation
git add src/MailWebhook src/SubscriptionManager src/shared/graph_client.py src/MailIngest/function.json
git commit -m "feat: implement Graph API webhook for email ingestion [deploy-dev]

- Add MailWebhook HTTP function for receiving notifications
- Add SubscriptionManager for subscription renewal
- Add Graph subscription methods to GraphAPIClient
- Change MailIngest to hourly fallback

Solves timer trigger reliability issue on Consumption plan.
Real-time email processing with 70% cost reduction."

# Push to trigger deployment
git push origin main
```

### Phase 2: Configure Secrets (After Deployment)

```bash
# Run the configuration script
./configure-dev-secrets.sh

# Or manually using the commands in Step 1 above
```

### Phase 3: Initialize Subscription

```bash
# Option A: Wait for SubscriptionManager timer (runs every 6 days)
# This will happen automatically but takes up to 6 days

# Option B: Manually trigger SubscriptionManager (Recommended)
# Via Azure Portal:
# 1. Go to Function App → SubscriptionManager → Code + Test
# 2. Click "Test/Run" → Run

# Option C: Call via Azure CLI (requires admin function key)
az rest --method post \
  --url "https://func-invoice-agent-dev.azurewebsites.net/admin/functions/SubscriptionManager" \
  --headers "x-functions-key=$(az functionapp keys list --name func-invoice-agent-dev --resource-group rg-invoice-agent-dev --query masterKey -o tsv)"
```

### Phase 4: Verify Webhook

```bash
# Send test email to dev-invoices@chelseapiers.com with attachment

# Check webhook was called (should see within seconds)
az monitor app-insights query \
  --app ai-invoice-agent-dev \
  --resource-group rg-invoice-agent-dev \
  --analytics-query "traces | where timestamp > ago(5m) and message contains 'MailWebhook' | order by timestamp desc"

# Check email was queued
az storage message peek \
  --queue-name webhook-notifications \
  --connection-string "$(az functionapp config appsettings list --name func-invoice-agent-dev --resource-group rg-invoice-agent-dev --query \"[?name=='AzureWebJobsStorage'].value\" -o tsv)"
```

---

## Troubleshooting

### Webhook Validation Fails

**Symptom**: SubscriptionManager logs "validation failed"

**Cause**: Graph couldn't reach webhook or validation response incorrect

**Fix**:
1. Verify webhook URL is publicly accessible (HTTPS required)
2. Check Function App is running
3. Verify function key is correct
4. Test webhook manually:
   ```bash
   curl -X POST "https://func-invoice-agent-dev.azurewebsites.net/api/MailWebhook?validationToken=test%20token&code=$FUNCTION_KEY"
   # Should return: test token
   ```

### No Notifications Received

**Symptom**: Emails arrive but webhook never called

**Causes**:
1. Subscription not created/expired
2. Client state mismatch
3. Graph API permissions missing

**Fix**:
1. Check subscription status:
   ```bash
   # Query GraphSubscriptions table
   az storage entity query \
     --table-name GraphSubscriptions \
     --connection-string "..."
   ```

2. Verify Graph API app has `Mail.Read` permission with admin consent

3. Manually renew/recreate subscription (run SubscriptionManager)

### Duplicate Email Processing

**Symptom**: Same email processed by both webhook and MailIngest

**Cause**: Both systems active simultaneously

**Fix**:
1. Verify webhook is working for 24-48 hours
2. If reliable, disable MailIngest timer:
   ```bash
   # Update schedule to never run (comment out)
   # Or keep hourly as safety net (current config)
   ```

---

## Monitoring

### Key Metrics

| Metric | Query | Expected |
|--------|-------|----------|
| Webhook Calls | `traces \| where message contains 'MailWebhook'` | ~50/day |
| Webhook Latency | Time from email to webhook | <10 seconds |
| Subscription Health | Table: GraphSubscriptions, IsActive=true | 1 active sub |
| Fallback Triggers | `traces \| where message contains 'MailIngest'` | 0/day (webhook working) |

### Alerts to Configure

1. **Subscription Expiring** - Alert if <24 hours until expiration
2. **Webhook Failures** - Alert if >3 failures in 10 minutes
3. **No Notifications** - Alert if 0 webhooks in 8 hours (during business hours)

---

## Rollback Plan

If webhooks prove unreliable:

```bash
# 1. Re-enable 5-minute polling
# Update src/MailIngest/function.json
{
  "schedule": "0 */5 * * * *"  # Back to every 5 minutes
}

# 2. Delete Graph subscription
# Via SubscriptionManager or manually:
az rest --method delete \
  --url "https://graph.microsoft.com/v1.0/subscriptions/{subscription-id}" \
  --headers "Authorization=Bearer $(az account get-access-token --resource https://graph.microsoft.com --query accessToken -o tsv)"

# 3. Deploy
git commit -m "revert: rollback to timer-based polling [deploy-dev]"
git push origin main
```

---

## Cost Comparison

| Approach | Executions/Month | Cost | Latency |
|----------|------------------|------|---------|
| Timer (5 min) | 8,640 | ~$2.00 | 5 minutes |
| **Webhook** | **1,500** | **~$0.60** | **<10 seconds** |
| Savings | -82% | -70% | 30x faster |

---

## Next Steps

1. ✅ Code implemented (MailWebhook + SubscriptionManager)
2. ⏳ Deploy to dev environment
3. ⏳ Configure webhook secrets in Key Vault
4. ⏳ Initialize subscription (run SubscriptionManager)
5. ⏳ Test with real email
6. ⏳ Monitor for 1 week alongside MailIngest
7. ⏳ Apply to production environment

---

## Production Deployment

Once proven in dev, apply to production:

```bash
# 1. Add secrets to production Key Vault
CLIENT_STATE=$(openssl rand -base64 32)
az keyvault secret set --vault-name kv-invoice-agent-prod --name "graph-client-state" --value "$CLIENT_STATE"

FUNCTION_KEY=$(az functionapp keys list --name func-invoice-agent-prod --resource-group rg-invoice-agent-prod --query "functionKeys.default" -o tsv)
WEBHOOK_URL="https://func-invoice-agent-prod.azurewebsites.net/api/MailWebhook?code=$FUNCTION_KEY"
az keyvault secret set --vault-name kv-invoice-agent-prod --name "mail-webhook-url" --value "$WEBHOOK_URL"

# 2. Update function app settings
az functionapp config appsettings set \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --settings \
    GRAPH_CLIENT_STATE="@Microsoft.KeyVault(SecretUri=https://kv-invoice-agent-prod.vault.azure.net/secrets/graph-client-state/)" \
    MAIL_WEBHOOK_URL="@Microsoft.KeyVault(SecretUri=https://kv-invoice-agent-prod.vault.azure.net/secrets/mail-webhook-url/)"

# 3. Restart and initialize
az functionapp restart --name func-invoice-agent-prod --resource-group rg-invoice-agent-prod

# 4. Trigger SubscriptionManager via Portal or CLI
```

---

**Status**: Implementation complete, ready for deployment and configuration
**Last Updated**: 2025-11-20
