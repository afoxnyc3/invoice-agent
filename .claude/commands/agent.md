# Invoice Agent Development Assistant

## Session Start
```bash
# 1. Sync with main
git checkout main && git pull

# 2. Check open issues
gh issue list --label "priority:critical,priority:high" --state open
```

## Quick Start (Read First)
1. **Read `/CLAUDE.md`** - Contains all project constraints, patterns, and workflow rules
2. **Reference function**: `src/ExtractEnrich/` - Copy this pattern for new functions

## System Overview

**Purpose**: Automate invoice email processing from shared mailbox to Accounts Payable in <10 seconds.

**Data Flow (current implementation)**:
```
Email Arrives → MailWebhook (HTTP) → MailWebhookProcessor (Queue)
                                            ↓
                     ┌──────────────────────┴──────────────────────┐
                     ↓                                             ↓
              Known Vendor                                  Unknown Vendor
                     ↓                                             ↓
           ExtractEnrich (Queue)                      Send Registration Email
                     ↓                                             ↓
              PostToAP (Queue)                         Record in Transactions
                     ↓
            Notify (Queue) → Teams
```

**Fallback**: `MailIngest` (Timer) polls hourly if webhooks miss emails.

## Repository Structure
```
src/
├── MailWebhook/           # HTTP - Graph webhook receiver
├── MailWebhookProcessor/  # Queue - Process notifications, extract PDF vendor
├── SubscriptionManager/   # Timer - Renew Graph subscriptions (6-day cycle)
├── MailIngest/            # Timer - Hourly fallback polling
├── ExtractEnrich/         # Queue - Vendor lookup + AI extraction ⭐ CANONICAL
├── PostToAP/              # Queue - Format and send to AP mailbox
├── Notify/                # Queue - Teams webhook notifications
├── AddVendor/             # HTTP - Vendor CRUD operations
├── Health/                # HTTP - Health check endpoint
└── shared/
    ├── config.py          # Singleton config with lazy-loaded clients
    ├── models.py          # Pydantic models (RawMail, EnrichedInvoice, etc.)
    ├── graph_client.py    # Microsoft Graph API wrapper
    ├── pdf_extractor.py   # pdfplumber + Azure OpenAI extraction
    └── email_processor.py # Shared email processing logic (attachment → blob + queue)

tests/
├── unit/                  # pytest with mocks
└── integration/           # Requires Azurite

infrastructure/
├── bicep/                 # IaC templates
│   ├── main.bicep
│   └── modules/
└── parameters/            # Environment configs (dev.json, prod.json)
```

## Data Contracts

### Queue Messages (actual Pydantic models)
`raw-mail` (MailWebhookProcessor/MailIngest → ExtractEnrich)
```python
class RawMail(BaseModel):
    id: str                         # ULID correlation/transaction id
    sender: EmailStr                # sender email
    subject: str
    blob_url: str                   # single attachment URL (PDF)
    received_at: str                # ISO-8601
    original_message_id: str        # Graph message id for dedup
    vendor_name: Optional[str] = None  # from PDF extraction if available
```

`to-post` (ExtractEnrich → PostToAP)
```python
class EnrichedInvoice(BaseModel):
    id: str
    vendor_name: str
    expense_dept: str
    gl_code: str                    # 4 digits
    allocation_schedule: str
    billing_party: str              # default from config
    blob_url: str
    original_message_id: str
    status: Literal["enriched","unknown"]
    sender_email: Optional[EmailStr] = None
    received_at: Optional[str] = None
    invoice_hash: Optional[str] = None
    invoice_amount: Optional[float] = None
    currency: Optional[str] = "USD"
    due_date: Optional[str] = None
    payment_terms: Optional[str] = "Net 30"
```

### Table Storage
| Table | PartitionKey | RowKey | Purpose |
|-------|-------------|--------|---------|
| VendorMaster | `"Vendor"` | normalized vendor name (e.g., `adobe_inc`) | Vendor GL/Dept/Allocation metadata |
| InvoiceTransactions | `YYYYMM` | ULID transaction id | Audit + dedup (`OriginalMessageId`, `InvoiceHash`, `Status`, `EmailsSentCount`) |
| GraphSubscriptions | `"GraphSubscription"` | subscription_id | Active Graph webhook subscription state (`IsActive`, `ExpirationDateTime`) |

## Critical Constraints (from CLAUDE.md + codebase)

- **Imports**: Use `from shared.config import config` NOT `from src.shared...`
- **Function complexity**: Cyclomatic complexity ≤10 (soft line limit ~25)
- **IDs**: Use ULID for transaction/correlation IDs (sortable, unique)
- **Test coverage**: ≥60% minimum
- **Validation**: Pydantic v2 strict mode on all models
- **Secrets**: Key Vault references only, never hardcoded
- **Error handling**: All external calls must have explicit try/except
- **Auth**: HTTP functions must be AAD/App Role or APIM-protected; function keys are not sufficient for prod
- **Timeouts**: Every external call (Graph, OpenAI, Teams, HTTP) must set an explicit timeout (≤15s) and use retry-with-backoff; defaults: Graph 10–15s, OpenAI 10–15s, Teams/webhooks 10s, other HTTP 10s
- **Storage access**: Production storage/Key Vault access must use Managed Identity; connection strings allowed only for local Azurite. Example: `TableServiceClient(account_url, credential=DefaultAzureCredential())`

## Autonomy Rules

### Act Without Asking
- Issues labeled `ready` or `priority:critical`
- Bug fixes with clear reproduction steps
- Test additions
- Documentation updates
- Refactoring within existing patterns

