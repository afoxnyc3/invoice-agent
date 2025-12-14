# Invoice Agent - System Architecture

This document describes the technical architecture, system design, and specifications for the Invoice Agent automated invoice processing system.

> **For development workflow and coding standards, see [../CLAUDE.md](../CLAUDE.md)**

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Overview](#system-overview)
3. [System Components](#system-components)
4. [Azure Resources & Infrastructure](#azure-resources--infrastructure)
5. [Data Models & Schemas](#data-models--schemas)
6. [Data Flow & Processing](#data-flow--processing)
7. [Security Architecture](#security-architecture)
8. [Error Handling & Retry Logic](#error-handling--retry-logic)
9. [Scalability & Performance](#scalability--performance)
10. [Monitoring & Observability](#monitoring--observability)
11. [Design Decisions & Rationale](#design-decisions--rationale)
12. [Integration Points](#integration-points)
13. [Deployment Architecture](#deployment-architecture)
14. [Current Implementation Status](#current-implementation-status)
15. [Future Enhancements](#future-enhancements)

---

## Executive Summary

### Problem Statement
Manual invoice processing from email takes 5+ minutes per invoice, with frequent errors, no audit trail, and no standardization. Finance team spends significant time extracting vendor information and applying GL codes before routing to accounts payable.

### Solution
Automated Azure serverless system that extracts vendor information from email, applies GL codes from a lookup table, routes enriched invoices to AP, and sends Teams notifications. Approval workflow remains in NetSuite (out of scope).

### Key Characteristics
- **Serverless**: Azure Functions on Consumption tier
- **Event-Driven**: Queue-based decoupling between processing stages
- **Fast**: <60 seconds end-to-end processing
- **Reliable**: 99.9% uptime target with automated retry
- **Scalable**: Auto-scale 0-200 instances based on load
- **Secure**: Managed Identity authentication, Key Vault secrets

### Success Metrics
- **Processing Time**: <60 seconds per invoice
- **Auto-routing Rate**: >80% (known vendors)
- **Unknown Vendor Rate**: <10%
- **Error Rate**: <1%
- **Test Coverage**: 93% (exceeds 85% CI threshold)

---

## System Overview

### Core Architecture

**Event-Driven Webhook Architecture (Nov 2024)**

```
┌─────────────────────────────────────────────────────────────────┐
│                        Shared Mailbox                            │
│                    (invoices@example.com)                       │
└────────────────────────────┬────────────────────────────────────┘
                             │ Email arrives
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                   Microsoft Graph API                            │
│  - Detects new email instantly (<5 seconds)                     │
│  - Sends change notification via webhook                        │
└──────────────┬─────────────────────────────┬────────────────────┘
               │ HTTP POST (<10 sec)         │
               ↓                             │ Subscription Management
┌─────────────────────────────────────────┐  │
│        MailWebhook Function (HTTP)      │  │
│  - HTTP trigger receives notification   │  │
│  - Validates client state (security)    │  │
│  - Queues notification for processing   │  │
│  - Returns 202 quickly (<3 sec)         │  │
└──────────────┬──────────────────────────┘  │
               │ Queue: webhook-notifications│
               ↓                             │
┌─────────────────────────────────────────┐  │
│   MailWebhookProcessor Function (Queue) │  │
│  - Fetches email details via Graph API  │  │
│  - Downloads attachments to Blob        │  │
│  - Extracts vendor from PDF (AI)        │  │
│  - Creates RawMail queue message        │  │
│  - Marks email as read                  │  │
└──────────────┬──────────────────────────┘  │
               │ Queue: raw-mail             │
               ↓                             │
┌─────────────────────────────────────────┐  │
│     ExtractEnrich Function (Queue)      │  │
│  - Extracts invoice fields from PDF     │  │
│  - Uses AI-extracted vendor name        │  │
│  - Lookup in VendorMaster table         │  │
│  - Apply GL codes and metadata          │  │
│  - Deduplication check (skip processed) │  │
└──────────────┬──────────────────────────┘  │
               │ Queue: to-post              │
               ↓                             │
┌─────────────────────────────────────────┐  │
│        PostToAP Function (Queue)        │  │
│  - Compose standardized email           │  │
│  - Send to AP mailbox via Graph         │  │
│  - Log to InvoiceTransactions           │  │
└──────────────┬──────────────────────────┘  │
               │ Queue: notify               │
               ↓                             │
┌─────────────────────────────────────────┐  │
│         Notify Function (Queue)         │  │
│  - Format Teams message                 │  │
│  - Post to webhook                      │  │
│  - Non-critical (no retry)              │  │
└─────────────────────────────────────────┘  │
                                             │
┌─────────────────────────────────────────┐  │
│  SubscriptionManager Function (Timer)   │◄─┘
│  - Timer: Every 6 days                  │
│  - Renews Graph API subscription        │
│  - Stores state in GraphSubscriptions   │
│  - Ensures webhooks stay active         │
└─────────────────────────────────────────┘

┌────────────────────────── FALLBACK ──────────────────────────────┐
│  MailIngest Function (Timer - Hourly Safety Net)                 │
│  - Timer: Every hour                                             │
│  - Polls for any missed emails                                   │
│  - Downloads attachments, extracts vendor from PDF               │
│  - Queues to raw-mail for ExtractEnrich processing               │
└──────────────────────────────────────────────────────────────────┘

┌────────────────────────── UTILITIES ─────────────────────────────┐
│  AddVendor Function (HTTP) - POST /api/AddVendor                 │
│  Health Function (HTTP) - GET /api/Health                        │
└──────────────────────────────────────────────────────────────────┘
```

**Key Architecture Changes (Nov 2024):**
- **Primary Path**: Event-driven webhooks (<10 sec latency, 95% of emails)
- **Fallback Path**: Hourly polling (safety net, 5% of emails)
- **Cost Reduction**: 70% savings ($0.60/month vs $2.00/month)
- **Function Count**: 9 - Includes MailWebhook, MailWebhookProcessor, SubscriptionManager, Health
- **New Queue**: `webhook-notifications` for webhook-based ingestion
- **New Table**: `GraphSubscriptions` for subscription state management

### Technology Stack (as of Nov 2024)
- **Python**: 3.11
- **Azure Functions Runtime**: 4.x on Linux
- **MSAL**: 1.25.0 (Microsoft Authentication Library)
- **Pydantic**: 2.x (strict validation, no v1 compat mode)
- **Azure SDK**: Latest stable versions
- **pdfplumber**: 0.10.3 (PDF text extraction)
- **Azure OpenAI**: 1.54.0 (Intelligent vendor extraction)
- **Pytest**: Testing framework

---

## System Components

### Function Specifications

#### 1. MailWebhook Function (NEW - Nov 2024)
**Purpose**: Receive real-time email notifications from Microsoft Graph API

- **Trigger**: HTTP POST (webhook endpoint)
- **Input**: Graph API change notification
- **Output**: Queue message to `webhook-notifications`
- **Processing**:
  1. **MODE 1 - Validation Handshake**: Return validation token during subscription creation
  2. **MODE 2 - Notification Processing**:
     - Validate `clientState` for security
     - Extract notification metadata (subscription ID, resource, change type)
     - Queue notification to `webhook-notifications` for processing
     - Return 202 Accepted to Graph (must respond quickly <3 seconds)
- **Max Execution Time**: 30 seconds
- **Scaling**: Auto-scale based on HTTP requests
- **Security**: Client state validation prevents unauthorized notifications
- **Design**: Lightweight endpoint that queues notifications immediately to avoid timeout

#### 2. MailWebhookProcessor Function (NEW - Nov 2024)
**Purpose**: Process webhook notifications and fetch email details

- **Trigger**: Queue trigger on `webhook-notifications`
- **Input**: Webhook notification message from MailWebhook
- **Output**: Queue message to `raw-mail`
- **Processing**:
  1. Parse webhook notification (extract mailbox and message ID from resource path)
  2. Fetch email details via Graph API (`get_email`)
  3. Check email loop prevention (skip system-generated emails)
  4. Download attachments to Blob Storage (`invoices/raw/`)
  5. Create RawMail queue message with email metadata
  6. Queue to `raw-mail` for ExtractEnrich processing
  7. Mark email as read
- **Max Execution Time**: 5 minutes
- **Scaling**: Auto-scale based on queue depth
- **Shared Logic**: Uses `shared.email_processor` module (same as MailIngest)
- **Why Separate?**: Decouples fast HTTP response from slow email fetching

#### 3. SubscriptionManager Function (NEW - Nov 2024)
**Purpose**: Maintain Graph API webhook subscriptions

- **Trigger**: Timer (cron: `0 0 0 */6 * *` - every 6 days)
- **Input**: None (auto-managed)
- **Output**: Updates GraphSubscriptions table
- **Processing**:
  1. Query GraphSubscriptions table for existing subscription
  2. Check expiration (Graph max: 7 days for mail resources)
  3. **If exists & expires in <48 hours**: Renew subscription via Graph API
  4. **If not exists**: Create new subscription with validation handshake
  5. Store subscription ID, expiration, and metadata
  6. Deactivate old subscriptions
- **Max Execution Time**: 2 minutes
- **Scaling**: Single instance (timer-triggered)
- **Why 6 days?**: Renews before 7-day expiration, with 24-hour buffer

#### 4. MailIngest Function (MODIFIED - Nov 2024)
**Purpose**: Fallback polling for missed emails (safety net)

- **Trigger**: Timer (cron: `0 0 * * * *` - every hour, **was 5 minutes**)
- **Input**: None (polls Graph API)
- **Output**: Queue message to `raw-mail`
- **Processing**:
  1. Authenticate to Graph API with service principal
  2. Query unread emails from shared mailbox
  3. Check email loop prevention (skip system-generated emails)
  4. Download attachments to Blob Storage (`invoices/raw/`)
  5. Create RawMail queue message with email metadata
  6. Queue to `raw-mail` for ExtractEnrich processing
  7. Mark email as read
- **Max Execution Time**: 5 minutes
- **Scaling**: Single instance (timer-triggered)
- **Shared Logic**: Uses `shared.email_processor` module (same as MailWebhookProcessor)
- **Role Change**: Primary ingestion → Fallback/safety net (handles ~5% of emails)

#### 5. ExtractEnrich Function
**Purpose**: Extract vendor and enrich with GL codes

- **Trigger**: Queue (`raw-mail`)
- **Input**: Queue message with email metadata
- **Output**: Queue message to `to-post`
- **Processing**:
  1. Extract vendor from email sender domain
  2. Fallback to subject line parsing if needed
  3. Lookup vendor in VendorMaster table
  4. Apply 4 enrichment fields (see [Data Models](#data-models--schemas))
  5. Flag unknown vendors
  6. Queue enriched message
- **Max Execution Time**: 5 minutes
- **Scaling**: Auto-scale based on queue depth

#### 6. PostToAP Function
**Purpose**: Send enriched invoice to AP mailbox

- **Trigger**: Queue (`to-post`)
- **Input**: Queue message with enriched data
- **Output**: Queue message to `notify`
- **Processing**:
  1. Compose standardized email
  2. Attach original invoice from Blob Storage
  3. Send via Graph API to AP mailbox
  4. Log transaction to InvoiceTransactions table
  5. Queue notification message
- **Max Execution Time**: 5 minutes
- **Scaling**: Auto-scale based on queue depth

#### 7. Notify Function
**Purpose**: Post status notifications to Teams

- **Trigger**: Queue (`notify`)
- **Input**: Queue message with notification details
- **Output**: None (webhook call)
- **Processing**:
  1. Format Teams message card
  2. Post to webhook URL
  3. Log response (non-critical - no retry)
- **Max Execution Time**: 2 minutes
- **Scaling**: Auto-scale based on queue depth

#### 8. AddVendor Function
**Purpose**: HTTP endpoint for vendor management

- **Trigger**: HTTP POST
- **Input**: JSON payload with vendor data
- **Output**: JSON response with status
- **Processing**:
  1. Validate vendor data (Pydantic)
  2. Insert/update VendorMaster table
  3. Return success/error response
- **Max Execution Time**: 30 seconds
- **Scaling**: Auto-scale based on HTTP requests
- **Rate Limit**: 10 requests/minute per client IP

#### 9. Health Function
**Purpose**: Health check endpoint for monitoring and load balancers

- **Trigger**: HTTP GET
- **Input**: None
- **Output**: JSON health status
- **Processing**:
  1. Check Storage Account connectivity
  2. Verify required configuration present
  3. Return health status with version info
- **Max Execution Time**: 30 seconds
- **Scaling**: Auto-scale based on HTTP requests
- **Rate Limit**: 60 requests/minute per client IP
- **Response Format**:
  ```json
  {
    "status": "healthy",
    "version": "1.0.0",
    "timestamp": "2024-12-04T15:00:00Z",
    "checks": {
      "storage": "ok",
      "config": "ok"
    }
  }
  ```

---

## Azure Resources & Infrastructure

### Compute Layer
**Azure Functions** (Consumption Plan Y1)
- **Runtime**: Python 3.11 on Linux
- **Scaling**: 0-200 instances auto-scale
- **Cold Start**: ~2-4 seconds
- **Timeout**: 5 minutes default (configurable)
- **Region**: Single region for dev, geo-redundant for prod

### AI Layer
**Azure OpenAI** (oai-invoice-agent-prod)
- **Model**: gpt-4o-mini (Standard tier)
- **Purpose**: Intelligent vendor extraction from PDF invoices
- **Endpoint**: East US region
- **Capacity**: 10K tokens per minute
- **Cost**: ~$0.001 per invoice (~$1.50/month at 50 invoices/day)
- **Latency**: ~500ms per extraction

### Storage Layer
**Storage Account** (Standard_LRS for dev, Standard_GRS for prod)

**Tables:**
- `VendorMaster`: Vendor lookup data (~100-1000 vendors)
- `InvoiceTransactions`: Audit log (7-year retention)
- `GraphSubscriptions`: Webhook subscription state management
- `RateLimits`: HTTP endpoint rate limiting data

**Blob Containers:**
- `invoices`: Invoice PDF attachments (`raw/` prefix for new uploads)
- `github-actions-deploy`: CI/CD deployment artifacts (ZIP packages)
- `azure-webjobs-*`: Azure-managed containers (hosts, secrets)
- `scm-releases`: Azure-managed deployment container

**Queues:**
- `webhook-notifications`: **NEW** - Real-time email notifications from MailWebhook (primary path)
- `raw-mail`: Unprocessed emails from MailIngest (fallback path)
- `to-post`: Enriched invoices for AP routing
- `notify`: Notifications for Teams
- `*-poison`: Dead letter queues (3 retry attempts)

### Security Layer
**Managed Identity** (System-assigned)
- Graph API access (Mail.Read, Mail.Send)
- Storage operations (Tables, Blobs, Queues)
- Key Vault access (secrets retrieval)

**Key Vault** (Standard tier)
- `graph-tenant-id`: Azure AD tenant identifier
- `graph-client-id`: App registration client ID
- `graph-client-secret`: Service principal secret
- `graph-client-state`: Webhook validation secret (security)
- `invoice-mailbox`: Shared mailbox address for invoice ingestion
- `ap-email-address`: AP mailbox address for routing
- `teams-webhook-url`: Teams channel webhook URL
- `azure-openai-endpoint`: Azure OpenAI resource endpoint
- `azure-openai-api-key`: Azure OpenAI API key

### Monitoring Layer
**Application Insights**
- Custom metrics (processing rate, match rate, etc.)
- Distributed tracing with correlation IDs
- Log aggregation (90-day retention)
- Alert rules (function failures, queue backup, error rate)

---

## Data Models & Schemas

### VendorMaster Table Schema

Table Storage schema for vendor lookup:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| PartitionKey | string | Always "Vendor" | "Vendor" |
| RowKey | string | vendor_name_lower | "adobe_com" |
| VendorName | string | Display name | "Adobe Inc" |
| ProductCategory | string | Direct or Reseller | "Direct" |
| ExpenseDept | string | Department code | "IT" |
| AllocationSchedule | string | Allocation code | "1" |
| GLCode | string | General ledger code | "6100" |
| VenueRequired | bool | Venue extraction flag | false |
| Active | bool | Soft delete flag | true |
| UpdatedAt | datetime | Last modified | "2024-11-09T12:00:00Z" |

> **Note:** `BillingParty` is not stored in VendorMaster. It comes from the `DEFAULT_BILLING_PARTY` environment variable at enrichment time.

**Query Pattern**: Direct lookup by RowKey
```python
# Example query
entity = table_client.get_entity(
    partition_key="Vendor",
    row_key="adobe_com"
)
```

### InvoiceTransactions Table Schema

Table Storage schema for audit trail:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| PartitionKey | string | YYYYMM format | "202411" |
| RowKey | string | ULID (unique, sortable) | "01JCK3Q7H8ZVXN3BARC9GWAEZM" |
| TransactionId | string | Same as RowKey | "01JCK3Q7H8ZVXN3BARC9GWAEZM" |
| VendorName | string | Identified vendor | "Adobe Inc" |
| SenderEmail | string | Original sender | "billing@adobe.com" |
| ExpenseDept | string | From lookup | "IT" |
| GLCode | string | From lookup | "6100" |
| AllocationSchedule | string | From lookup | "MONTHLY" |
| BillingParty | string | From config | "Company HQ" |
| Status | string | processed/unknown/error | "processed" |
| BlobUrl | string | Attachment location | "https://..." |
| ProcessedAt | datetime | Completion time | "2024-11-09T14:30:00Z" |
| ErrorMessage | string | If failed | null |

**Query Pattern**: Partition by month for efficient time-range queries
```python
# Example query for November 2024
entities = table_client.query_entities(
    query_filter="PartitionKey eq '202411'"
)
```

### GraphSubscriptions Table Schema (NEW - Nov 2024)

Table Storage schema for webhook subscription management:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| PartitionKey | string | Always "GraphSubscription" | "GraphSubscription" |
| RowKey | string | subscription_id | "da93534d-0c4c-4d9d-9b9e-c429c0549221" |
| SubscriptionId | string | Graph API subscription ID | "da93534d-0c4c-4d9d-9b9e-c429c0549221" |
| Resource | string | Monitored resource path | "users/invoices@company.com/mailFolders('Inbox')/messages" |
| ExpirationDateTime | datetime | When subscription expires | "2025-11-23T22:25:47Z" |
| IsActive | bool | Current status | true |
| CreatedAt | datetime | Creation timestamp | "2025-11-20T18:30:00Z" |
| LastRenewed | datetime | Last renewal timestamp | "2025-11-20T18:30:00Z" |

**Query Pattern**: Single active subscription per resource
```python
# Query for active subscription
query_filter = "PartitionKey eq 'GraphSubscription' and IsActive eq true"
entities = list(table_client.query_entities(query_filter))
```

**Subscription Lifecycle:**
- Created by SubscriptionManager on first run
- Renewed every 6 days (Graph max: 7 days for mail resources)
- Marked inactive when replaced by new subscription
- Subscription ID stored for renewal/deletion operations

### RateLimits Table Schema

Table Storage schema for HTTP endpoint rate limiting:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| PartitionKey | string | Endpoint name | "MailWebhook" |
| RowKey | string | Client IP + minute bucket | "192.168.1.1_202412041530" |
| RequestCount | int | Number of requests in window | 45 |
| WindowStart | datetime | Start of rate limit window | "2024-12-04T15:30:00Z" |
| LastRequest | datetime | Most recent request time | "2024-12-04T15:30:45Z" |

**Query Pattern**: Check current window for client
```python
# Check rate limit for client IP
row_key = f"{client_ip}_{current_minute}"
entity = table_client.get_entity(
    partition_key=endpoint_name,
    row_key=row_key
)
```

**TTL**: Entries expire after 5 minutes (cleanup via Table Storage lifecycle)

### Queue Message Schemas

#### raw-mail Queue
Message from MailIngest to ExtractEnrich:

```json
{
  "id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
  "sender": "billing@adobe.com",
  "subject": "Invoice #12345 - November 2024",
  "blob_url": "https://storage.blob.core.windows.net/invoices/raw/invoice123.pdf",
  "received_at": "2024-11-09T14:00:00Z",
  "attachment_count": 1
}
```

#### to-post Queue
Message from ExtractEnrich to PostToAP:

```json
{
  "id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
  "vendor_name": "Adobe Inc",
  "expense_dept": "IT",
  "gl_code": "6100",
  "allocation_schedule": "MONTHLY",
  "billing_party": "Company HQ",
  "blob_url": "https://storage.blob.core.windows.net/invoices/raw/invoice123.pdf",
  "sender_email": "billing@adobe.com",
  "subject": "Invoice #12345 - November 2024",
  "status": "enriched"
}
```

#### notify Queue
Message from PostToAP to Notify:

```json
{
  "type": "success",
  "message": "Processed: Adobe Inc - GL 6100",
  "transaction_id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
  "details": {
    "vendor": "Adobe Inc",
    "gl_code": "6100",
    "expense_dept": "IT",
    "sender": "billing@adobe.com"
  }
}
```

**Message Types**:
- `success`: Invoice processed successfully
- `unknown`: Unknown vendor (manual review needed)
- `error`: Processing failure

### Pydantic Data Models

All queue messages use Pydantic for validation:

**RawMail**: Email ingestion schema
**EnrichedInvoice**: Vendor-enriched data
**NotificationMessage**: Teams webhook payload

All models require strict validation (no coercion, no extra fields allowed).

### Teams Notification Formats

Notifications are sent as **Adaptive Cards v1.4** wrapped in a Power Automate message envelope.
See `src/Notify/__init__.py` for the actual implementation.

#### Payload Structure (Power Automate Format)
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
        {"type": "TextBlock", "text": "✅ Invoice Processed", "weight": "Bolder", "size": "Medium", "wrap": true},
        {"type": "FactSet", "facts": [
          {"title": "Vendor", "value": "Adobe Inc"},
          {"title": "Gl Code", "value": "6100"},
          {"title": "Transaction Id", "value": "01JCK3Q7H8ZVXN3BARC9GWAEZM"}
        ]}
      ]
    }
  }]
}
```

#### Notification Types

| Type | Emoji | Use Case |
|------|-------|----------|
| `success` | ✅ | Invoice processed successfully |
| `unknown` | ⚠️ | Unknown vendor detected |
| `error` | ❌ | Processing failure |
| `duplicate` | 🔄 | Duplicate invoice detected |

#### Power Automate Flow Configuration

The flow must extract the card content and serialize it:
```
string(triggerBody()?['attachments']?[0]?['content'])
```

See `docs/integrations/TEAMS_POWER_AUTOMATE.md` for detailed setup instructions.

---

## Data Flow & Processing

### 1. Email Ingestion (MailIngest)

```
Timer(hourly) → Graph API → Filter Unread → Download Attachments → Queue Message → Mark Read
```

**Processing Steps**:
1. Timer trigger fires every hour (fallback for missed webhooks)
2. Authenticate to Graph API (MSAL with service principal)
3. Query shared mailbox for unread emails
4. Process up to 50 emails per execution
5. Download attachments to Blob Storage
6. Create queue message with metadata
7. Mark email as read
8. Handle throttling (honor retry-after headers)

**Vendor Extraction Hierarchy**:
1. Email domain mapping (e.g., `@adobe.com` → "adobe_com")
2. Subject line parsing (regex patterns)
3. Default to "UNKNOWN" if no match

### 2. Vendor Enrichment (ExtractEnrich)

```
Queue Message → PDF Extraction (AI) → Fallback to Email Domain → Table Lookup → Apply Metadata → Queue Enriched
```

**Processing Steps**:
1. Receive message from `raw-mail` queue
2. **NEW: Extract vendor from PDF using Azure OpenAI**
   - Download PDF from blob storage
   - Extract text from first page (pdfplumber)
   - Use GPT-4o-mini to identify vendor name (~500ms, $0.001/invoice)
   - If successful: Use extracted vendor name
3. **Fallback**: Extract vendor from email sender domain (if PDF extraction fails)
4. Normalize vendor name (lowercase, replace dots)
5. Lookup in VendorMaster table
6. If found: Apply enrichment fields
7. If not found: Flag as "UNKNOWN"
8. Queue enriched message to `to-post`

**Enrichment Fields Applied** (from VendorMaster lookup):
- **ExpenseDept**: Department code for allocation (e.g., "IT", "Marketing")
- **AllocationSchedule**: Allocation schedule code (e.g., "1", "3", "14")
- **GLCode**: General ledger code (e.g., "6100")
- **BillingParty**: Entity responsible for payment (from `DEFAULT_BILLING_PARTY` config)

**Invoice Fields Extracted** (from PDF using Azure OpenAI):
- **InvoiceAmount**: Detected amount with currency (e.g., "1,234.56")
- **Currency**: Currency code (e.g., "USD", "EUR")
- **DueDate**: Payment due date (e.g., "2024-12-15")
- **PaymentTerms**: Payment terms (e.g., "Net 30")

**Reseller Handling**:
- If `ProductCategory == "Reseller"`, invoice is flagged as "unknown" status for manual review
- Prevents automatic enrichment of VAR (Value-Added Reseller) invoices that require venue extraction

**Fallback Behavior**:
- Unknown vendors processed with "UNKNOWN" values
- Notification sent to Teams for manual review
- Invoice still routed to AP (not blocked)

### 3. AP Routing (PostToAP)

```
Enriched Message → Compose Email → Send via Graph → Log Transaction → Queue Notify
```

**Processing Steps**:
1. Receive message from `to-post` queue
2. Compose standardized email:
   - Subject: `Invoice: {Vendor} - GL {GLCode}`
   - Body: HTML table with metadata
   - Attachment: Original invoice from Blob Storage
3. Send via Graph API to AP mailbox
4. Log transaction to InvoiceTransactions table
5. Queue notification message to `notify`

**Email Format**:
```
Subject: Invoice: Adobe Inc - GL 6100

Body:
Invoice processed via automation. Details below:

Vendor: Adobe Inc
Department: IT
GL Code: 6100
Allocation Schedule: MONTHLY
Billing Party: Company HQ
Transaction ID: 01JCK3Q7H8ZVXN3BARC9GWAEZM
Received: 2024-11-09 14:00:00
Processed: 2024-11-09 14:30:00

[Attachment: invoice123.pdf]
```

### 4. Notification (Notify)

```
Notify Message → Format Card → Post to Teams → Log Response
```

**Processing Steps**:
1. Receive message from `notify` queue
2. Format Teams message card (success/warning/error)
3. Post to webhook URL
4. Log response (non-critical - no retry on failure)

**Non-Critical Path**:
- Teams webhook failures don't block processing
- Invoice still processed even if notification fails
- Errors logged for monitoring

---

## Security Architecture

### Authentication & Authorization

**Managed Identity (System-Assigned)**:
- All Azure resource access uses Managed Identity
- No credentials stored in code or config files
- Automatic credential rotation

**Graph API Authentication**:
- App-only authentication with client credentials
- Service Principal with certificate or secret
- Permissions: `Mail.Read`, `Mail.Send` (application-level)
- Token caching with 1-hour TTL

**RBAC (Role-Based Access Control)**:
- Function App: Storage Blob Data Contributor
- Function App: Storage Queue Data Contributor
- Function App: Storage Table Data Contributor
- Function App: Key Vault Secrets User
- Least privilege for all resources

### Network Security

**Current State** (MVP):
- Public endpoints (Function App, Storage)
- TLS 1.2 minimum for all connections
- CORS disabled on all functions

**Future Enhancements**:
- Private Endpoints for production storage
- IP restrictions on Function App
- VNet integration for secure connectivity

### Data Security

**Encryption at Rest**:
- Storage service encryption (SSE) enabled by default
- Key managed by Azure (Microsoft-managed keys)

**Encryption in Transit**:
- TLS 1.2 minimum for all communications
- HTTPS enforced for all endpoints

**Audit Logging**:
- All operations logged to Application Insights
- Correlation IDs for request tracing
- No PII in log messages

**PII Handling**:
- Email addresses stored in InvoiceTransactions (audit requirement)
- No credit card or payment information
- 7-year retention for compliance

### Infrastructure Hardening (Dec 2024)

Based on Azure Quick Review (AZQR) security scan, implemented Phase 1 compliance improvements:

**Storage Account**:
- Container soft delete enabled (30 days prod, 7 days dev)
- Blob soft delete enabled (30 days prod, 7 days dev)
- TLS 1.2 minimum, HTTPS-only
- Public blob access disabled

**Key Vault**:
- Soft delete enabled (90 days)
- Purge protection enabled
- Diagnostic settings → Log Analytics
- AuditEvent logging for compliance

**Function App**:
- Auto-heal enabled
  - Triggers: 10x 500 errors in 5 min, or 5x slow requests (>60s) in 5 min
  - Action: Recycle worker process
  - Min execution time: 60 seconds before recycle

**Resource Governance**:
- Standard tags applied to all resources:
  - Project: InvoiceAgent
  - Environment: prod/dev
  - CostCenter: Finance-AP
  - Application: invoice-agent
  - CreatedDate: 2024-11-14
  - ManagedBy: Bicep

**Cost Impact**: $0-2/month for diagnostic log ingestion (all other changes are free Azure features)

### Rate Limiting

HTTP endpoints are protected by sliding-window rate limiting to prevent abuse:

| Endpoint | Limit | Window | Storage |
|----------|-------|--------|---------|
| MailWebhook | 100 requests | 1 minute | RateLimits table |
| AddVendor | 10 requests | 1 minute | RateLimits table |
| Health | 60 requests | 1 minute | RateLimits table |

**Implementation** (`shared/rate_limiter.py`):
- Sliding window algorithm with minute granularity
- Client identified by IP address (X-Forwarded-For header)
- Exceeded limits return HTTP 429 Too Many Requests
- Can be disabled via `RATE_LIMIT_DISABLED` env var for testing

### Email Loop Prevention

Multiple safeguards prevent infinite email loops between system and mailboxes:

**Implementation** (`shared/email_processor.py` - `should_skip_email()`):

1. **Recipient Validation**: Validates recipient is NOT the `INVOICE_MAILBOX`
2. **Allowed Recipients List**: If `ALLOWED_AP_EMAILS` configured, recipient must be in list
3. **System Email Detection**: Skips emails matching pattern `^Invoice:\s+.+\s+-\s+GL\s+\d{4}$`
4. **Reply Detection**: Skips replies to vendor registration emails
5. **Sender Filtering**: Filters out emails from system mailbox in MailIngest/MailWebhookProcessor

See [ADR-0027](adr/0027-email-loop-prevention.md) for design rationale.

### Deduplication Strategy

Multi-level deduplication prevents duplicate invoice processing and payments:

**Level 1 - Message Deduplication** (`shared/deduplication.py`):
- Key: `original_message_id` (Graph API message ID)
- Scope: Prevents same email from being processed twice
- Storage: InvoiceTransactions table lookup

**Level 2 - Invoice Hash Deduplication**:
- Key: SHA256 hash of (vendor_name + sender_email + received_date)
- Scope: Prevents duplicate invoices from same vendor/sender/date
- Lookback: 90 days in InvoiceTransactions table

**Level 3 - Atomic Transaction Claim**:
- Mechanism: Table Storage upsert with ETag checking
- Scope: Prevents race conditions in concurrent processing
- Effect: Only first processor wins, others skip gracefully

See [ADR-0028](adr/0028-message-id-deduplication.md) for design rationale.

---

## Error Handling & Retry Logic

### Transient Failures

**Retry Strategy**:
- 3 retries with exponential backoff (2s, 4s, 8s)
- Graph API throttling: Honor `Retry-After` headers
- Queue visibility timeout: 5 minutes
- Poison queue after 3 attempts

**Common Transient Errors**:
- Network timeouts
- Graph API throttling (429 status)
- Temporary storage unavailability
- Service disruptions

### Business Errors

**Handling Strategy**:
- Unknown vendor: Flag and continue with "UNKNOWN"
- Missing attachment: Process anyway, log warning
- Malformed email: Skip and mark as read
- Invalid email format: Log and continue

**No Blocking**:
- Business errors don't block queue processing
- Unknown vendors still routed to AP
- Manual review triggered via Teams notification

### Critical Failures

**Circuit Breaker Pattern**:
- Storage down: Open circuit after 5 failures
- Graph API auth failure: Alert ops, halt processing
- Key Vault unreachable: Use cached secrets (1hr TTL)

**Alerting**:
- High error rate (>5%): Immediate alert
- Queue backup (>50 messages): Warning alert
- Function failures: Critical alert
- SLO breaches: Management notification

### Error Recovery

**Automatic Recovery**:
- Transient errors: Retry mechanism
- Poison queue: Manual review and resubmit
- Unknown vendors: Add to VendorMaster and reprocess

**Manual Recovery**:
- Teams webhook down: Continue processing, fix webhook
- Malformed emails: Investigate and update parsing logic
- Storage corruption: Restore from backup

---

## Scalability & Performance

### Design Targets

| Metric | Target | Rationale |
|--------|--------|-----------|
| Throughput | 50 concurrent invoices | Current volume: 5-50/day |
| Latency | <60 seconds end-to-end | SLA requirement |
| Availability | 99.9% uptime | 43 min downtime/month |
| Storage | 7-year retention | Compliance requirement |
| Cold Start | <4 seconds | Python on Linux |

### Scaling Strategy

**Azure Functions**:
- Auto-scale 0-200 instances based on queue depth
- Consumption Plan for cost efficiency
- Single instance for timer triggers (MailIngest)
- Parallel processing for queue triggers

**Queues**:
- Parallel processing with visibility timeout
- Poison queues for failed messages
- Dead letter handling after 3 retries

**Storage**:
- Table Storage partitioned by month (PartitionKey=YYYYMM)
- Blob Storage with lifecycle management
- Batch operations for performance

**Monitoring**:
- Adaptive sampling for high volume
- Custom metrics for business KPIs
- Alert thresholds based on traffic patterns

### Performance Optimizations

**Connection Pooling**:
- Graph API client reused across invocations
- Table Storage client connection pooling
- HTTP session reuse

**Caching**:
- Graph API tokens cached (1-hour TTL)
- Key Vault secrets cached (1-hour TTL)
- Vendor lookups not cached (data freshness required)

**Batch Operations**:
- Table Storage batch writes where possible
- Queue message batching for high volume
- Blob Storage parallel uploads

**Lazy Loading**:
- Dependencies loaded on demand
- Function-specific imports only
- Minimal cold start overhead

---

## Monitoring & Observability

### Metrics Tracked

**Business Metrics**:
- Invoice processing rate (invoices/hour)
- Vendor match rate (%)
- Average processing time (seconds)
- Unknown vendor rate (%)
- Error rate by function (%)

**Technical Metrics**:
- Queue depths (messages)
- Function execution time (ms)
- Cold start frequency (%)
- Storage operations (ops/sec)
- API call latency (ms)

### Logging Strategy

**Structured JSON Logs**:
```json
{
  "timestamp": "2024-11-09T14:30:00Z",
  "level": "INFO",
  "correlation_id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
  "function": "ExtractEnrich",
  "message": "Vendor lookup successful",
  "vendor": "adobe_com",
  "elapsed_ms": 45
}
```

**Log Levels**:
- **ERROR**: Function failures, critical errors
- **WARNING**: Unknown vendors, missing data, retries
- **INFO**: Successful processing, state transitions
- **DEBUG**: Detailed processing steps (dev only)

**Correlation IDs**:
- ULID used for transaction correlation
- Passed through all queue messages
- Included in all log entries
- Traceable in Application Insights

**Retention**:
- Application Insights: 90 days
- Table Storage (InvoiceTransactions): 7 years
- Blob Storage (attachments): 7 years

### Alert Rules

| Alert | Threshold | Action |
|-------|-----------|--------|
| Function failures | >5 in 5 min | Page on-call |
| Queue backup | >50 messages | Investigate scaling |
| High error rate | >5% | Page on-call |
| SLO breach | <60s p95 | Investigate performance |
| Storage errors | >10 in 5 min | Check storage health |
| Graph API failures | >3 in 5 min | Check service principal |

### Dashboard Metrics

**Real-Time Dashboard**:
- Current queue depths
- Active function executions
- Error rate (rolling 5 min)
- Processing rate (invoices/hour)

**Daily Summary**:
- Total invoices processed
- Vendor match rate
- Unknown vendors list
- Error summary by type

---

## Design Decisions & Rationale

### Why Serverless (Azure Functions)?

**Decision**: Use Azure Functions Consumption Plan instead of containers or VMs

**Rationale**:
- **Variable Workload**: 5-50 invoices/day with sporadic arrival patterns
- **Cost-Effective**: Pay only for execution time (no idle costs)
- **Auto-Scaling**: Automatic scaling without management overhead
- **Fast Time to Market**: Focus on business logic, not infrastructure
- **Built-in Monitoring**: Application Insights integration

**Trade-offs**:
- Cold start latency (~2-4 seconds)
- 5-minute execution timeout
- Limited control over runtime environment

**Alternative Considered**: Container Apps (rejected due to higher cost for low volume)

### Why Table Storage over Cosmos DB?

**Decision**: Use Azure Table Storage for VendorMaster and InvoiceTransactions

**Rationale**:
- **Simple Key-Value Lookups**: Direct access by PartitionKey + RowKey
- **Cost**: 100x cheaper than Cosmos DB for this scale
- **Sufficient Scale**: Handles <1000 vendors easily
- **No Complex Queries**: Don't need SQL, indexing, or global distribution

**Trade-offs**:
- No complex querying (acceptable for our use case)
- No automatic indexing on arbitrary fields
- Limited to 1000 ops/sec per partition (sufficient for our volume)

**Alternative Considered**: Cosmos DB (rejected due to cost and complexity overkill)

### Why Queue-Based Decoupling?

**Decision**: Use Azure Storage Queues between processing stages

**Rationale**:
- **Decoupling**: Natural error boundaries between functions
- **Built-in Retry**: Automatic retry with exponential backoff
- **Resilience**: Functions can fail independently without blocking pipeline
- **Easy Monitoring**: Queue depth shows processing lag
- **Simple**: No complex message routing or pub/sub needed

**Trade-offs**:
- Eventual consistency (acceptable for our use case)
- No message ordering guarantees
- Limited message size (64KB)

**Alternative Considered**: Service Bus (rejected as overkill for simple queuing)

### Why Email Routing (Not NetSuite Direct)?

**Decision**: Route enriched invoices via email to AP, not direct NetSuite API integration

**Rationale**:
- **Maintains Existing Workflow**: AP team familiar with email-based process
- **No NetSuite Integration**: Avoids complexity of NetSuite API, authentication, rate limits
- **Faster MVP**: Email integration is simpler and faster to implement
- **Flexibility**: Easy to change AP endpoint without modifying NetSuite
- **Audit Trail**: Email provides natural audit trail

**Trade-offs**:
- Manual approval still required in NetSuite
- Not end-to-end automation
- Email could fail (but we have retry)

**Alternative Considered**: Direct NetSuite API (planned for Phase 2)

### Why Simple Teams Webhooks (Not Bot Framework)?

**Decision**: Use simple webhook notifications instead of Teams Bot Framework

**Rationale**:
- **Simple**: Just POST JSON to webhook URL
- **No Authentication**: Webhook URL is the secret
- **Sufficient**: Don't need interactive buttons or conversations
- **Fast**: No bot registration or complex setup
- **Reliable**: No bot framework dependencies

**Trade-offs**:
- No interactive actions (acceptable - notifications only)
- No conversations or replies
- Limited formatting options

**Alternative Considered**: Teams Bot Framework (rejected as overkill for notifications)

---

## Integration Points

### Microsoft Graph API

**Purpose**: Read emails from shared mailbox, send to AP mailbox

**Authentication**:
- App-only authentication (no user context)
- Service Principal with client secret or certificate
- MSAL library for token management
- Token caching (1-hour TTL)

**Permissions** (Application-level):
- `Mail.Read`: Read emails from shared mailbox
- `Mail.Send`: Send enriched invoices to AP
- Admin consent required

**Endpoints Used**:
- `GET /users/{mailbox}/messages`: List emails
- `GET /users/{mailbox}/messages/{id}`: Get email details
- `GET /users/{mailbox}/messages/{id}/attachments`: Download attachments
- `POST /users/{mailbox}/sendMail`: Send emails
- `PATCH /users/{mailbox}/messages/{id}`: Mark as read

**Throttling**:
- Honor `Retry-After` headers
- Exponential backoff on 429 status
- Max 3 retries before failure

**Error Handling**:
- 401 Unauthorized: Reauthenticate
- 403 Forbidden: Check permissions
- 429 Too Many Requests: Backoff and retry
- 500 Server Error: Retry with backoff

**Configuration**:
- Mailbox: Configured via `INVOICE_MAILBOX` environment variable
- Credentials: Stored in Key Vault

### Azure Table Storage

**Purpose**: Vendor lookup and transaction audit trail

**Tables**:
- **VendorMaster**: Vendor enrichment data
- **InvoiceTransactions**: Processing audit log

**Access Pattern**:
- Direct lookup by PartitionKey + RowKey
- Range queries by PartitionKey (month-based)
- No complex queries or secondary indexes

**Batch Operations**:
- Used for high-volume writes where possible
- Up to 100 operations per batch
- All operations in batch must share PartitionKey

**Error Handling**:
- 404 Not Found: Vendor doesn't exist (expected for unknown vendors)
- 409 Conflict: Entity already exists (idempotent operations)
- 500 Server Error: Retry with backoff

**Configuration**:
- Connection string from environment (uses Managed Identity)
- Automatic retry built into SDK

### Azure Blob Storage

**Purpose**: Store invoice attachments

**Containers**:
- `invoices/raw/`: Original email attachments
- `invoices/processed/`: Archived invoices (future)

**Access Pattern**:
- Upload attachments from MailIngest
- Download attachments in PostToAP
- Reference via URL in queue messages

**Lifecycle Management**:
- 7-year retention for compliance
- Auto-delete after retention period
- Archive tier for old invoices (future)

**Error Handling**:
- Retry on transient failures
- Verify upload with checksum
- Handle concurrent access gracefully

### Azure Storage Queues

**Purpose**: Decouple processing stages

**Queues**:
- `raw-mail`: Email metadata from MailIngest
- `to-post`: Enriched invoices for AP
- `notify`: Notifications for Teams
- `*-poison`: Dead letter queues

**Message Format**:
- JSON payload
- Base64-encoded by SDK
- Max 64KB per message

**Visibility Timeout**:
- 5 minutes (function execution time)
- Auto-extended if processing continues

**Poison Queue**:
- After 5 failed attempts
- Manual review and resubmit
- Alerts on poison queue depth

### Teams Webhooks (Power Automate)

**Purpose**: Post notifications to Teams channel via Power Automate flow

**Format**: Adaptive Cards v1.4 wrapped in Power Automate message envelope

**Authentication**: Power Automate webhook URL is the secret (no additional auth)

**Message Types**:
- Success (✅): Invoice processed
- Warning (⚠️): Unknown vendor
- Error (❌): Processing failure
- Duplicate (🔄): Duplicate invoice detected

**Non-Critical Path**:
- Webhook failures don't block processing
- Specific error handling for Timeout, ConnectionError, HTTPError
- Full error details logged for debugging

**Power Automate Flow**:
- Trigger: "When a Teams webhook request is received"
- Action: "Post card in a chat or channel"
- Expression: `string(triggerBody()?['attachments']?[0]?['content'])`

### Azure Key Vault

**Purpose**: Secure storage for secrets and configuration

**Secrets**:
- `graph-client-secret`: Service principal secret
- `azure-openai-endpoint`: Azure OpenAI resource endpoint
- `azure-openai-api-key`: Azure OpenAI API key
- `azure-openai-deployment`: Deployment name (e.g., "gpt-4o-mini")
- `ap-email-address`: AP mailbox address
- `teams-webhook-url`: Teams channel webhook
- `invoice-mailbox`: Shared mailbox for invoices

**Access**:
- Managed Identity authentication
- Secret caching (1-hour TTL)
- Automatic credential rotation

**Error Handling**:
- Use cached secrets if Key Vault unreachable
- Alert on sustained Key Vault failures
- Fallback to environment variables in dev

### Azure OpenAI (NEW - Nov 2024)

**Purpose**: Intelligent vendor name extraction from PDF invoices

**Model**: GPT-4o-mini (fast, cost-effective)

**Authentication**:
- API key authentication
- Keys stored in Key Vault
- Endpoint configured per environment

**API Usage**:
- Endpoint: `/chat/completions`
- Temperature: 0 (deterministic)
- Max tokens: 20 (vendor name only)
- API version: 2024-02-01

**Cost & Performance**:
- Cost: ~$0.001 per invoice (~$1.50/month at 50 invoices/day)
- Latency: ~500ms per PDF
- Accuracy: 95%+ vendor extraction rate

**Error Handling**:
- Graceful degradation to email domain extraction
- Log failures for monitoring
- No blocking - system continues on failure

**Prompt Strategy**:
```
System: Extract the vendor/company name from this invoice text.
        Return ONLY the company name, nothing else.
        Examples: 'Adobe Inc', 'Microsoft', 'Amazon Web Services'.
        If you cannot find a vendor name, return 'UNKNOWN'.
User: [PDF text, first 2000 chars]
```

**Integration Flow**:
1. `MailWebhookProcessor` uploads PDF to blob storage
2. Calls `shared.pdf_extractor.extract_vendor_from_pdf(blob_url)`
3. PDF downloaded and text extracted (pdfplumber)
4. Text sent to Azure OpenAI for vendor identification
5. Vendor name returned and queued in `RawMail.vendor_name`
6. `ExtractEnrich` uses vendor name for VendorMaster lookup

---

## Deployment Architecture

### Environments

#### Development
- **Purpose**: Local development and testing
- **Region**: Single region (East US)
- **Redundancy**: Standard_LRS (locally redundant)
- **Scale**: Minimal (1-2 instances)
- **Monitoring**: Basic Application Insights

#### Staging (Optional)
- **Purpose**: Manual testing before production (not used in CI/CD)
- **Region**: Same as production
- **Redundancy**: Standard_LRS
- **Scale**: Production-like
- **Monitoring**: Full Application Insights
- **Note**: Staging slot exists but is not used in automated deployments (see ADR-0034)

#### Production
- **Purpose**: Live invoice processing
- **Region**: East US (primary)
- **Redundancy**: Standard_GRS (geo-redundant)
- **Scale**: Auto-scale 0-200 instances
- **Monitoring**: Full Application Insights with alerts

### CI/CD Pipeline

```
GitHub → Actions → Tests → Build → Upload to Blob → Generate SAS → Deploy to Production → Health Check → Tag Release
```

**Pipeline Stages**:
1. **Test**: Run pytest (472 tests, 93% coverage)
2. **Lint**: Black, Flake8, mypy, bandit
3. **Build**: Package Python functions into ZIP
4. **Infrastructure**: Deploy Bicep templates (incremental mode)
5. **Upload**: Upload package to blob storage with git SHA filename
6. **Generate SAS**: Create 1-year SAS URL for package access
7. **Deploy**: Update `WEBSITE_RUN_FROM_PACKAGE` app setting with SAS URL
8. **Restart**: Restart Function App to load new package
9. **Health Check**: Verify health endpoint returns 200 and 9 functions loaded
10. **Tag**: Create git tag for release tracking

**Deployment Pattern**: Direct Blob URL Deployment
- No staging slot or slot swap (removed due to reliability issues on Linux Consumption)
- Each deployment creates version-tagged package (`function-app-{sha}.zip`)
- Rollback by updating `WEBSITE_RUN_FROM_PACKAGE` to previous package URL
- See [ADR-0034](adr/0034-blob-url-deployment.md) for rationale

### Configuration Management

**Infrastructure as Code**:
- Bicep templates for all Azure resources
- Parameter files per environment
- Version controlled in Git

**App Settings**:
- Stored as Function App configuration
- Key Vault references for secrets
- Environment-specific values

**Secret Management**:
- All secrets in Key Vault
- Managed Identity for access
- Automatic rotation where supported

**Rollback Procedure**:
```bash
# List available packages
az storage blob list --container-name function-releases --account-name stinvoiceagentprod --query "[].name" -o tsv

# Generate SAS for previous version
az storage blob generate-sas --container-name function-releases --name "function-app-<prev-sha>.zip" ...

# Update app setting and restart
az functionapp config appsettings set --settings "WEBSITE_RUN_FROM_PACKAGE=<sas-url>"
az functionapp restart --name func-invoice-agent-prod
```
- See [docs/DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for detailed rollback steps
- See [docs/operations/ROLLBACK_PROCEDURE.md](operations/ROLLBACK_PROCEDURE.md) for emergency procedures

---

## Current Implementation Status

### Phase 1 (MVP) - DEPLOYED TO PRODUCTION

**Deployment Date**: November 14, 2024

**Infrastructure** ✅:
- Function App (Consumption Plan, Python 3.11)
- Storage Account (Tables, Blobs, Queues)
- Key Vault (secrets configured)
- Application Insights (monitoring active)
- Managed Identity (system-assigned)
- Staging Slot (configured)

**Functions Deployed** ✅ (9 total):
- MailWebhook: Webhook receiver (HTTP trigger) - **ACTIVE**
- MailWebhookProcessor: Email processing (queue trigger) - **ACTIVE**
- SubscriptionManager: Subscription renewal (timer trigger) - **ACTIVE**
- MailIngest: Fallback polling (timer trigger) - **ACTIVE**
- ExtractEnrich: Vendor lookup + PDF extraction (queue trigger) - **ACTIVE**
- PostToAP: Email routing (queue trigger) - **ACTIVE**
- Notify: Teams notifications (queue trigger) - **ACTIVE**
- AddVendor: Vendor management (HTTP trigger) - **ACTIVE**
- Health: Health check endpoint (HTTP trigger) - **ACTIVE**

**CI/CD Pipeline** ✅:
- GitHub Actions workflow configured
- 472 tests passing (93% coverage)
  - 446 unit tests
  - 26 integration tests (all passing)
- Quality gates: Black, Flake8, mypy, bandit
- Direct blob URL deployment to production
- Health check verification (9 functions loaded)
- Automatic release tagging

**Integration** ✅:
- Graph API (MSAL authentication)
- Table Storage (Managed Identity)
- Blob Storage (Managed Identity)
- Queue Storage (Managed Identity)
- Teams Webhooks (configured and tested)
- Key Vault (Managed Identity access)

**Monitoring** ✅:
- Application Insights configured
- Custom metrics defined
- Alert rules created
- Dashboard configured

### Activation Status

**Deployment Lessons Learned**:
1. **Slot Swap Unreliable on Linux Consumption**: `WEBSITE_RUN_FROM_PACKAGE=1` breaks after slot swap - use explicit blob URL instead (see ADR-0034)
2. **User Delegation SAS Limited to 7 Days**: For longer expiry, use storage account key SAS
3. **Health Check Critical**: Always verify functions loaded (count=9) and health endpoint returns 200 after deployment
4. **Rollback via Blob URL**: Keep previous packages in blob storage for quick rollback

**Activation Status** ✅:
- **VendorMaster table seeded**: Production ready with vendor data loaded
  - Script executed: `infrastructure/scripts/seed_vendors.py`
  - Seed data applied: `infrastructure/data/vendors.csv`
  - Status: Operational and ready for invoice processing

**Activation Checklist**:
- [x] Execute seed script: `python infrastructure/scripts/seed_vendors.py --env prod`
- [ ] Send test invoice email to shared mailbox
- [ ] Monitor end-to-end processing in Application Insights
- [ ] Verify Teams notification received
- [ ] Measure actual end-to-end performance
- [ ] Validate vendor match rate
- [ ] Confirm AP email delivery

**Recommended Next Actions**:
1. Send 3-5 test invoices (known vendors) to verify end-to-end flow
2. Monitor Application Insights for 24 hours to establish baseline metrics
3. Measure performance metrics vs targets (<60s processing, >80% auto-routing)
4. Validate vendor match rate and identify any unknown vendors
5. Adjust alert thresholds based on real production data
6. Document actual performance characteristics
7. Monitor and optimize based on production metrics

---

## Future Enhancements

### Phase 2: Intelligence - COMPLETE (Nov 2024)

> **Status**: Implemented via [ADR-0022](adr/0022-pdf-vendor-extraction.md)
> **Deployment Date**: November 24, 2024

**PDF Vendor Extraction** ✅:
- pdfplumber for PDF text extraction
- Azure OpenAI (gpt-4o-mini) for intelligent vendor identification
- 95%+ accuracy, ~500ms latency, ~$0.001/invoice
- Graceful fallback to email domain if extraction fails

**Duplicate Detection** ✅:
- Message-level dedup by `original_message_id`
- Invoice-level dedup by hash (vendor + sender + date)
- 90-day lookback window in InvoiceTransactions table
- See [ADR-0028](adr/0028-message-id-deduplication.md)

**Remaining Phase 2 Items** (Future):
- AI Vendor Matching: Fuzzy matching for vendor name variations
- Amount Extraction: Extract invoice amount from PDF for validation

### Phase 3: Integration (Planned - Month 3+)

**Direct NetSuite API**:
- Post directly to NetSuite instead of email
- Automated approval workflow
- End-to-end automation

**Multi-Mailbox Support**:
- Process from multiple shared mailboxes
- Department-specific routing
- Custom enrichment rules per mailbox

**Analytics Dashboard**:
- Power BI integration
- Processing trends
- Vendor analytics
- Cost allocation reporting

**Mobile Notifications**:
- Push notifications for errors
- Approval requests on mobile
- Real-time status updates

### Architectural Considerations for Future

**Event Grid**:
- Real-time event-driven triggers (instead of timer)
- Sub-second latency for email processing

**Cosmos DB**:
- If query complexity increases
- If vendor count exceeds 10,000
- If global distribution needed

**Azure Cognitive Services**:
- OCR for handwritten invoices
- Language detection for international invoices
- Sentiment analysis for email content

**Logic Apps**:
- Complex workflow orchestration
- Multi-step approval processes
- Integration with other systems

**API Management**:
- External API exposure for AddVendor
- Rate limiting and throttling
- Developer portal for partners

---

## Data Retention & Compliance

### Retention Policies

| Data Type | Retention Period | Storage | Rationale |
|-----------|------------------|---------|-----------|
| Invoice Attachments | 7 years | Blob Storage | Compliance requirement |
| Transaction Logs | 7 years | Table Storage | Audit trail requirement |
| Application Logs | 90 days | Application Insights | Operational monitoring |
| Queue Messages | 7 days | Queue Storage | Processing buffer |

### Compliance Requirements

**Audit Trail**:
- All transactions logged to InvoiceTransactions table
- Immutable records (no updates, only inserts)
- Correlation IDs for full traceability

**Data Access**:
- Role-based access control (RBAC)
- Audit logs for all data access
- Principle of least privilege

**Data Privacy**:
- No credit card or sensitive financial data
- Email addresses stored for operational purposes
- No PII in application logs

---

**Version:** 3.2 (Integration Tests Complete)
**Last Updated:** 2025-12-10
**Maintained By:** Engineering Team
**Related Documents**:
- [Development Workflow](../CLAUDE.md)
- [Local Development](LOCAL_DEVELOPMENT.md)
- [Deployment Guide](DEPLOYMENT_GUIDE.md)
- [Decision Log](DECISIONS.md)
