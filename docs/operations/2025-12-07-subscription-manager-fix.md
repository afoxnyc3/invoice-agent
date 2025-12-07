# SubscriptionManager Fix - December 7, 2025

## Issue Summary

**Symptom:** SubscriptionManager function failing with circuit breaker errors when creating Graph API webhook subscriptions.

**Root Cause:** `MailWebhook/function.json` had `authLevel: "function"` which requires authentication. Graph API's validation request (plain GET without auth) received 401 Unauthorized, causing subscription creation to fail repeatedly and tripping the circuit breaker.

---

## Fix Implemented

### Code Change
**File:** `src/MailWebhook/function.json`
```json
// Changed from:
"authLevel": "function"
// To:
"authLevel": "anonymous"
```

**Commit:** `d4d8b92` - fix: allow anonymous access to MailWebhook for Graph API validation

### Security Note
This is the standard pattern for Microsoft Graph webhooks. Security is maintained via:
- `clientState` validation in notification payloads (code validates this)
- Rate limiting (100 req/min)

### Settings Re-added
After deployment, these settings were manually re-added:
```bash
az functionapp config appsettings set --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --settings "MAIL_WEBHOOK_URL=https://func-invoice-agent-prod.azurewebsites.net/api/MailWebhook"

az functionapp config appsettings set --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --settings "GRAPH_CLIENT_STATE=$(openssl rand -hex 16)"
```

---

## Follow-up Task: Persist Settings in IaC ✅ COMPLETED

**Completed:** December 7, 2025

### Problem
`MAIL_WEBHOOK_URL` and `GRAPH_CLIENT_STATE` were reset during deployment because they're not defined in infrastructure-as-code.

### Solution Implemented

| Setting | Storage Location | Value | Status |
|---------|------------------|-------|--------|
| `MAIL_WEBHOOK_URL` | App Settings (Bicep) | `https://${functionAppName}.azurewebsites.net/api/MailWebhook` | ✅ Added |
| `GRAPH_CLIENT_STATE` | Key Vault Reference | `@Microsoft.KeyVault(...)` | ✅ Added |

### Files Modified
```
infrastructure/bicep/modules/functionapp.bicep  - Added app settings (lines 142-150)
docs/DEPLOYMENT_GUIDE.md                        - Added secret setup instructions
```

### Changes Made
1. **functionapp.bicep**: Added `MAIL_WEBHOOK_URL` as dynamic value constructed from function app name
2. **functionapp.bicep**: Added `GRAPH_CLIENT_STATE` as Key Vault secret reference
3. **DEPLOYMENT_GUIDE.md**: Added setup command for `graph-client-state` secret in Key Vault

### First-Time Setup
For new deployments, add the secret to Key Vault:
```bash
az keyvault secret set --vault-name $KV_NAME --name "graph-client-state" --value "$(openssl rand -hex 16)"
```

---

## Verification Commands

### Test Webhook Validation
```bash
curl -s "https://func-invoice-agent-prod.azurewebsites.net/api/MailWebhook?validationToken=test"
# Expected: "test" with HTTP 200
```

### Trigger SubscriptionManager
```bash
MASTER_KEY=$(az functionapp keys list --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod --query 'masterKey' -o tsv)
curl -X POST "https://func-invoice-agent-prod.azurewebsites.net/admin/functions/SubscriptionManager" \
  -H "x-functions-key: $MASTER_KEY" -H "Content-Type: application/json" -d '{}'
```

### Check Subscription Status
```bash
az monitor app-insights query --app ai-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --analytics-query "traces | where timestamp > ago(5m) | where message contains 'Subscription' | project timestamp, message"
```

### Verify GraphSubscriptions Table
```python
# Python snippet to check active subscriptions
from azure.data.tables import TableServiceClient
service = TableServiceClient.from_connection_string(CONN)
table = service.get_table_client('GraphSubscriptions')
for entity in table.query_entities("IsActive eq true"):
    print(f"ID: {entity['SubscriptionId']}, Expires: {entity['ExpirationDateTime']}")
```

---

## Related Files

| File | Purpose |
|------|---------|
| `src/MailWebhook/__init__.py` | Webhook handler (validates clientState) |
| `src/MailWebhook/function.json` | HTTP trigger config (authLevel) |
| `src/SubscriptionManager/__init__.py` | Creates/renews Graph subscriptions |
| `src/shared/circuit_breaker.py` | Circuit breaker config (60s reset) |
| `src/shared/graph_client.py` | Graph API client |
| `docs/adr/0021-event-driven-webhooks.md` | Architecture decision |

---

## Current State (Post-Fix)

| Component | Status |
|-----------|--------|
| MailWebhook authLevel | `anonymous` (deployed) |
| Webhook validation | Returns 200 + token |
| Graph subscription | Active, auto-renews every 6 days |
| MAIL_WEBHOOK_URL | ✅ Persisted in Bicep |
| GRAPH_CLIENT_STATE | ✅ Persisted in Key Vault reference |