### Stop and Ask If
- [ ] Change affects queue message schemas (breaking change)
- [ ] Change affects Table Storage schemas (migration needed)
- [ ] Security implications unclear (auth, PII, Key Vault)
- [ ] Architecture decision with multiple valid approaches
- [ ] 3 implementation attempts failed validation
- [ ] Contradicts patterns in CLAUDE.md

## Implementation Workflow

### 1. Before Starting Any Issue
```bash
# Sync with main
git checkout main && git pull

# Read the issue fully
gh issue view <number>

# Check for blocking issues
gh issue list --label "priority:critical" --state open
```

### 2. Branch and Implement
```bash
# Branch naming: {type}/issue-{number}-{description}
git checkout -b feat/issue-42-add-retry-logic

# Implementation order:
# 1. Models (shared/models.py) - data contracts first
# 2. Shared utilities (if needed)
# 3. Function logic with error handling
# 4. function.json bindings (if new triggers)
# 5. Tests (unit first, integration if needed)
# 6. Bicep (if new Azure resources)
```

### 3. Validation Gates (All Must Pass)
```bash
# From repo root
export PYTHONPATH=./src

# Tests with coverage
pytest tests/unit --cov=src --cov-fail-under=60 -v

# Code formatting
black --check src/ tests/

# Linting
flake8 src/ tests/

# YAML validation (if workflow changes)
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci-cd.yml'))"
```

### 4. Commit and PR
```bash
# Commit format: type(scope): description
git add -A
git commit -m "feat(ExtractEnrich): add retry logic for transient failures

- Add exponential backoff for Graph API calls
- Handle 429 rate limiting gracefully
- Add correlation ID to all log entries

Closes #42"

# Push and create PR
git push -u origin feat/issue-42-add-retry-logic
gh pr create --title "feat(ExtractEnrich): add retry logic (closes #42)" \
  --body "## Summary
Brief description

## Changes
- Change 1
- Change 2

## Test Plan
- [ ] Unit tests pass
- [ ] Manual verification

Closes #42"
```

## Code Patterns

### Queue Function Template (Copy from ExtractEnrich patterns)
```python
"""
FunctionName - Brief description.

Triggered by: queue-name queue
Outputs to: next-queue queue (if applicable)
"""
import logging
import json
import azure.functions as func
from shared.config import config
from shared.models import InputModel, OutputModel
from shared.logger import get_logger
from shared.retry import retry_with_backoff

logger = logging.getLogger(__name__)

def main(msg: func.QueueMessage, outputQueue: func.Out[str]) -> None:
    """Process queue message."""
    correlation_id = msg.id  # fall back to queue id if payload missing

    try:
        # Parse input
        data = json.loads(msg.get_body().decode("utf-8"))
        correlation_id = data.get("id", data.get("correlation_id", msg.id))
        clog = get_logger(__name__, correlation_id)
        clog.info("Processing started")

        # Validate with Pydantic
        input_model = InputModel(**data)

        # Business logic here
        @retry_with_backoff(max_attempts=3, initial_delay=2.0)
        def process_with_retry():
            # Wrap external calls with explicit timeouts (Graph/OpenAI 10–15s, Teams/webhooks 10s)
            return process(input_model)

        result = process_with_retry()

        # Output to next queue
        output = OutputModel(**result)
        outputQueue.set(output.model_dump_json())

        clog.info("Processing completed")

    except ValidationError as e:
        # Don't retry validation errors
        logger.error(f"[{correlation_id}] Validation failed: {e}")
        raise
    except Exception as e:
        # Will retry up to 5 times, then poison queue
        logger.error(f"[{correlation_id}] Processing failed: {e}")
        raise
```

### HTTP Function Template
```python
def main(req: func.HttpRequest) -> func.HttpResponse:
    """Handle HTTP request."""
    try:
        # Parse and validate
        body = req.get_json()
        input_model = InputModel(**body)

        # Process
        result = process(input_model)

        return func.HttpResponse(
            json.dumps(result),
            status_code=200,
            mimetype="application/json"
        )
    except ValidationError as e:
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=400,
            mimetype="application/json"
        )
    except Exception as e:
        logger.exception("Unexpected error")
        return func.HttpResponse(
            json.dumps({"error": "Internal server error"}),
            status_code=500,
            mimetype="application/json"
        )
```

## When Stuck

1. **Can't find pattern**: Read `src/ExtractEnrich/__init__.py` as canonical example
2. **Import errors**: Check PYTHONPATH and use `from shared.*` not `from src.shared.*`
3. **Test failures**: Run `pytest -xvs` for verbose output, check mocks
4. **Azure errors**: Check `src/shared/config.py` for client initialization patterns
5. **Graph API issues**: See `src/shared/graph_client.py` for authentication flow
6. **3 failures**: Stop, document what you tried, ask for guidance

## Key Documentation
- `/CLAUDE.md` - Development workflow, constraints, quality gates
- `/docs/ARCHITECTURE.md` - System design, data models, security
- `/docs/DEPLOYMENT_GUIDE.md` - CI/CD, staging slots, Azure setup
- `/docs/operations/TROUBLESHOOTING_GUIDE.md` - Common issues and fixes

## Telemetry & Alerts (MVP defaults)
- Logs: INFO in prod, DEBUG only locally; Application Insights sampling 10–20% to control cost.
- Metrics to emit: Graph latency/success, OpenAI latency/success, queue depth and age, DLQ count, subscription expiration time, webhook validation failures.
- Alerts (Azure Monitor): queue age >2m or DLQ count >0; Graph/OpenAI failure rate ≥3 in 5m; subscription expiring in <24h; health endpoint 5xx.
