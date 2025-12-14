# Teams Power Automate Integration Guide

## Overview

The Invoice Agent sends notifications to Microsoft Teams via Power Automate's "When a Teams webhook request is received" trigger. This guide covers setup, configuration, and troubleshooting.

## Architecture

```
Notify Function → HTTP POST → Power Automate Flow → Teams Channel
     │                              │
     │ Adaptive Card v1.4           │ string() serialization
     │ in message envelope          │
     └──────────────────────────────┘
```

## Payload Format

The Notify function sends Adaptive Cards wrapped in a Power Automate message envelope:

```json
{
  "type": "message",
  "attachments": [{
    "contentType": "application/vnd.microsoft.card.adaptive",
    "contentUrl": null,
    "content": {
      "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
      "type": "AdaptiveCard",
      "version": "1.4",
      "body": [
        {"type": "TextBlock", "text": "✅ Invoice Processed", "weight": "Bolder", "wrap": true},
        {"type": "FactSet", "facts": [
          {"title": "Vendor", "value": "Adobe Inc"},
          {"title": "Transaction Id", "value": "01JCK3Q7H8ZVXN3BARC9GWAEZM"}
        ]}
      ]
    }
  }]
}
```

**Critical fields:**
- `type: "message"` - Required at root level
- `contentType: "application/vnd.microsoft.card.adaptive"` - Exact string
- `contentUrl: null` - Must be present and null
- `version: "1.4"` - Use 1.4 (Teams has bugs in 1.5+)

---

## Power Automate Flow Setup

### Step 1: Create the Flow

1. Go to https://make.powerautomate.com/
2. Click **+ Create** → **Instant cloud flow**
3. Name: "Invoice Agent Teams Notifications"
4. Select trigger: **"When a Teams webhook request is received"**
5. Click **Create**

### Step 2: Configure the Trigger

1. Click the trigger to expand settings
2. Set **Who can trigger the flow**: Choose based on security requirements
   - "Anyone" - No authentication (simplest)
   - "Specific users in my tenant" - Requires Azure AD token
3. Copy the **HTTP POST URL** - this is your webhook URL

### Step 3: Add Post Card Action

1. Click **+ New step**
2. Search for "Post card in a chat or channel"
3. Select **Post card in a chat or channel (V2)**
4. Configure:
   - **Post as**: Flow bot
   - **Post in**: Channel
   - **Team**: Select your team
   - **Channel**: Select target channel

### Step 4: Configure the Adaptive Card Expression (CRITICAL)

This is where most issues occur. The card content must be extracted and serialized.

1. Click the **Adaptive Card** field
2. Switch to the **Expression** tab (not Dynamic content)
3. Enter exactly:
   ```
   string(triggerBody()?['attachments']?[0]?['content'])
   ```
4. Click **OK**
5. **Save** the flow

### Common Configuration Errors

| Error | Cause | Fix |
|-------|-------|-----|
| Expression stored as literal string | Used Dynamic content tab | Switch to Expression tab |
| "Card couldn't be displayed" | Raw object instead of string | Use `string()` wrapper |
| No flow run history | Wrong auth setting or bad URL | Check trigger authentication |
| 400 Bad Request | Malformed JSON or missing fields | Validate with utility script |

---

## Azure Configuration

### Key Vault Secret

The webhook URL is stored in Key Vault:
- **Secret name**: `teams-webhook-url`
- **Value**: Full Power Automate HTTP POST URL

```bash
# Set the secret
az keyvault secret set \
  --vault-name kv-invoice-agent-prod \
  --name teams-webhook-url \
  --value "https://prod-XX.westus.logic.azure.com:443/workflows/..."
```

### Function App Setting

The Function App references the Key Vault secret:
```json
"TEAMS_WEBHOOK_URL": "@Microsoft.KeyVault(SecretUri=https://kv-invoice-agent-prod.vault.azure.net/secrets/teams-webhook-url)"
```

---

## Testing

### Using the Test Script

```bash
# Test with your webhook URL
python scripts/power-automate/test_webhook.py "YOUR_WEBHOOK_URL" --message "Test notification"

# Use environment variable
export TEAMS_WEBHOOK_URL="YOUR_WEBHOOK_URL"
python scripts/power-automate/test_webhook.py --message "Test from Invoice Agent"

# Verbose mode for debugging
python scripts/power-automate/test_webhook.py "$TEAMS_WEBHOOK_URL" --verbose
```

### Validate Payload Format

```bash
# Validate a JSON payload file
python scripts/power-automate/validate_adaptive_card.py payload.json

# Validate inline JSON
python scripts/power-automate/validate_adaptive_card.py --payload '{"type": "message", ...}'
```

### Diagnose Flow Issues

If you export your flow definition:
```bash
python scripts/power-automate/diagnose_flow.py definition.json
```

---

## Troubleshooting

### No Flow Run History

**Cause**: Request never reached Power Automate

**Check**:
1. Verify TEAMS_WEBHOOK_URL in Function App settings
2. Verify Key Vault secret has correct value
3. Check Function App has Key Vault access
4. Test webhook URL directly with curl

### Flow Runs But No Message

**Cause**: Card not displayed in Teams

**Check**:
1. Verify Expression uses `string()` wrapper
2. Verify card content uses version "1.4"
3. Check for unsupported Adaptive Card elements
4. Look at flow run history → Post card action outputs

### HTTP 400 Bad Request

**Cause**: Malformed payload

**Check**:
1. Run `validate_adaptive_card.py` on your payload
2. Ensure `contentUrl: null` is present
3. Verify JSON is valid (no trailing commas)

### HTTP 202 Accepted But No Message

**Cause**: Flow accepted but failed internally

**Check**:
1. Check Power Automate flow run history
2. Look for errors in Post card action
3. Verify Team/Channel selection is valid

---

## Error Logging

The Notify function logs detailed errors to Application Insights:

| Error Type | Log Message | Debugging Info |
|------------|-------------|----------------|
| Timeout | `Teams webhook timeout` | Network/latency issue |
| Connection | `Teams webhook connection failed` | DNS/firewall issue |
| HTTP 4xx | `Teams webhook HTTP 4xx` | Payload format issue |
| HTTP 5xx | `Teams webhook HTTP 5xx` | Power Automate issue |

Query logs:
```bash
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "traces | where message contains 'Teams webhook' | project timestamp, message"
```

---

## Related Documentation

- [TROUBLESHOOTING_GUIDE.md](../operations/TROUBLESHOOTING_GUIDE.md#teams-notifications) - General troubleshooting
- [ARCHITECTURE.md](../ARCHITECTURE.md#teams-notification-formats) - Payload format details
- [ADR-0005](../adr/0005-simple-teams-webhooks.md) - Design decision
- `src/Notify/__init__.py` - Implementation source code
