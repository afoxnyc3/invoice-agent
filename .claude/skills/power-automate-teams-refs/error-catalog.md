# Power Automate Teams Error Catalog

## Table of Contents
1. [Trigger Errors](#trigger-errors)
2. [Parse JSON Errors](#parse-json-errors)
3. [Adaptive Card Errors](#adaptive-card-errors)
4. [Teams Connector Errors](#teams-connector-errors)
5. [Flow Runtime Errors](#flow-runtime-errors)

---

## Trigger Errors

### TriggerInputSchemaMismatch

**Error Message:**
```
The input body for trigger 'manual' of type 'Request' did not match its schema definition. 
Error details: 'Required properties are missing from object: contentType, content.'
```

**Cause:** Payload structure doesn't match expected Teams webhook format.

**Solution:**
1. Ensure payload has `type: "message"` at root
2. Wrap card in `attachments` array
3. Include both `contentType` and `content` in attachment object
4. Include `contentUrl: null`

**Correct Payload:**
```json
{
  "type": "message",
  "attachments": [{
    "contentType": "application/vnd.microsoft.card.adaptive",
    "contentUrl": null,
    "content": {
      "type": "AdaptiveCard",
      "version": "1.4",
      "body": [...]
    }
  }]
}
```

---

### HTTP 400 Bad Request

**Cause:** Malformed JSON or invalid trigger configuration.

**Diagnostic Steps:**
1. Validate JSON at https://jsonlint.com/
2. Check for trailing commas, unclosed brackets
3. Verify webhook URL is complete (includes signature)
4. Confirm Content-Type header is `application/json`

---

### HTTP 401/403 Unauthorized

**Cause:** Authentication mismatch with trigger settings.

**Solutions by Auth Type:**
- **Anyone**: Remove all auth headers
- **Tenant users**: Include Azure AD token in Authorization header
- **Specific users**: Ensure calling user is in allowed list

---

### Expression Stored as Literal String (Common!)

**Symptom:** Flow runs successfully but no card appears in Teams, OR card shows literal text like `triggerBody()?['attachments']?[0]?['content']`

**Cause:** The expression was entered in the Dynamic Content tab instead of Expression tab, storing it as a literal string.

**Solution:**
1. Click the Adaptive Card field in "Post card" action
2. Switch to **Expression** tab (not Dynamic content)
3. Enter: `string(triggerBody()?['attachments']?[0]?['content'])`
4. Click OK, then Save

**Why `string()` is Required:**
- `PostCardToConversation` expects the card as a **JSON string**, not an object
- The trigger body contains the card as a parsed object
- `string()` serializes the object back to JSON string format

**Correct Expression:**
```
string(triggerBody()?['attachments']?[0]?['content'])
```

**Incorrect (literal string, not evaluated):**
```
triggerBody()?['attachments']?[0]?['content']
```

---

## Parse JSON Errors

### JsonReaderException: Unexpected character

**Error Message:**
```
Newtonsoft.Json.JsonReaderException: After parsing a value an unexpected character was 
encountered: {. Path 'body[1].text', line 13, position 88.
```

**Cause:** Special characters breaking JSON structure.

**Common Culprits:**
- Unescaped quotes in text values
- Newline characters (`\n`) not properly escaped
- Backslashes not doubled (`\\`)

**Fix - Escape Dynamic Content:**
```
replace(replace(replace(variables('text'), '\', '\\'), '"', '\"'), char(10), '\n')
```

---

### Schema Validation Failed

**Error Message:**
```
Invalid type. Expected Object but got Array.
```

**Cause:** Schema doesn't match actual data structure.

**Diagnostic:**
1. Go to flow run history
2. Find the Parse JSON action
3. Expand Inputs section
4. Copy the actual input JSON
5. Use "Generate from sample" with this JSON

**Tip:** For variable structures, use permissive schema:
```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": true
}
```

---

### Null Reference in Foreach

**Error Message:**
```
The execution of template action 'Send_each_adaptive_card' failed: the result of the 
evaluation of 'foreach' expression '@triggerOutputs()?['body']?['attachments']' is of type 'Null'.
```

**Cause:** Expected array is null or doesn't exist.

**Fix - Null-safe Array Access:**
```
if(
  empty(triggerBody()?['attachments']),
  createArray(),
  triggerBody()?['attachments']
)
```

---

## Adaptive Card Errors

### "We're sorry, this card couldn't be displayed"

**Causes:**
1. Schema version unsupported (Teams supports up to 1.4 reliably)
2. Unsupported element type
3. Invalid image URL
4. Card exceeds size limits

**Diagnostic Checklist:**
- [ ] Version is "1.4" not "1.5" or "1.6"
- [ ] All image URLs are HTTPS and publicly accessible
- [ ] No unsupported elements (Table, RichTextBlock with complex features)
- [ ] Card is under 28KB total

**Fix - Downgrade Version:**
```json
{
  "type": "AdaptiveCard",
  "version": "1.4",  // Not 1.5 or 1.6
  ...
}
```

---

### Card Posts but Looks Wrong

**Cause:** Style/formatting issues.

**Common Fixes:**

1. **Text not wrapping:**
   ```json
   {"type": "TextBlock", "text": "...", "wrap": true}
   ```

2. **Image not showing:**
   - Verify URL works in browser
   - Use HTTPS (not HTTP)
   - Check image isn't behind auth

3. **Layout broken:**
   - Use explicit `width` on columns
   - Avoid deeply nested containers (max 3 levels)

---

### Action.Submit Returns Error

**Error Message:** "Something went wrong, please try again"

**Cause:** 
- Using `Post adaptive card in a chat or channel` without wait
- Card actions without proper flow handler

**Fix:** Use `Post adaptive card and wait for a response` action instead.

---

## Teams Connector Errors

### Request Entity Too Large

**Error Message:**
```
Request Entity too large
```

**Cause:** Payload exceeds ~28KB limit.

**Solutions:**
1. Remove inline base64 images, use URLs instead
2. Reduce number of items in FactSet/ColumnSet
3. Split into multiple cards
4. Summarize long text content

**Check Size in Python:**
```python
import json
payload_size = len(json.dumps(payload).encode('utf-8'))
print(f"Payload size: {payload_size} bytes")
if payload_size > 28000:
    print("Warning: May exceed Teams limit")
```

---

### Rate Limiting

**Error Message:**
```
Microsoft Teams endpoint returned HTTP error 429
```

**Cause:** Too many requests in short period.

**Limits:**
- 100 API calls per 60 seconds per connection
- 25 non-GET requests per 5 minutes (for bot operations)

**Solutions:**
1. Implement exponential backoff
2. Batch notifications where possible
3. Add delays between requests

```python
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))
```

---

### Channel/Team Not Found

**Error Message:**
```
Team not found
```

**Causes:**
1. Flow connection using wrong account
2. User doesn't have access to team/channel
3. Team/channel was deleted or renamed

**Fix:**
1. Re-authenticate flow connection
2. Verify team/channel IDs are current
3. Use dynamic content from Teams trigger instead of hardcoded IDs

---

## Flow Runtime Errors

### Scope Failed

**Symptom:** Actions after scope don't run.

**Debug Pattern:**
```
Scope (Try)
  └─ Action 1
  └─ Action 2 (fails here)
  └─ Action 3 (never runs)
Scope (Catch)  [Configure run after: has failed]
  └─ Get failure details
  └─ Send alert
```

**Get Error Details in Catch:**
```
result('Scope_-_Try')
```

Access specific failure:
```
first(body('Filter_Failed_Actions'))?['error']?['message']
```

---

### Timeout Exceeded

**Error Message:**
```
The operation timed out
```

**Cause:** Action takes longer than allowed duration.

**Limits:**
- HTTP actions: 120 seconds default
- Premium: Up to 230 seconds

**Solutions:**
1. Reduce payload size
2. Add retry with shorter timeouts
3. Use async pattern with callback

---

### Concurrency Conflicts

**Error Message:**
```
The workflow with id X was invoked more than Y times simultaneously
```

**Fix - Enable Concurrency Control:**
1. Click trigger settings (⋮ menu)
2. Enable Concurrency Control
3. Set Degree of Parallelism (1 = sequential)

---

## Diagnostic Commands

### Export Flow for Analysis
1. Open flow in edit mode
2. Click Export → Package (.zip)
3. Extract and examine definition.json

### Key Elements to Check in definition.json
```json
{
  "definition": {
    "$schema": "...",
    "triggers": {
      "manual": {
        "type": "Request",
        "kind": "Teams",
        "inputs": {
          "schema": {...}  // Check this matches your payload
        }
      }
    },
    "actions": {
      "Parse_JSON": {
        "inputs": {
          "schema": {...}  // And this
        }
      }
    }
  }
}
```

### Flow Run History Analysis
1. Go to flow → Run history
2. Click failed run
3. Expand each action to see:
   - **Inputs**: What was received
   - **Outputs**: What was produced
   - **Error**: Specific failure reason

---

## Quick Reference: Status Codes

| Code | Meaning | Common Cause |
|------|---------|--------------|
| 200 | Success | - |
| 202 | Accepted (async) | Webhook queued |
| 400 | Bad Request | Invalid JSON |
| 401 | Unauthorized | Missing/bad auth |
| 403 | Forbidden | No permission |
| 404 | Not Found | Bad URL/ID |
| 429 | Too Many Requests | Rate limited |
| 500 | Internal Error | Flow failure |
| 502 | Bad Gateway | Upstream error |
