# Invoice Agent - Technical Specification

**Purpose:** Automated invoice processing system using Azure serverless architecture
**Status:** Production Deployed (Webhook-based, Event-Driven)
**Cost:** ~$0.60/month | **Latency:** <10 seconds | **Test Coverage:** 96%

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Technology Stack & Rationale](#technology-stack--rationale)
4. [System Components](#system-components)
5. [Data Models & Storage](#data-models--storage)
6. [Code Quality Standards](#code-quality-standards)
7. [Infrastructure & Deployment](#infrastructure--deployment)
8. [Observability & Monitoring](#observability--monitoring)
9. [Security & Compliance](#security--compliance)
10. [Scaling & Evolution](#scaling--evolution)
11. [Official References](#official-references)

---

## Executive Summary

### Problem
Manual invoice processing from email takes 5+ minutes per invoice with no standardization, audit trail, or automation.

### Solution
Event-driven serverless pipeline that:
- Receives real-time email notifications via Microsoft Graph webhooks (<10 sec)
- Extracts vendor from email sender/subject
- Enriches with GL codes from lookup table
- Routes to accounts payable mailbox
- Maintains complete audit trail

### Key Metrics
- **Processing Time:** <10 seconds (was 5+ minutes manual)
- **Cost:** $0.60/month (70% reduction after webhook migration)
- **Reliability:** 99.9% uptime target with automatic retry
- **Test Coverage:** 96% (98 tests passing)

---

## Architecture Overview

### Event-Driven Pipeline (Nov 2024 - Current)

```
┌─────────────────────────────────────────────────────────────────┐
│                   Shared Mailbox (invoices@company.com)         │
└────────────────────────────┬────────────────────────────────────┘
                             │ Email arrives
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                     Microsoft Graph API                          │
│  - Detects email instantly (<5 seconds)                         │
│  - Sends webhook notification (HTTP POST)                       │
└──────────────┬──────────────────────────────┬───────────────────┘
               │ Real-time notification       │ Subscription Mgmt
               ↓                              ↓
┌──────────────────────────────┐  ┌──────────────────────────────┐
│   MailWebhook (HTTP)        │  │ SubscriptionManager (Timer) │
│ - Validates client state    │  │ - Renews every 6 days       │
│ - Queues for processing     │  │ - Stores in GraphSubs table │
│ - Returns 202 in <3 sec     │  └──────────────────────────────┘
└──────────────┬───────────────┘
               │ Queue: webhook-notifications
               ↓
┌──────────────────────────────┐
│ MailWebhookProcessor (Queue)│
│ - Fetches email via Graph   │
│ - Downloads attachments     │
│ - Queues to raw-mail        │
└──────────────┬───────────────┘
               │ Queue: raw-mail
               ↓
┌──────────────────────────────┐
│   ExtractEnrich (Queue)     │
│ - Extract vendor from email │
│ - Lookup in VendorMaster    │
│ - Apply GL codes            │
└──────────────┬───────────────┘
               │ Queue: to-post
               ↓
┌──────────────────────────────┐
│     PostToAP (Queue)        │
│ - Compose standardized email│
│ - Send to AP mailbox        │
│ - Log to InvoiceTransactions│
└──────────────┬───────────────┘
               │ Queue: notify
               ↓
┌──────────────────────────────┐
│      Notify (Queue)         │
│ - Post to Teams webhook     │
│ - Non-critical (no retry)   │
└──────────────────────────────┘

FALLBACK PATH (Safety Net):
┌──────────────────────────────┐
│   MailIngest (Timer Hourly) │
│ - Polls for missed emails   │
│ - Queues to raw-mail        │
└──────────────────────────────┘
```

### Key Architecture Principles

1. **Event-Driven First, Polling as Fallback**
   - Primary: Graph API webhooks (95% of emails, <10 sec)
   - Fallback: Hourly polling (5% missed notifications)

2. **Queue-Based Decoupling**
   - Natural error boundaries between functions
   - Built-in retry with exponential backoff
   - Poison queues after 5 attempts
   - Observable via queue depth metrics

3. **Serverless for Variable Workload**
   - 5-50 invoices/day with sporadic arrival
   - Auto-scale 0-200 instances
   - Pay only for execution time

4. **Fail-Safe, Not Fail-Stop**
   - Unknown vendors still processed (flagged for review)
   - Teams webhook failures don't block pipeline
   - Hourly fallback catches webhook failures

---

## Technology Stack & Rationale

### Compute: Azure Functions (Consumption Plan Y1)

**Choice:** Serverless functions over containers/VMs

**Rationale:**
- ✅ Variable workload (5-50/day) = perfect serverless fit
- ✅ Cost efficiency: $0.60/month vs $30-50/month for containers
- ✅ Zero ops overhead (no patching, scaling, cluster management)
- ✅ Native queue triggers and integrations

**Trade-offs:**
- ⚠️ Cold start latency (~2-4 sec for Python, acceptable for <10 sec SLA)
- ⚠️ 5-minute execution timeout (sufficient for email processing)

**When to reconsider:**
- Volume >1,000 invoices/day (but then cost justifies migration)
- Need <100ms cold starts (not required for email processing)

**Official Docs:**
- [Azure Functions Python Developer Guide](https://learn.microsoft.com/en-us/azure/azure-functions/functions-reference-python)
- [Consumption Plan Pricing](https://azure.microsoft.com/en-us/pricing/details/functions/)

---

### Language: Python 3.11 (Current) | TypeScript (Recommended for Future)

**Current Choice:** Python 3.11

**Rationale:**
- ✅ Pydantic for robust data validation
- ✅ Simpler Azure SDK ecosystem
- ✅ Finance teams familiar with Python

**Trade-offs:**
- ⚠️ Slower cold starts than Node.js (2-4s vs 1-2s)
- ⚠️ Less natural for async/event-driven patterns
- ⚠️ Smaller serverless ecosystem vs JavaScript/TypeScript

**For Future Services:**

**Recommendation: TypeScript for new serverless projects**

**Why TypeScript is better for serverless:**
```typescript
// TypeScript: Natural async/await, faster cold starts
export async function processInvoice(context, msg) {
  const email = await parseMessage(msg);
  const vendor = await lookupVendor(email.sender);
  await sendToAP(email, vendor);
}

// Python: Requires more ceremony, slower cold starts
async def process_invoice(msg: str) -> None:
    email = await parse_message(msg)
    vendor = await lookup_vendor(email.sender)
    await send_to_ap(email, vendor)
```

**Decision Framework:**
- **Event-driven/async workflows** → TypeScript (better ergonomics)
- **Data processing pipelines** → Python (pandas, numpy ecosystem)
- **Mixed team skillsets** → Use what team knows best

**Official Docs:**
- [Azure Functions TypeScript Guide](https://learn.microsoft.com/en-us/azure/azure-functions/functions-reference-node)
- [Cold Start Performance](https://azure.github.io/azure-functions-durable-extension/articles/performance.html)

---

### Storage: Table Storage (Not Cosmos DB)

**Choice:** Azure Table Storage for VendorMaster and InvoiceTransactions

**Rationale:**
- ✅ **Cost:** $0.05/month vs $5-25/month for Cosmos DB (100x cheaper)
- ✅ **Access pattern:** Simple key-value lookups (PartitionKey + RowKey)
- ✅ **Scale:** Handles 100-1,000 vendors easily (overkill for current needs)

**Trade-offs:**
- ⚠️ No complex queries (acceptable - we only do direct lookups)
- ⚠️ No automatic indexing on arbitrary fields (not needed)
- ⚠️ Limited to 1,000 ops/sec per partition (sufficient for our volume)

**When to migrate to Cosmos DB:**
- Full-text search across vendor fields
- Multi-region active-active replication
- Vendor count >10,000 with complex queries

**Table Design:**

```python
# VendorMaster: Optimized for vendor lookup
PartitionKey: "Vendor"
RowKey: "adobe_com" (normalized email domain)
Fields: VendorName, ExpenseDept, GLCode, AllocationSchedule, BillingParty

# InvoiceTransactions: Optimized for time-range queries
PartitionKey: "202411" (YYYYMM format)
RowKey: "01JCK3Q7H8ZVXN3BARC9GWAEZM" (ULID - sortable, unique)
Fields: VendorName, SenderEmail, ExpenseDept, GLCode, Status, ProcessedAt
```

**Official Docs:**
- [Table Storage Design Guide](https://learn.microsoft.com/en-us/azure/storage/tables/table-storage-design-guide)
- [When to Use Cosmos DB vs Table Storage](https://learn.microsoft.com/en-us/azure/architecture/guide/technology-choices/data-store-decision-tree)

---

### Integration: Queue-Based (Not Durable Functions)

**Choice:** Azure Storage Queues between functions

**Rationale:**
- ✅ **Retry logic:** Built-in exponential backoff and poison queues
- ✅ **Error boundaries:** Each function can fail independently
- ✅ **Observability:** Queue depth = instant visibility into lag
- ✅ **Cost:** Effectively free vs Service Bus ($0.05 vs $10/month)
- ✅ **Simplicity:** No topic/subscription complexity

**Trade-offs:**
- ⚠️ No message ordering guarantees (not needed for independent invoices)
- ⚠️ No dead-letter queue with TTL (poison queue is sufficient)
- ⚠️ Max 64KB message size (sufficient for metadata + blob URLs)

**When to migrate to Durable Functions:**
- **Trigger:** >100 invoices/day OR conditional workflow logic
- **Use case:** Orchestration with compensation (e.g., approval workflows)
- **Pattern:** Fan-out/fan-in or human-in-the-loop approvals

**Queue Design:**

```python
# Linear pipeline (current)
webhook-notifications → raw-mail → to-post → notify

# Future orchestration (when needed)
Durable Function Orchestrator
├─ Activity: FetchEmail
├─ Activity: EnrichVendor
├─ Sub-Orchestration: ApprovalWorkflow (if GL > $10,000)
└─ Activity: SendToAP
```

**Official Docs:**
- [Azure Storage Queues](https://learn.microsoft.com/en-us/azure/storage/queues/storage-queues-introduction)
- [When to Use Durable Functions](https://learn.microsoft.com/en-us/azure/azure-functions/durable/durable-functions-overview)

---

## System Components

### Function Specifications

#### 1. MailWebhook (HTTP Trigger)
**Purpose:** Receive Graph API change notifications

```python
# Endpoint: POST /api/MailWebhook
# Trigger: HTTP POST from Microsoft Graph
# Execution: <3 seconds (Graph requires fast response)

def main(req: func.HttpRequest) -> func.HttpResponse:
    # MODE 1: Validation handshake (return validation token)
    if req.params.get('validationToken'):
        return func.HttpResponse(req.params.get('validationToken'))

    # MODE 2: Process notification
    payload = req.get_json()
    validate_client_state(payload)  # Security check
    queue_message('webhook-notifications', payload)
    return func.HttpResponse(status_code=202)  # Accepted
```

**Security:** Client state validation prevents unauthorized webhooks

**Scaling:** Auto-scale based on HTTP requests

**Official Docs:**
- [Microsoft Graph Webhooks](https://learn.microsoft.com/en-us/graph/webhooks)
- [Change Notifications](https://learn.microsoft.com/en-us/graph/webhooks-lifecycle)

---

#### 2. MailWebhookProcessor (Queue Trigger)
**Purpose:** Process webhook notifications and fetch email details

```python
# Trigger: webhook-notifications queue
# Output: raw-mail queue
# Execution: <60 seconds

def main(msg: func.QueueMessage) -> None:
    notification = parse_notification(msg.get_body())
    email = fetch_email_from_graph(notification.resource)

    if is_system_email(email):
        return  # Prevent email loops

    attachments = download_attachments(email)
    raw_mail_msg = create_raw_mail(email, attachments)
    queue_message('raw-mail', raw_mail_msg)
    mark_as_read(email.id)
```

**Shared Logic:** Uses `shared.email_processor` (same as MailIngest)

**Why Separate from MailWebhook:** Decouples fast HTTP response from slow email fetching

---

#### 3. SubscriptionManager (Timer Trigger)
**Purpose:** Maintain Graph API webhook subscription

```python
# Trigger: Cron (0 0 0 */6 * *) - Every 6 days
# Execution: <2 minutes

def main(timer: func.TimerRequest) -> None:
    sub = get_active_subscription()  # Query GraphSubscriptions table

    if sub and expires_within_48_hours(sub):
        renew_subscription(sub.id)  # Extend expiration
    elif not sub:
        create_subscription()  # Initial setup

    update_subscription_table(sub)
```

**Why 6 days:** Graph API subscriptions expire after 7 days. Renew with 24-hour buffer.

**Official Docs:**
- [Subscription Lifecycle](https://learn.microsoft.com/en-us/graph/webhooks-lifecycle)

---

#### 4. MailIngest (Timer Trigger - Fallback)
**Purpose:** Hourly polling for missed emails (safety net)

```python
# Trigger: Cron (0 0 * * * *) - Every hour
# Execution: <5 minutes

def main(timer: func.TimerRequest) -> None:
    emails = fetch_unread_emails()  # Graph API

    for email in emails:
        if is_system_email(email):
            continue

        attachments = download_attachments(email)
        raw_mail_msg = create_raw_mail(email, attachments)
        queue_message('raw-mail', raw_mail_msg)
        mark_as_read(email.id)
```

**Role Change:** Primary ingestion → Fallback safety net (handles ~5% of emails)

---

#### 5. ExtractEnrich (Queue Trigger)
**Purpose:** Extract vendor and enrich with GL codes

```python
# Trigger: raw-mail queue
# Output: to-post queue

def main(msg: func.QueueMessage) -> None:
    email = parse_raw_mail(msg.get_body())
    vendor_key = extract_vendor(email.sender)  # e.g., "adobe_com"

    vendor = lookup_vendor(vendor_key)  # Table Storage query

    enriched = {
        'vendor_name': vendor.VendorName if vendor else 'UNKNOWN',
        'gl_code': vendor.GLCode if vendor else 'UNKNOWN',
        'expense_dept': vendor.ExpenseDept if vendor else 'UNKNOWN',
        'status': 'enriched' if vendor else 'unknown_vendor'
    }

    queue_message('to-post', enriched)
```

**Fallback Behavior:** Unknown vendors still processed with "UNKNOWN" values

---

#### 6. PostToAP (Queue Trigger)
**Purpose:** Send enriched invoice to AP mailbox

```python
# Trigger: to-post queue
# Output: notify queue

def main(msg: func.QueueMessage) -> None:
    invoice = parse_enriched(msg.get_body())

    email_body = compose_ap_email(invoice)
    send_via_graph(
        to='ap@company.com',
        subject=f'Invoice: {invoice.vendor_name} - GL {invoice.gl_code}',
        body=email_body,
        attachments=[invoice.blob_url]
    )

    log_transaction(invoice)  # InvoiceTransactions table
    queue_message('notify', create_notification(invoice))
```

---

#### 7. Notify (Queue Trigger)
**Purpose:** Post status to Teams channel

```python
# Trigger: notify queue
# Non-critical: No retry on failure

def main(msg: func.QueueMessage) -> None:
    notification = parse_notification(msg.get_body())

    card = create_adaptive_card(notification)  # Teams format
    post_to_webhook(TEAMS_WEBHOOK_URL, card)

    # Note: Failures logged but don't block pipeline
```

**Non-Critical Path:** Teams webhook failures don't stop invoice processing

---

## Data Models & Storage

### Pydantic Models (Strict Validation)

```python
from pydantic import BaseModel, EmailStr, Field
from typing import Literal
from datetime import datetime

class RawMail(BaseModel):
    """Email ingestion from MailIngest or MailWebhookProcessor"""
    id: str = Field(..., description="ULID transaction ID")
    sender: EmailStr
    subject: str
    blob_url: str  # Attachment location
    received_at: datetime
    attachment_count: int = Field(ge=0)

    model_config = {"strict": True}  # No type coercion

class EnrichedInvoice(BaseModel):
    """Vendor-enriched data from ExtractEnrich"""
    id: str
    vendor_name: str
    expense_dept: str
    gl_code: str
    allocation_schedule: str
    billing_party: str
    blob_url: str
    sender_email: EmailStr
    subject: str
    status: Literal["enriched", "unknown_vendor"]

    model_config = {"strict": True}

class NotificationMessage(BaseModel):
    """Teams notification payload"""
    type: Literal["success", "unknown", "error"]
    message: str
    transaction_id: str
    details: dict

    model_config = {"strict": True}
```

**Why Pydantic:**
- Type safety with runtime validation
- Automatic JSON serialization/deserialization
- Clear data contracts between functions

---

### Table Storage Schemas

#### VendorMaster Table

```python
{
    "PartitionKey": "Vendor",  # Always "Vendor"
    "RowKey": "adobe_com",  # Normalized email domain
    "VendorName": "Adobe Inc",
    "ExpenseDept": "IT",
    "GLCode": "6100",
    "AllocationScheduleNumber": "MONTHLY",
    "BillingParty": "Company HQ",
    "Active": true,
    "UpdatedAt": "2024-11-09T12:00:00Z"
}
```

**Query Pattern:** Direct lookup by RowKey (O(1) performance)

```python
entity = table_client.get_entity(
    partition_key="Vendor",
    row_key=normalize_vendor("billing@adobe.com")  # → "adobe_com"
)
```

---

#### InvoiceTransactions Table

```python
{
    "PartitionKey": "202411",  # YYYYMM format
    "RowKey": "01JCK3Q7H8ZVXN3BARC9GWAEZM",  # ULID (sortable)
    "TransactionId": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
    "VendorName": "Adobe Inc",
    "SenderEmail": "billing@adobe.com",
    "ExpenseDept": "IT",
    "GLCode": "6100",
    "Status": "processed",
    "BlobUrl": "https://...",
    "ProcessedAt": "2024-11-09T14:30:00Z",
    "ErrorMessage": null
}
```

**Query Pattern:** Partition by month for efficient time-range queries

```python
# Get all invoices for November 2024
entities = table_client.query_entities(
    query_filter="PartitionKey eq '202411'"
)
```

**Why ULID over UUID:**
- Sortable (timestamp embedded)
- 128-bit random (no collisions)
- URL-safe Base32 encoding
- Faster indexing than UUID v4

**Official Docs:**
- [ULID Specification](https://github.com/ulid/spec)

---

#### GraphSubscriptions Table (NEW)

```python
{
    "PartitionKey": "GraphSubscription",  # Always "GraphSubscription"
    "RowKey": "da93534d-0c4c-4d9d-9b9e-c429c0549221",  # Subscription ID
    "SubscriptionId": "da93534d-0c4c-4d9d-9b9e-c429c0549221",
    "Resource": "users/invoices@company.com/mailFolders('Inbox')/messages",
    "ExpirationDateTime": "2025-11-23T22:25:47Z",
    "IsActive": true,
    "CreatedAt": "2025-11-20T18:30:00Z",
    "LastRenewed": "2025-11-20T18:30:00Z"
}
```

**Lifecycle:**
- Created by SubscriptionManager on first run
- Renewed every 6 days (Graph max: 7 days)
- Marked inactive when replaced

---

## Code Quality Standards

### ❌ OLD: Arbitrary Line Limits

```python
# OLD RULE (Don't use this)
# Max 25 lines per function
```

**Problem:**
- Arbitrary metric doesn't measure complexity
- Forces unnecessary extraction of single-use helpers
- Makes simple linear flows harder to read

---

### ✅ NEW: Complexity-Based Metrics

**Code Quality Metrics:**

| Metric | Target | Tool | Rationale |
|--------|--------|------|-----------|
| **Cyclomatic Complexity** | ≤10 | radon, lizard | Measures branches/loops (true complexity) |
| **Parameters per Function** | ≤3 | Manual review | Encourages good design patterns |
| **Function Length** | ≤50 lines | Advisory only | Guideline, not hard limit |
| **Nesting Depth** | ≤3 levels | Manual review | Deep nesting = hard to test |
| **Extract on Reuse** | 2+ callers | Manual review | Don't extract proactively |

**Cyclomatic Complexity Example:**

```python
# Complexity = 1 (linear, no branches)
def process_invoice(msg):
    email = parse_message(msg)
    vendor = extract_vendor(email)
    enrichment = lookup_vendor(vendor)
    send_to_ap(email, enrichment)

# Complexity = 5 (4 if statements + 1)
def process_invoice_complex(msg):
    email = parse_message(msg)

    if email.has_attachment:
        if email.attachment.type == 'pdf':
            vendor = extract_from_pdf(email)
        else:
            vendor = extract_from_subject(email)
    else:
        return None  # Complexity +1

    if vendor:  # Complexity +1
        enrichment = lookup_vendor(vendor)
    else:  # Complexity +1
        enrichment = default_enrichment()

    send_to_ap(email, enrichment)
```

**Tools:**

```bash
# Install complexity analysis tools
pip install radon lizard

# Check cyclomatic complexity
radon cc src/ --min C  # Show functions with complexity >10

# Check maintainability index
radon mi src/ --min B  # Show files with MI <20

# Multi-language analysis
lizard src/ --CCN 10  # Show functions exceeding threshold
```

**Pre-Commit Hook:**

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: complexity-check
        name: Check Cyclomatic Complexity
        entry: radon cc src/ --min C --total-average
        language: system
        pass_filenames: false
```

**Official Docs:**
- [Radon Documentation](https://radon.readthedocs.io/)
- [Cyclomatic Complexity](https://en.wikipedia.org/wiki/Cyclomatic_complexity)

---

### Function Design Principles

**Good Function Design:**

```python
# ✅ GOOD: Single responsibility, low complexity
def extract_vendor_from_email(email: EmailStr) -> str:
    """Extract vendor key from email domain."""
    domain = email.split('@')[1]
    return normalize_domain(domain)

def lookup_vendor_by_key(vendor_key: str) -> Optional[Vendor]:
    """Query VendorMaster table by normalized key."""
    try:
        entity = table_client.get_entity("Vendor", vendor_key)
        return Vendor.from_table_entity(entity)
    except ResourceNotFoundError:
        return None

def enrich_invoice(email: RawMail) -> EnrichedInvoice:
    """Orchestrate vendor extraction and enrichment."""
    vendor_key = extract_vendor_from_email(email.sender)
    vendor = lookup_vendor_by_key(vendor_key)

    return EnrichedInvoice(
        id=email.id,
        vendor_name=vendor.VendorName if vendor else "UNKNOWN",
        gl_code=vendor.GLCode if vendor else "UNKNOWN",
        status="enriched" if vendor else "unknown_vendor"
    )
```

**Bad Function Design:**

```python
# ❌ BAD: Violates complexity limit
def process_everything(msg: str) -> None:
    """Does too many things, high complexity."""
    email = json.loads(msg)

    # Complexity +1
    if '@' in email['sender']:
        domain = email['sender'].split('@')[1]
        vendor_key = domain.lower().replace('.', '_')

        # Complexity +1
        try:
            vendor = table_client.get_entity("Vendor", vendor_key)
            gl_code = vendor['GLCode']

            # Complexity +1
            if gl_code.startswith('6'):
                dept = "IT"
            elif gl_code.startswith('7'):  # Complexity +1
                dept = "Marketing"
            else:  # Complexity +1
                dept = "General"

        except Exception as e:  # Complexity +1
            gl_code = "UNKNOWN"
            dept = "UNKNOWN"

            # Complexity +1
            if 'ResourceNotFound' in str(e):
                send_teams_alert("Unknown vendor")
            else:  # Complexity +1
                raise
    else:  # Complexity +1
        gl_code = "UNKNOWN"
        dept = "UNKNOWN"

    # ... more logic (Complexity = 9+)
```

---

## Infrastructure & Deployment

### Infrastructure as Code (Bicep)

**Module Structure:**

```
infrastructure/bicep/
├── main.bicep              # Orchestration
├── modules/
│   ├── functionapp.bicep   # Function App + App Service Plan
│   ├── storage.bicep       # Storage Account (Tables, Queues, Blobs)
│   ├── keyvault.bicep      # Key Vault + Secrets
│   ├── monitoring.bicep    # Application Insights + Alerts
│   └── rbac.bicep          # Role Assignments (Managed Identity)
└── parameters/
    ├── dev.json            # Development environment
    └── prod.json           # Production environment
```

**Why Bicep over Terraform:**
- Native Azure type checking
- Better IDE support (Azure extensions)
- Converts to ARM templates (Azure-native)
- No state file management

**When to use Terraform:**
- Multi-cloud deployments (AWS + Azure)
- Existing Terraform workflows
- Team expertise in HCL

---

### Infrastructure Testing (NEW)

**Problem Solved:**
- Staging slot app settings didn't sync (manual error)
- No validation before deployment
- Configuration drift undetected

**Solution: Automated Infrastructure Tests**

**1. Bicep Validation (Pre-Deployment)**

```bash
# .github/workflows/infrastructure.yml
- name: Validate Bicep Templates
  run: |
    az bicep build --file infrastructure/bicep/main.bicep
    az deployment group validate \
      --resource-group rg-invoice-agent-dev \
      --template-file infrastructure/bicep/main.bicep \
      --parameters infrastructure/parameters/dev.json
```

**2. What-If Analysis (Pre-Deployment)**

```bash
# Show changes before deployment
az deployment group what-if \
  --resource-group rg-invoice-agent-prod \
  --template-file infrastructure/bicep/main.bicep \
  --parameters infrastructure/parameters/prod.json
```

**3. Post-Deployment Validation**

```python
# tests/infrastructure/test_deployment.py
import pytest
from azure.identity import DefaultAzureCredential
from azure.mgmt.web import WebSiteManagementClient

def test_staging_slot_exists():
    """Verify staging slot is configured."""
    client = WebSiteManagementClient(credential, subscription_id)
    slots = client.web_apps.list_slots(rg, function_app_name)
    assert any(slot.name == 'staging' for slot in slots)

def test_app_settings_parity():
    """Verify staging has same settings as production."""
    prod_settings = get_app_settings(function_app_name, slot=None)
    staging_settings = get_app_settings(function_app_name, slot='staging')

    # Check critical settings match
    assert prod_settings['GRAPH_TENANT_ID'] == staging_settings['GRAPH_TENANT_ID']
    assert prod_settings['FUNCTIONS_WORKER_RUNTIME'] == staging_settings['FUNCTIONS_WORKER_RUNTIME']

def test_managed_identity_configured():
    """Verify Managed Identity has required roles."""
    identity = get_function_app_identity(function_app_name)
    roles = get_role_assignments(identity.principal_id)

    required_roles = [
        'Storage Blob Data Contributor',
        'Storage Queue Data Contributor',
        'Storage Table Data Contributor'
    ]

    for role in required_roles:
        assert role in roles, f"Missing role: {role}"
```

**4. Configuration Sync Script**

```bash
# scripts/sync-staging-settings.sh
#!/bin/bash
set -e

FUNCTION_APP="func-invoice-agent-prod"
RG="rg-invoice-agent-prod"

echo "Fetching production settings..."
az functionapp config appsettings list \
  --name $FUNCTION_APP \
  --resource-group $RG \
  --output json > /tmp/prod-settings.json

echo "Applying to staging slot..."
az functionapp config appsettings set \
  --name $FUNCTION_APP \
  --resource-group $RG \
  --slot staging \
  --settings @/tmp/prod-settings.json

echo "Restarting staging slot..."
az functionapp restart \
  --name $FUNCTION_APP \
  --resource-group $RG \
  --slot staging

echo "✅ Staging settings synced"
```

**Official Docs:**
- [Bicep Testing](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/test-toolkit)
- [Azure SDK for Python](https://learn.microsoft.com/en-us/python/api/overview/azure/)

---

### CI/CD Pipeline (Enhanced)

**GitHub Actions Workflow:**

```yaml
# .github/workflows/deploy.yml
name: Deploy Invoice Agent

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd src
          pip install -r requirements.txt

      - name: Run tests
        run: |
          export PYTHONPATH=./src
          pytest --cov=functions --cov=shared --cov-fail-under=60 -v

      - name: Check code quality
        run: |
          black --check src/
          flake8 src/
          mypy src/ --strict
          bandit -r src/ -ll

      - name: Check complexity
        run: |
          radon cc src/ --min C --total-average

  validate-infrastructure:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Azure Login
        uses: azure/login@v1
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Validate Bicep
        run: |
          az bicep build --file infrastructure/bicep/main.bicep

      - name: What-If Analysis
        run: |
          az deployment group what-if \
            --resource-group rg-invoice-agent-dev \
            --template-file infrastructure/bicep/main.bicep \
            --parameters infrastructure/parameters/dev.json

  deploy-staging:
    needs: [test, validate-infrastructure]
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v3

      - name: Deploy to Staging Slot
        run: |
          cd src
          func azure functionapp publish func-invoice-agent-prod --slot staging --python

      - name: Sync App Settings
        run: ./scripts/sync-staging-settings.sh

      - name: Run Smoke Tests
        run: pytest tests/smoke/ --env staging

  deploy-production:
    needs: [deploy-staging]
    runs-on: ubuntu-latest
    environment: production  # Manual approval gate
    steps:
      - name: Swap Slots
        run: |
          az functionapp deployment slot swap \
            --resource-group rg-invoice-agent-prod \
            --name func-invoice-agent-prod \
            --slot staging \
            --target-slot production

      - name: Verify Production Health
        run: |
          curl -f https://func-invoice-agent-prod.azurewebsites.net/api/health
```

**Key Improvements:**
1. Infrastructure validation before code deployment
2. Automated staging slot configuration sync
3. Post-deployment smoke tests
4. Complexity checking in CI/CD

---

## Observability & Monitoring

### Application Insights (Enhanced)

**Current State:**
- ✅ Basic Application Insights integration
- ✅ Correlation IDs (ULID) in all logs
- ✅ Structured JSON logging

**Enhancements:**

#### 1. OpenTelemetry Instrumentation

**Why OpenTelemetry:**
- Distributed tracing across functions
- Vendor-neutral (can switch from App Insights to other backends)
- Better correlation of queue-based workflows

**Implementation:**

```python
# shared/telemetry.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from azure.monitor.opentelemetry import configure_azure_monitor

# Configure Azure Monitor exporter
configure_azure_monitor(
    connection_string=os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
)

tracer = trace.get_tracer(__name__)

# Usage in functions
def main(msg: func.QueueMessage) -> None:
    with tracer.start_as_current_span("extract_enrich") as span:
        email = parse_raw_mail(msg.get_body())
        span.set_attribute("vendor.email", email.sender)
        span.set_attribute("transaction.id", email.id)

        vendor = lookup_vendor(email.sender)
        span.set_attribute("vendor.found", vendor is not None)

        # ... rest of processing
```

**Benefits:**
- See complete trace from webhook → notification
- Identify bottlenecks across function boundaries
- Correlate logs across queue hops

**Official Docs:**
- [Azure Monitor OpenTelemetry](https://learn.microsoft.com/en-us/azure/azure-monitor/app/opentelemetry-enable)
- [OpenTelemetry Python](https://opentelemetry.io/docs/languages/python/)

---

#### 2. Business Metrics Dashboard

**Custom Metrics:**

```python
# shared/metrics.py
from azure.monitor.opentelemetry.exporter import ApplicationInsightsSampler
from opentelemetry import metrics

meter = metrics.get_meter(__name__)

# Define custom metrics
invoice_counter = meter.create_counter(
    name="invoices_processed",
    description="Total invoices processed",
    unit="1"
)

vendor_match_counter = meter.create_counter(
    name="vendor_matches",
    description="Vendor lookups found",
    unit="1"
)

processing_duration = meter.create_histogram(
    name="processing_duration_ms",
    description="End-to-end processing time",
    unit="ms"
)

# Usage
invoice_counter.add(1, {"status": "success", "vendor": vendor.name})
vendor_match_counter.add(1, {"found": True})
processing_duration.record(duration_ms, {"function": "extract_enrich"})
```

**Dashboard Queries (KQL):**

```kql
// Vendor match rate (last 24 hours)
customMetrics
| where name == "vendor_matches"
| summarize
    Total = sum(value),
    Found = sumif(value, customDimensions.found == "true")
| extend MatchRate = (Found / Total) * 100

// Processing time P95 (last 24 hours)
customMetrics
| where name == "processing_duration_ms"
| summarize percentile(value, 95) by bin(timestamp, 1h)
| render timechart

// Queue depth over time
customMetrics
| where name == "queue_depth"
| summarize avg(value) by bin(timestamp, 5m), tostring(customDimensions.queue_name)
| render timechart
```

---

#### 3. Alert Rules (Enhanced)

**Alert Configuration:**

```bicep
// infrastructure/bicep/modules/monitoring.bicep
resource alertRules 'Microsoft.Insights/metricAlerts@2018-03-01' = [
  {
    name: 'high-error-rate'
    properties: {
      criteria: {
        allOf: [
          {
            metricName: 'FunctionErrors'
            operator: 'GreaterThan'
            threshold: 5
            timeAggregation: 'Count'
          }
        ]
      }
      windowSize: 'PT5M'
      evaluationFrequency: 'PT1M'
      severity: 1  // Critical
      actions: [{
        actionGroupId: oncallActionGroup.id
      }]
    }
  }
  {
    name: 'queue-backup'
    properties: {
      criteria: {
        allOf: [
          {
            metricName: 'QueueMessageCount'
            operator: 'GreaterThan'
            threshold: 50
            timeAggregation: 'Average'
          }
        ]
      }
      windowSize: 'PT15M'
      evaluationFrequency: 'PT5M'
      severity: 2  // Warning
      actions: [{
        actionGroupId: teamActionGroup.id
      }]
    }
  }
  {
    name: 'vendor-match-rate-low'
    properties: {
      criteria: {
        allOf: [
          {
            metricName: 'vendor_matches'
            dimensions: [{ name: 'found', values: ['true'] }]
            operator: 'LessThan'
            threshold: 80  // <80% match rate
            timeAggregation: 'Average'
          }
        ]
      }
      windowSize: 'PT1H'
      evaluationFrequency: 'PT15M'
      severity: 3  // Informational
      actions: [{
        actionGroupId: teamActionGroup.id
      }]
    }
  }
  {
    name: 'cost-anomaly'
    properties: {
      criteria: {
        allOf: [
          {
            metricName: 'FunctionExecutionCount'
            operator: 'GreaterThan'
            threshold: 10000  // Unusual spike
            timeAggregation: 'Count'
          }
        ]
      }
      windowSize: 'PT1H'
      evaluationFrequency: 'PT15M'
      severity: 2
      actions: [{
        actionGroupId: opsActionGroup.id
      }]
    }
  }
]
```

**Official Docs:**
- [Azure Monitor Alerts](https://learn.microsoft.com/en-us/azure/azure-monitor/alerts/alerts-overview)

---

## Security & Compliance

### Authentication & Authorization

**Managed Identity (System-Assigned):**

```bicep
// All Azure resource access via Managed Identity
resource functionApp 'Microsoft.Web/sites@2022-03-01' = {
  identity: {
    type: 'SystemAssigned'
  }
}

// RBAC assignments
resource blobRoleAssignment 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  scope: storageAccount
  properties: {
    roleDefinitionId: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'  // Storage Blob Data Contributor
    principalId: functionApp.identity.principalId
  }
}
```

**Graph API Authentication:**

```python
# shared/graph_client.py
from msal import ConfidentialClientApplication

class GraphClient:
    def __init__(self):
        self.app = ConfidentialClientApplication(
            client_id=os.getenv('GRAPH_CLIENT_ID'),
            client_credential=get_secret('graph-client-secret'),  # From Key Vault
            authority=f"https://login.microsoftonline.com/{os.getenv('GRAPH_TENANT_ID')}"
        )
        self._token_cache = None
        self._token_expiry = None

    def get_token(self) -> str:
        """Get cached token or refresh if expired."""
        if self._token_cache and datetime.now() < self._token_expiry:
            return self._token_cache

        result = self.app.acquire_token_for_client(
            scopes=['https://graph.microsoft.com/.default']
        )

        if 'access_token' in result:
            self._token_cache = result['access_token']
            self._token_expiry = datetime.now() + timedelta(seconds=result['expires_in'] - 300)  # 5-min buffer
            return self._token_cache
        else:
            raise AuthenticationError(result.get('error_description'))
```

**Official Docs:**
- [Managed Identity Best Practices](https://learn.microsoft.com/en-us/azure/active-directory/managed-identities-azure-resources/managed-identity-best-practice-recommendations)
- [MSAL Python](https://learn.microsoft.com/en-us/entra/msal/python/)

---

### Data Security

**Encryption:**
- **At Rest:** Azure Storage service encryption (Microsoft-managed keys)
- **In Transit:** TLS 1.2 minimum for all connections
- **Secrets:** Azure Key Vault with Managed Identity access

**Audit Logging:**
- All operations logged to Application Insights
- Correlation IDs (ULID) for request tracing
- No PII in log messages (email addresses in InvoiceTransactions only)

**Data Retention:**
- **Invoice Attachments:** 7 years (compliance requirement)
- **Transaction Logs:** 7 years (audit trail)
- **Application Logs:** 90 days (operational monitoring)

---

## Scaling & Evolution

### Current Scale (MVP)
- **Volume:** 5-50 invoices/day
- **Cost:** $0.60/month
- **Latency:** <10 seconds
- **Architecture:** Queue-based linear pipeline

### Scaling Triggers & Migration Paths

#### Trigger 1: >100 Invoices/Day

**Current Bottleneck:** Queue-based polling (visibility timeout overhead)

**Migration Path:** Durable Functions Orchestration

```python
# Before: Queue-based
webhook → raw-mail → to-post → notify

# After: Durable Functions
@app.orchestration_trigger(context_name="orchestratorContext")
def invoice_orchestrator(context):
    email = yield context.call_activity('fetch_email', context.get_input())
    vendor = yield context.call_activity('enrich_vendor', email)

    # Conditional logic (requires orchestration)
    if vendor.gl_code.startswith('9'):  # High-value invoices
        approval = yield context.call_activity('request_approval', vendor)
        if not approval:
            return

    yield context.call_activity('send_to_ap', vendor)
    yield context.call_activity('send_notification', vendor)
```

**Benefits:**
- Reduced latency (no queue polling overhead)
- Conditional workflows (approval logic)
- Built-in retry and compensation

**Official Docs:**
- [When to Use Durable Functions](https://learn.microsoft.com/en-us/azure/azure-functions/durable/durable-functions-overview#application-patterns)

---

#### Trigger 2: >10,000 Vendors

**Current Bottleneck:** Table Storage scan for vendor search

**Migration Path:** Cosmos DB with Full-Text Search

```python
# Before: Direct PartitionKey + RowKey lookup
vendor = table_client.get_entity("Vendor", "adobe_com")

# After: Cosmos DB with search
query = "SELECT * FROM c WHERE CONTAINS(c.vendorName, 'Adobe')"
vendors = container.query_items(query, enable_cross_partition_query=True)
```

**Cost Impact:** $5-25/month (vs $0.05/month Table Storage)

**Benefits:**
- Full-text search across vendor names
- Complex queries (e.g., "all IT vendors with GL code 61xx")
- Global distribution (if multi-region needed)

---

#### Trigger 3: Multi-Region Deployment

**Current Bottleneck:** Single-region (East US)

**Migration Path:** Event Grid + Geo-Redundant Storage

```bicep
// Event Grid for inter-region events
resource eventGridTopic 'Microsoft.EventGrid/topics@2022-06-15' = {
  name: 'invoice-events'
  location: 'global'
  properties: {
    inputSchema: 'CloudEventSchemaV1_0'
  }
}

// Function subscriptions in multiple regions
resource functionAppEastUS 'Microsoft.Web/sites@2022-03-01' = {
  location: 'eastus'
  // Subscribe to Event Grid
}

resource functionAppWestEurope 'Microsoft.Web/sites@2022-03-01' = {
  location: 'westeurope'
  // Subscribe to Event Grid
}
```

**Benefits:**
- <50ms latency for European users
- Disaster recovery across regions
- Active-active processing

**Cost Impact:** 2x infrastructure cost

---

## Official References

### Azure Functions
- [Python Developer Guide](https://learn.microsoft.com/en-us/azure/azure-functions/functions-reference-python)
- [TypeScript Developer Guide](https://learn.microsoft.com/en-us/azure/azure-functions/functions-reference-node)
- [Durable Functions Patterns](https://learn.microsoft.com/en-us/azure/azure-functions/durable/durable-functions-overview#application-patterns)
- [Performance Best Practices](https://learn.microsoft.com/en-us/azure/azure-functions/performance-reliability)

### Microsoft Graph API
- [Webhooks Overview](https://learn.microsoft.com/en-us/graph/webhooks)
- [Change Notifications](https://learn.microsoft.com/en-us/graph/webhooks-lifecycle)
- [Throttling Guidance](https://learn.microsoft.com/en-us/graph/throttling)
- [Mail API Reference](https://learn.microsoft.com/en-us/graph/api/resources/mail-api-overview)

### Azure Storage
- [Table Storage Design Guide](https://learn.microsoft.com/en-us/azure/storage/tables/table-storage-design-guide)
- [Queue Storage Best Practices](https://learn.microsoft.com/en-us/azure/storage/queues/storage-performance-checklist)
- [Blob Storage Performance Tuning](https://learn.microsoft.com/en-us/azure/storage/blobs/storage-performance-checklist)

### Infrastructure as Code
- [Bicep Documentation](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/)
- [Bicep Best Practices](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/best-practices)
- [Infrastructure Testing](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/test-toolkit)

### Observability
- [OpenTelemetry Azure Monitor](https://learn.microsoft.com/en-us/azure/azure-monitor/app/opentelemetry-enable)
- [Application Insights for Functions](https://learn.microsoft.com/en-us/azure/azure-functions/functions-monitoring)
- [KQL Query Language](https://learn.microsoft.com/en-us/azure/data-explorer/kusto/query/)

### Security
- [Managed Identity Best Practices](https://learn.microsoft.com/en-us/azure/active-directory/managed-identities-azure-resources/managed-identity-best-practice-recommendations)
- [Key Vault Integration](https://learn.microsoft.com/en-us/azure/key-vault/general/overview)
- [Azure RBAC](https://learn.microsoft.com/en-us/azure/role-based-access-control/overview)

---

**Version:** 2.0 (Lessons Learned Edition)
**Last Updated:** 2024-11-23
**Maintained By:** Engineering Team
**Replaces:** `docs/ARCHITECTURE.md`
