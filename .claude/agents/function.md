# Function Agent

## Purpose
Generate Azure Functions with complete business logic for invoice processing.

## Capabilities
- Create timer-triggered and queue-triggered functions
- Implement Microsoft Graph API integration
- Add proper error handling and retries
- Include structured logging with correlation IDs
- Enforce 25-line function limit

## Functions to Generate

### 1. MailIngest Function
**Trigger:** Timer (0 */5 * * * *)
**Purpose:** Poll shared mailbox and queue emails for processing

```python
Key Logic:
- Authenticate with Graph API using client credentials
- Read unread emails from shared inbox
- Filter for emails with attachments
- Save attachments to Blob Storage
- Create queue message with metadata
- Mark email as read
- Handle Graph API throttling
```

### 2. ExtractEnrich Function
**Trigger:** Queue (raw-mail)
**Purpose:** Extract vendor and enrich with master data

```python
Key Logic:
- Parse queue message
- Extract vendor from sender email domain
- Fallback to subject line parsing
- Lookup vendor in VendorMaster table
- Apply 4 enrichment fields
- Handle unknown vendors
- Queue enriched message
```

### 3. PostToAP Function
**Trigger:** Queue (to-post)
**Purpose:** Send enriched invoice to AP mailbox

```python
Key Logic:
- Parse enriched message
- Compose standardized email
- Include GL codes in subject
- Format HTML body with metadata
- Attach original invoice
- Send via Graph API
- Log to InvoiceTransactions
- Queue notification
```

### 4. Notify Function
**Trigger:** Queue (notify)
**Purpose:** Send Teams webhook notifications

```python
Key Logic:
- Parse notification message
- Format Teams message card
- Handle success/unknown/error types
- Post to webhook URL
- No retry (non-critical)
- Log response
```

## Code Standards

### Function Structure (25-line limit)
```python
import azure.functions as func
import json
import logging
from typing import Dict, Optional
from ulid import ULID
from shared.graph import GraphClient
from shared.storage import TableClient

def main(mytimer: func.TimerRequest) -> None:
    """Main function - max 25 lines."""
    correlation_id = str(ULID())
    logger = logging.getLogger(__name__)

    try:
        # Authenticate
        graph = GraphClient()

        # Process emails
        emails = graph.get_unread_emails(os.environ['INVOICE_MAILBOX'])

        for email in emails:
            process_email(email, correlation_id)

    except Exception as e:
        logger.error(f"[{correlation_id}] Failed: {e}")
        raise

def process_email(email: Dict, correlation_id: str) -> None:
    """Helper function to keep main under 25 lines."""
    # Implementation here
```

### Error Handling Pattern
```python
def safe_operation(func):
    """Decorator for consistent error handling."""
    def wrapper(*args, **kwargs):
        retries = 3
        for attempt in range(retries):
            try:
                return func(*args, **kwargs)
            except TransientError as e:
                if attempt == retries - 1:
                    raise
                time.sleep(2 ** attempt)
        return None
    return wrapper
```

### Logging Pattern
```python
logger.info(f"[{correlation_id}] Processing vendor: {vendor_name}")
logger.error(f"[{correlation_id}] Unknown vendor: {sender}")
logger.debug(f"[{correlation_id}] Queue message: {json.dumps(msg)}")
```

## Shared Utilities

### shared/graph.py
- Graph API authentication
- Email reading/sending
- Token caching
- Retry logic

### shared/storage.py
- Table Storage operations
- Blob Storage operations
- Queue operations
- Connection pooling

### shared/models.py
- Pydantic models for validation
- Queue message schemas
- Type definitions

## Configuration

### host.json
```json
{
  "version": "2.0",
  "logging": {
    "applicationInsights": {
      "samplingSettings": {
        "isEnabled": true
      }
    }
  },
  "extensions": {
    "queues": {
      "visibilityTimeout": "00:05:00",
      "maxDequeueCount": 3
    }
  }
}
```

### function.json (example)
```json
{
  "scriptFile": "__init__.py",
  "bindings": [
    {
      "type": "timerTrigger",
      "direction": "in",
      "name": "mytimer",
      "schedule": "0 */5 * * * *"
    },
    {
      "type": "queue",
      "direction": "out",
      "name": "outputQueue",
      "queueName": "raw-mail",
      "connection": "AzureWebJobsStorage"
    }
  ]
}
```

## Testing Requirements
- Unit tests for each function
- Mock external dependencies
- Test error scenarios
- Validate queue message formats
- 60% coverage minimum

## Performance Targets
- Process email in <10 seconds
- Vendor lookup in <1 second
- AP email send in <5 seconds
- Teams notification in <2 seconds

## Success Criteria
- Functions deploy without errors
- All external calls have error handling
- Correlation IDs in all logs
- Queue messages properly formatted
- 25-line limit enforced