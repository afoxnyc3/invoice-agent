# Adaptive Card Templates for Teams

## Table of Contents
1. [Basic Notification](#basic-notification)
2. [Invoice Processed](#invoice-processed)
3. [Email Processing Result](#email-processing-result)
4. [Error Alert](#error-alert)
5. [Status Update](#status-update)
6. [Approval Request](#approval-request)

---

## Basic Notification

Minimal card for simple notifications:

```json
{
  "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
  "type": "AdaptiveCard",
  "version": "1.4",
  "body": [
    {
      "type": "TextBlock",
      "text": "📬 New Notification",
      "weight": "Bolder",
      "size": "Medium",
      "wrap": true
    },
    {
      "type": "TextBlock",
      "text": "Your message content here.",
      "wrap": true
    }
  ]
}
```

---

## Invoice Processed

For invoice/document processing notifications:

```json
{
  "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
  "type": "AdaptiveCard",
  "version": "1.4",
  "body": [
    {
      "type": "Container",
      "style": "emphasis",
      "items": [
        {
          "type": "ColumnSet",
          "columns": [
            {
              "type": "Column",
              "width": "auto",
              "items": [
                {
                  "type": "TextBlock",
                  "text": "📄",
                  "size": "Large"
                }
              ]
            },
            {
              "type": "Column",
              "width": "stretch",
              "items": [
                {
                  "type": "TextBlock",
                  "text": "Invoice Processed",
                  "weight": "Bolder",
                  "size": "Large",
                  "color": "Good",
                  "wrap": true
                },
                {
                  "type": "TextBlock",
                  "text": "Invoice ${invoice_number} has been successfully processed",
                  "size": "Small",
                  "isSubtle": true,
                  "wrap": true
                }
              ]
            }
          ]
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
          "value": "✓ Processed"
        }
      ]
    },
    {
      "type": "TextBlock",
      "text": "Processed at ${timestamp}",
      "size": "Small",
      "isSubtle": true,
      "wrap": true,
      "separator": true
    }
  ],
  "actions": [
    {
      "type": "Action.OpenUrl",
      "title": "View Invoice",
      "url": "${invoice_url}"
    },
    {
      "type": "Action.OpenUrl",
      "title": "View All Invoices",
      "url": "${dashboard_url}"
    }
  ]
}
```

---

## Email Processing Result

For email/inbox processing agent notifications:

```json
{
  "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
  "type": "AdaptiveCard",
  "version": "1.4",
  "body": [
    {
      "type": "Container",
      "style": "accent",
      "items": [
        {
          "type": "TextBlock",
          "text": "📧 Email Processing Complete",
          "weight": "Bolder",
          "size": "Large",
          "color": "Light",
          "wrap": true
        }
      ],
      "bleed": true
    },
    {
      "type": "TextBlock",
      "text": "Summary",
      "weight": "Bolder",
      "size": "Medium",
      "wrap": true,
      "spacing": "Medium"
    },
    {
      "type": "FactSet",
      "facts": [
        {
          "title": "Emails Processed",
          "value": "${emails_count}"
        },
        {
          "title": "Invoices Found",
          "value": "${invoices_count}"
        },
        {
          "title": "Attachments Saved",
          "value": "${attachments_count}"
        },
        {
          "title": "Errors",
          "value": "${errors_count}"
        }
      ]
    },
    {
      "type": "Container",
      "items": [
        {
          "type": "TextBlock",
          "text": "Details",
          "weight": "Bolder",
          "size": "Medium",
          "wrap": true
        },
        {
          "type": "TextBlock",
          "text": "${details_text}",
          "wrap": true,
          "size": "Small"
        }
      ],
      "separator": true,
      "spacing": "Medium"
    }
  ],
  "actions": [
    {
      "type": "Action.OpenUrl",
      "title": "View Processing Log",
      "url": "${log_url}"
    }
  ]
}
```

---

## Error Alert

For error/failure notifications with urgency:

```json
{
  "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
  "type": "AdaptiveCard",
  "version": "1.4",
  "body": [
    {
      "type": "Container",
      "style": "attention",
      "items": [
        {
          "type": "ColumnSet",
          "columns": [
            {
              "type": "Column",
              "width": "auto",
              "items": [
                {
                  "type": "TextBlock",
                  "text": "⚠️",
                  "size": "Large"
                }
              ]
            },
            {
              "type": "Column",
              "width": "stretch",
              "items": [
                {
                  "type": "TextBlock",
                  "text": "Error Alert",
                  "weight": "Bolder",
                  "size": "Large",
                  "wrap": true
                }
              ]
            }
          ]
        }
      ],
      "bleed": true
    },
    {
      "type": "TextBlock",
      "text": "${error_title}",
      "weight": "Bolder",
      "wrap": true,
      "spacing": "Medium"
    },
    {
      "type": "TextBlock",
      "text": "${error_message}",
      "wrap": true,
      "color": "Attention"
    },
    {
      "type": "FactSet",
      "facts": [
        {
          "title": "Component",
          "value": "${component}"
        },
        {
          "title": "Severity",
          "value": "${severity}"
        },
        {
          "title": "Time",
          "value": "${timestamp}"
        },
        {
          "title": "Trace ID",
          "value": "${trace_id}"
        }
      ],
      "separator": true
    }
  ],
  "actions": [
    {
      "type": "Action.OpenUrl",
      "title": "View Logs",
      "url": "${logs_url}"
    },
    {
      "type": "Action.OpenUrl",
      "title": "Acknowledge",
      "url": "${ack_url}"
    }
  ]
}
```

---

## Status Update

For progress/status updates:

```json
{
  "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
  "type": "AdaptiveCard",
  "version": "1.4",
  "body": [
    {
      "type": "TextBlock",
      "text": "🔄 ${process_name} Status",
      "weight": "Bolder",
      "size": "Large",
      "wrap": true
    },
    {
      "type": "ColumnSet",
      "columns": [
        {
          "type": "Column",
          "width": "stretch",
          "items": [
            {
              "type": "TextBlock",
              "text": "Status",
              "weight": "Bolder",
              "size": "Small",
              "wrap": true
            },
            {
              "type": "TextBlock",
              "text": "${status}",
              "size": "ExtraLarge",
              "color": "${status_color}",
              "wrap": true
            }
          ]
        },
        {
          "type": "Column",
          "width": "stretch",
          "items": [
            {
              "type": "TextBlock",
              "text": "Progress",
              "weight": "Bolder",
              "size": "Small",
              "wrap": true
            },
            {
              "type": "TextBlock",
              "text": "${progress}%",
              "size": "ExtraLarge",
              "wrap": true
            }
          ]
        }
      ]
    },
    {
      "type": "FactSet",
      "facts": [
        {
          "title": "Started",
          "value": "${start_time}"
        },
        {
          "title": "Duration",
          "value": "${duration}"
        },
        {
          "title": "Items Processed",
          "value": "${items_processed}/${total_items}"
        }
      ],
      "separator": true
    },
    {
      "type": "TextBlock",
      "text": "${current_step}",
      "wrap": true,
      "isSubtle": true,
      "separator": true
    }
  ]
}
```

---

## Approval Request

For workflows requiring user approval (use with "wait for response"):

```json
{
  "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
  "type": "AdaptiveCard",
  "version": "1.4",
  "body": [
    {
      "type": "Container",
      "style": "emphasis",
      "items": [
        {
          "type": "TextBlock",
          "text": "🔔 Approval Required",
          "weight": "Bolder",
          "size": "Large",
          "wrap": true
        }
      ]
    },
    {
      "type": "TextBlock",
      "text": "${request_title}",
      "weight": "Bolder",
      "size": "Medium",
      "wrap": true,
      "spacing": "Medium"
    },
    {
      "type": "TextBlock",
      "text": "${request_description}",
      "wrap": true
    },
    {
      "type": "FactSet",
      "facts": [
        {
          "title": "Requested by",
          "value": "${requester_name}"
        },
        {
          "title": "Amount",
          "value": "${amount}"
        },
        {
          "title": "Category",
          "value": "${category}"
        },
        {
          "title": "Due Date",
          "value": "${due_date}"
        }
      ],
      "separator": true
    },
    {
      "type": "Input.Text",
      "id": "comment",
      "placeholder": "Add a comment (optional)",
      "isMultiline": true
    }
  ],
  "actions": [
    {
      "type": "Action.Submit",
      "title": "✓ Approve",
      "style": "positive",
      "data": {
        "action": "approve"
      }
    },
    {
      "type": "Action.Submit",
      "title": "✗ Reject",
      "style": "destructive",
      "data": {
        "action": "reject"
      }
    },
    {
      "type": "Action.OpenUrl",
      "title": "View Details",
      "url": "${details_url}"
    }
  ]
}
```

---

## Usage Notes

### Variable Substitution

Templates use `${variable_name}` placeholders. Replace in Python:

```python
import json
import re

def fill_template(template: dict, values: dict) -> dict:
    """Replace ${var} placeholders in template with values."""
    template_str = json.dumps(template)
    
    for key, value in values.items():
        placeholder = f"${{{key}}}"
        # Escape special JSON characters in value
        safe_value = json.dumps(str(value))[1:-1]  # Remove surrounding quotes
        template_str = template_str.replace(placeholder, safe_value)
    
    return json.loads(template_str)

# Example
values = {
    "invoice_number": "INV-2024-001",
    "vendor_name": "ACME Corp",
    "amount": "$1,500.00",
    "due_date": "2024-02-15",
    "timestamp": "2024-01-15 14:30 UTC"
}
card = fill_template(invoice_template, values)
```

### Color Options

Available colors for TextBlock:
- `Default`, `Dark`, `Light`
- `Accent` (blue)
- `Good` (green)
- `Warning` (yellow)
- `Attention` (red)

### Container Styles

- `default` - Normal background
- `emphasis` - Light gray background
- `accent` - Themed color background
- `good` - Green background
- `attention` - Red background
- `warning` - Yellow background

### Size Options

TextBlock sizes: `Small`, `Default`, `Medium`, `Large`, `ExtraLarge`

### Best Practices

1. Always set `"wrap": true` on TextBlocks
2. Keep FactSet to ≤10 items
3. Limit to 6 actions
4. Use icons (emoji) sparingly
5. Test in Teams before production
6. Keep total card size under 28KB
