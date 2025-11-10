# /build - Function Builder

Build and package Azure Functions with complete business logic.

## Actions

1. **Generate function code**
   - Create MailIngest with Graph API integration
   - Create ExtractEnrich with vendor lookup
   - Create PostToAP with email sending
   - Create Notify with Teams webhook

2. **Create shared utilities**
   - Graph API client wrapper
   - Table Storage repositories
   - Pydantic models for validation
   - Error handling decorators

3. **Update configuration**
   - Generate function.json for each function
   - Update host.json with settings
   - Update requirements.txt with dependencies

4. **Validate code quality**
   - Run type checking with mypy
   - Check 25-line function limit
   - Verify error handling present
   - Ensure correlation IDs used

5. **Package for deployment**
   - Create deployment zip
   - Exclude test files and cache
   - Include all dependencies

## Code Generation

When user types `/build`:

```python
# Generate MailIngest function
print("Generating MailIngest function...")

# src/functions/MailIngest/__init__.py
code = '''
import azure.functions as func
import json
import logging
from datetime import datetime
from ulid import ULID
from shared.graph import GraphClient
from shared.storage import QueueClient

def main(mytimer: func.TimerRequest, outputQueue: func.Out[str]) -> None:
    """Poll mailbox and queue emails for processing."""
    correlation_id = str(ULID())
    logger = logging.getLogger(__name__)

    try:
        logger.info(f"[{correlation_id}] Starting email ingestion")
        graph = GraphClient()
        emails = graph.get_unread_emails("invoices@example.com")

        for email in emails:
            message = process_email(email, correlation_id)
            if message:
                outputQueue.set(json.dumps(message))
                graph.mark_as_read(email["id"])

        logger.info(f"[{correlation_id}] Processed {len(emails)} emails")

    except Exception as e:
        logger.error(f"[{correlation_id}] MailIngest failed: {e}")
        raise

def process_email(email: dict, correlation_id: str) -> dict:
    """Process individual email (helper to stay under 25 lines)."""
    if not email.get("hasAttachments"):
        return None

    # Save attachments to blob
    blob_url = save_attachments(email["attachments"])

    return {
        "id": correlation_id,
        "sender": email["sender"]["emailAddress"]["address"],
        "subject": email["subject"],
        "blob_url": blob_url,
        "received_at": datetime.utcnow().isoformat()
    }
'''

# Write similar code for other functions...

# Generate shared utilities
print("Creating shared utilities...")

# shared/graph.py
graph_client = '''
import msal
import requests
from typing import List, Dict, Optional
import os

class GraphClient:
    """Microsoft Graph API client."""

    def __init__(self):
        self.app = msal.ConfidentialClientApplication(
            os.environ["GRAPH_CLIENT_ID"],
            authority=f"https://login.microsoftonline.com/{os.environ['GRAPH_TENANT_ID']}",
            client_credential=os.environ["GRAPH_CLIENT_SECRET"]
        )
        self.token = None

    def _get_token(self) -> str:
        """Get or refresh access token."""
        if not self.token:
            result = self.app.acquire_token_for_client(
                scopes=["https://graph.microsoft.com/.default"]
            )
            self.token = result["access_token"]
        return self.token

    def get_unread_emails(self, mailbox: str) -> List[Dict]:
        """Get unread emails from mailbox."""
        headers = {"Authorization": f"Bearer {self._get_token()}"}
        url = f"https://graph.microsoft.com/v1.0/users/{mailbox}/messages"
        params = {"$filter": "isRead eq false", "$top": 50}

        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()["value"]
'''

# Validate code quality
print("Validating code quality...")
# - Check function line counts
# - Run mypy for type checking
# - Verify imports are correct
```

## Build Output

```
📦 Building Invoice Agent Functions...

✅ Generated MailIngest function (24 lines)
✅ Generated ExtractEnrich function (23 lines)
✅ Generated PostToAP function (25 lines)
✅ Generated Notify function (20 lines)

✅ Created shared/graph.py (Graph API client)
✅ Created shared/storage.py (Storage operations)
✅ Created shared/models.py (Data models)

✅ Updated host.json
✅ Updated requirements.txt

📋 Code Quality Report:
- All functions under 25 lines ✅
- Type hints complete ✅
- Error handling present ✅
- Correlation IDs used ✅

📦 Created deployment package: function-app.zip (2.3 MB)

Next steps:
1. Run `/test` to validate functions
2. Run `/deploy` to push to Azure
```

## File Structure Created

```
src/
├── functions/
│   ├── MailIngest/
│   │   ├── __init__.py
│   │   └── function.json
│   ├── ExtractEnrich/
│   │   ├── __init__.py
│   │   └── function.json
│   ├── PostToAP/
│   │   ├── __init__.py
│   │   └── function.json
│   └── Notify/
│       ├── __init__.py
│       └── function.json
├── shared/
│   ├── __init__.py
│   ├── graph.py
│   ├── storage.py
│   └── models.py
├── host.json
└── requirements.txt
```

## Requirements Generated

```txt
# requirements.txt
azure-functions==1.17.0
azure-identity==1.15.0
azure-keyvault-secrets==4.7.0
azure-data-tables==12.4.4
azure-storage-blob==12.19.0
azure-storage-queue==12.8.0
msal==1.25.0
pydantic==2.5.0
ulid-py==1.1.0
requests==2.31.0
```

## Validation Rules

- Each function must be ≤25 lines
- All functions must have type hints
- All external calls must have try/except
- All logs must include correlation ID
- All queue messages must be valid JSON

## Error Cases

If build fails:
- Function exceeds 25 lines → Split into helper functions
- Missing type hints → Add type annotations
- No error handling → Wrap in try/except
- Import errors → Check requirements.txt
- Validation errors → Review code standards