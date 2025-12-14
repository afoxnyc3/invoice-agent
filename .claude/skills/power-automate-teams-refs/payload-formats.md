# Payload Formats Reference

## Table of Contents
1. [Complete Message Envelope](#complete-message-envelope)
2. [Minimal Test Payload](#minimal-test-payload)
3. [Invoice Notification Card](#invoice-notification-card)
4. [Alert Card with Actions](#alert-card-with-actions)
5. [Python Sender Examples](#python-sender-examples)
6. [Curl Test Commands](#curl-test-commands)

## Complete Message Envelope

The **exact** structure required for Power Automate "When a Teams webhook request is received" trigger:

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
        "body": [
          {
            "type": "TextBlock",
            "text": "Your message here",
            "wrap": true
          }
        ]
      }
    }
  ]
}
```

### Required Fields Breakdown

| Field | Value | Notes |
|-------|-------|-------|
| `type` (root) | `"message"` | Exactly this string |
| `attachments` | Array | Must be array, even for single card |
| `contentType` | `"application/vnd.microsoft.card.adaptive"` | Exact string |
| `contentUrl` | `null` | Include as null, not omitted |
| `content.type` | `"AdaptiveCard"` | Case-sensitive |
| `content.version` | `"1.4"` | Use 1.4, not 1.5 or 1.6 |
| `content.$schema` | `"http://adaptivecards.io/schemas/adaptive-card.json"` | Optional but recommended |

## Minimal Test Payload

Use this to verify basic connectivity before adding complexity:

```json
{
  "type": "message",
  "attachments": [
    {
      "contentType": "application/vnd.microsoft.card.adaptive",
      "contentUrl": null,
      "content": {
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
          {
            "type": "TextBlock",
            "text": "Test message",
            "wrap": true
          }
        ]
      }
    }
  ]
}
```

## Invoice Notification Card

Example for invoice processing workflow notifications:

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
        "body": [
          {
            "type": "Container",
            "items": [
              {
                "type": "TextBlock",
                "text": "📧 Invoice Processed",
                "weight": "Bolder",
                "size": "Large",
                "color": "Accent",
                "wrap": true
              }
            ]
          },
          {
            "type": "FactSet",
            "facts": [
              {
                "title": "Invoice #",
                "value": "${invoice_number}"
              },
              {
                "title": "Vendor",
                "value": "${vendor_name}"
              },
              {
                "title": "Amount",
                "value": "${amount}"
              },
              {
                "title": "Due Date",
                "value": "${due_date}"
              },
              {
                "title": "Status",
                "value": "${status}"
              }
            ]
          },
          {
            "type": "TextBlock",
            "text": "Processed at ${timestamp}",
            "size": "Small",
            "isSubtle": true,
            "wrap": true
          }
        ],
        "actions": [
          {
            "type": "Action.OpenUrl",
            "title": "View Invoice",
            "url": "${invoice_url}"
          }
        ]
      }
    }
  ]
}
```

## Alert Card with Actions

For system alerts requiring user action:

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
        "body": [
          {
            "type": "TextBlock",
            "text": "⚠️ Alert: ${alert_title}",
            "weight": "Bolder",
            "size": "Large",
            "color": "Warning",
            "wrap": true
          },
          {
            "type": "TextBlock",
            "text": "${alert_message}",
            "wrap": true
          },
          {
            "type": "FactSet",
            "facts": [
              {
                "title": "Severity",
                "value": "${severity}"
              },
              {
                "title": "Source",
                "value": "${source}"
              },
              {
                "title": "Time",
                "value": "${timestamp}"
              }
            ]
          }
        ],
        "actions": [
          {
            "type": "Action.OpenUrl",
            "title": "View Details",
            "url": "${details_url}"
          },
          {
            "type": "Action.OpenUrl",
            "title": "Acknowledge",
            "url": "${ack_url}"
          }
        ]
      }
    }
  ]
}
```

## Python Sender Examples

### Using requests library

```python
import requests
import json

