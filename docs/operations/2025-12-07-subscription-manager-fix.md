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

## Follow-up Task: Persist Settings in IaC

### Problem
`MAIL_WEBHOOK_URL` and `GRAPH_CLIENT_STATE` were reset during deployment because they're not defined in infrastructure-as-code.

### Task
Add these settings to Bicep templates so they persist across deployments:

| Setting | Storage Location | Value |
|---------|------------------|-------|
| `MAIL_WEBHOOK_URL` | App Settings (Bicep) | `https://${functionAppName}.azurewebsites.net/api/MailWebhook` |
| `GRAPH_CLIENT_STATE` | Key Vault Secret | Random 32-char hex string |

### Files to Modify
```
infrastructure/bicep/modules/functionapp.bicep  - Add app settings
infrastructure/bicep/modules/keyvault.bicep     - Add secret (if not exists)
infrastructure/parameters/prod.json             - Add parameter values
```

### Implementation Notes
1. `MAIL_WEBHOOK_URL` can be constructed dynamically from the function app name
2. `GRAPH_CLIENT_STATE` should be a Key Vault secret with `@Microsoft.KeyVault()` reference
3. Generate the secret once and store in Key Vault (don't regenerate on each deploy)

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
| MAIL_WEBHOOK_URL | Set (needs IaC) |
| GRAPH_CLIENT_STATE | Set (needs IaC) |
