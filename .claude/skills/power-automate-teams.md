---
name: power-automate-teams
description: Expert-level Power Automate workflow troubleshooting and Teams notification integration. Use this skill when working with Power Automate HTTP triggers, Teams adaptive cards, webhook migrations from Office 365 Connectors, JSON payload formatting, Parse JSON actions, or debugging flow failures. Covers the "When a Teams webhook request is received" trigger, adaptive card schema validation, and common error patterns.
---

# Power Automate Teams Integration

## Core Workflow: HTTP → Teams Notification

The modern replacement for deprecated Office 365 Connectors uses Power Automate's "When a Teams webhook request is received" trigger. Key constraints:

1. **Trigger Type**: HTTP POST only (no GET)
2. **Payload Format**: Must follow exact schema (see [payload-formats.md](references/payload-formats.md))
3. **Card Version**: Use Adaptive Cards v1.4 (Teams bugs in v1.5+)
4. **Auth Options**: Anyone, Tenant users, or Specific users

## Debugging Workflow

1. **Validate JSON locally** → Run `scripts/validate_adaptive_card.py`
2. **Test with minimal card** → Run `scripts/test_webhook.py` 
3. **Check flow run history** → Examine inputs/outputs at each action
4. **Review Parse JSON schema** → Most failures here

## Common Error Patterns

| Error | Cause | Fix |
|-------|-------|-----|
| `TriggerInputSchemaMismatch` | Missing `type`, `attachments`, `contentType`, or `content` | Wrap card in message envelope |
| `JsonReaderException: unexpected character` | Quotes, escaping, trailing commas | Validate JSON, escape special chars |
| `We're sorry, this card couldn't be displayed` | Schema version mismatch or unsupported element | Downgrade to v1.4, remove unsupported features |
| `Request Entity too large` | Payload >28KB | Reduce content, externalize images |
| `Null result in foreach` | Parse JSON expecting array, got object | Fix schema or use `createArray()` |

## Payload Structure (Required Format)

```json
{
  "type": "message",
  "attachments": [
    {
      "contentType": "application/vnd.microsoft.card.adaptive",
      "contentUrl": null,
      "content": {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [...]
      }
    }
  ]
}
```

**Critical**: 
- `"type": "message"` at root level
- `"contentType": "application/vnd.microsoft.card.adaptive"` exactly
- `"contentUrl": null` (not omitted)
- Card inside `content`, not at root

## Parse JSON Schema for Trigger Output

When processing trigger body in subsequent actions:

```json
{
  "type": "object",
  "properties": {
    "type": { "type": "string" },
    "attachments": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "contentType": { "type": "string" },
          "content": { "type": "object" }
        }
      }
    }
  }
}
```

## Flow Architecture Patterns

**Pattern A: Direct Card Post (Simple)**
```
Trigger → Post adaptive card in chat or channel
```

**Pattern B: Parse and Transform (Dynamic)**
```
Trigger → Parse JSON → Compose (build card) → Post card
```

**Pattern C: Error-Handled (Production)**
```
Trigger → Scope (Try) → [Parse JSON → Post Card]
                      → Scope (Catch) → [Log error → Notify admin]
```

## Reference Files

- **Payload Formats**: [power-automate-teams-refs/payload-formats.md](power-automate-teams-refs/payload-formats.md) - Complete JSON schemas
- **Error Catalog**: [power-automate-teams-refs/error-catalog.md](power-automate-teams-refs/error-catalog.md) - Detailed error troubleshooting
- **Card Templates**: [power-automate-teams-refs/card-templates.md](power-automate-teams-refs/card-templates.md) - Reusable card designs

## Scripts

- `scripts/power-automate/validate_adaptive_card.py` - Local JSON/schema validation
- `scripts/power-automate/test_webhook.py` - Send test payload to workflow URL
- `scripts/power-automate/diagnose_flow.py` - Parse flow export for common issues

## Quick Fixes

**Escape special characters in dynamic content:**
```
replace(replace(variables('text'), '\', '\\'), '"', '\"')
```

**Force array for Apply to Each:**
```
if(equals(length(body('Parse_JSON')?['attachments']), 0), 
   createArray(), 
   body('Parse_JSON')?['attachments'])
```

**Extract card content from trigger:**
```
triggerBody()?['attachments']?[0]?['content']
```

## Adaptive Card Best Practices

1. **Version**: Always use `"version": "1.4"` for Teams
2. **Images**: Use HTTPS URLs only, test in browser first
3. **Text**: Set `"wrap": true` on all TextBlock elements
4. **Actions**: Limit to 6 actions maximum
5. **FactSet**: Keep facts ≤10 items for readability
6. **Schema**: Include `"$schema": "http://adaptivecards.io/schemas/adaptive-card.json"`

## Testing Checklist

1. [ ] JSON validates at https://adaptivecards.io/designer/ (select Microsoft Teams host)
2. [ ] Payload wrapped in message envelope
3. [ ] Test with curl/Postman before Python integration
4. [ ] Check flow run history for input/output at each step
5. [ ] Verify Parse JSON schema matches actual input structure