def send_teams_notification(webhook_url: str, card_content: dict) -> bool:
    """
    Send adaptive card to Power Automate Teams webhook.
    
    Args:
        webhook_url: Power Automate flow trigger URL
        card_content: The adaptive card body (just the content, not envelope)
    
    Returns:
        bool: True if successful
    """
    payload = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "contentUrl": None,
                "content": card_content
            }
        ]
    }
    
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(
            webhook_url,
            data=json.dumps(payload),
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"Failed to send notification: {e}")
        return False


# Example usage
card = {
    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
    "type": "AdaptiveCard",
    "version": "1.4",
    "body": [
        {
            "type": "TextBlock",
            "text": "Invoice INV-001 processed successfully",
            "weight": "Bolder",
            "wrap": True
        },
        {
            "type": "FactSet",
            "facts": [
                {"title": "Amount", "value": "$1,500.00"},
                {"title": "Vendor", "value": "ACME Corp"}
            ]
        }
    ]
}

webhook_url = "https://prod-XX.eastus.logic.azure.com:443/workflows/..."
send_teams_notification(webhook_url, card)
```

### Using urllib3 (no external dependencies)

```python
import urllib3
import json

def send_teams_notification_urllib(webhook_url: str, card_content: dict) -> bool:
    """Send notification using only stdlib + urllib3."""
    http = urllib3.PoolManager()
    
    payload = json.dumps({
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "contentUrl": None,
            "content": card_content
        }]
    })
    
    response = http.request(
        "POST",
        webhook_url,
        body=payload,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status >= 300:
        print(f"Error: {response.status} - {response.data.decode()}")
        return False
    return True
```

## Curl Test Commands

### Windows (cmd)
```cmd
curl.exe -X POST "YOUR_WEBHOOK_URL" ^
  -H "Content-Type: application/json" ^
  -d "{\"type\":\"message\",\"attachments\":[{\"contentType\":\"application/vnd.microsoft.card.adaptive\",\"contentUrl\":null,\"content\":{\"type\":\"AdaptiveCard\",\"version\":\"1.4\",\"body\":[{\"type\":\"TextBlock\",\"text\":\"Test from curl\",\"wrap\":true}]}}]}"
```

### Windows (PowerShell)
```powershell
$body = @{
    type = "message"
    attachments = @(
        @{
            contentType = "application/vnd.microsoft.card.adaptive"
            contentUrl = $null
            content = @{
                type = "AdaptiveCard"
                version = "1.4"
                body = @(
                    @{
                        type = "TextBlock"
                        text = "Test from PowerShell"
                        wrap = $true
                    }
                )
            }
        }
    )
} | ConvertTo-Json -Depth 10

Invoke-RestMethod -Uri "YOUR_WEBHOOK_URL" -Method Post -Body $body -ContentType "application/json"
```

### Linux/macOS
```bash
curl -X POST "YOUR_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "message",
    "attachments": [{
      "contentType": "application/vnd.microsoft.card.adaptive",
      "contentUrl": null,
      "content": {
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [{
          "type": "TextBlock",
          "text": "Test from curl",
          "wrap": true
        }]
      }
    }]
  }'
```

## Common Mistakes

❌ **Wrong: Card at root level**
```json
{
  "type": "AdaptiveCard",
  "body": [...]
}
```

✅ **Correct: Card wrapped in message envelope**
```json
{
  "type": "message",
  "attachments": [{
    "contentType": "application/vnd.microsoft.card.adaptive",
    "content": { "type": "AdaptiveCard", ... }
  }]
}
```

❌ **Wrong: Missing contentUrl**
```json
{
  "contentType": "application/vnd.microsoft.card.adaptive",
  "content": {...}
}
```

✅ **Correct: Include contentUrl as null**
```json
{
  "contentType": "application/vnd.microsoft.card.adaptive",
  "contentUrl": null,
  "content": {...}
}
```

❌ **Wrong: Python True/False in JSON**
```python
"wrap": True  # Python boolean
```

✅ **Correct: Use json.dumps() or lowercase**
```python
json.dumps({"wrap": True})  # Converts to "wrap": true
```
