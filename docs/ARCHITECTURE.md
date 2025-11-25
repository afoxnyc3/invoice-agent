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
- **Test Coverage**: >60% (currently at 96%)

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
│        MailWebhook Function (NEW)       │  │
│  - HTTP trigger receives notification  │  │
│  - Validates client state (security)   │  │
│  - Saves attachments to Blob Storage   │  │
│  - Queues for processing                │  │
└──────────────┬──────────────────────────┘  │
               │ Queue: webhook-notifications│
               ↓                             │
┌─────────────────────────────────────────┐  │
│     ExtractEnrich Function              │  │
│  - Extract vendor from PDF (AI)         │  │
│  - Fallback to email domain if needed   │  │
│  - Lookup in VendorMaster table         │  │
│  - Apply GL codes and metadata          │  │
└──────────────┬──────────────────────────┘  │
               │ Queue: to-post              │
               ↓                             │
┌─────────────────────────────────────────┐  │
│        PostToAP Function                │  │
│  - Compose standardized email           │  │
│  - Send to AP mailbox via Graph         │  │
│  - Log to InvoiceTransactions           │  │
└──────────────┬──────────────────────────┘  │
               │ Queue: notify               │
               ↓                             │
┌─────────────────────────────────────────┐  │
│         Notify Function                 │  │
│  - Format Teams message                 │  │
│  - Post to webhook                      │  │
│  - Non-critical (no retry)              │  │
└─────────────────────────────────────────┘  │
                                             │
┌─────────────────────────────────────────┐  │
│  SubscriptionManager Function (NEW)    │◄─┘
│  - Timer: Every 6 days                  │
│  - Renews Graph API subscription        │
│  - Stores state in GraphSubscriptions   │
│  - Ensures webhooks stay active         │
└─────────────────────────────────────────┘

┌────────────────────────── FALLBACK ──────────────────────────────┐
│  MailIngest Function (MODIFIED - Hourly Safety Net)              │
│  - Timer: Every hour (was 5 minutes)                             │
│  - Polls for any missed emails                                   │
│  - Queues to raw-mail for processing                             │
└──────────────────────────────────────────────────────────────────┘
```

**Key Architecture Changes (Nov 2024):**
- **Primary Path**: Event-driven webhooks (<10 sec latency, 95% of emails)
- **Fallback Path**: Hourly polling (safety net, 5% of emails)
- **Cost Reduction**: 70% savings ($0.60/month vs $2.00/month)
- **Function Count**: 7 (was 5) - Added MailWebhook + SubscriptionManager
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

---

## Azure Resources & Infrastructure

### Compute Layer
**Azure Functions** (Consumption Plan Y1)
- **Runtime**: Python 3.11 on Linux
- **Scaling**: 0-200 instances auto-scale
- **Cold Start**: ~2-4 seconds
- **Timeout**: 5 minutes default (configurable)
- **Region**: Single region for dev, geo-redundant for prod

### Storage Layer
**Storage Account** (Standard_LRS for dev, Standard_GRS for prod)

**Tables:**
- `VendorMaster`: Vendor lookup data (~100-1000 vendors)
- `InvoiceTransactions`: Audit log (7-year retention)
- `GraphSubscriptions`: **NEW** - Webhook subscription state management

**Blobs:**
- `invoices/raw/`: Original email attachments
- `invoices/processed/`: Archived invoices (future)

**Queues:**
- `webhook-notifications`: **NEW** - Real-time email notifications from MailWebhook (primary path)
- `raw-mail`: Unprocessed emails from MailIngest (fallback path)
- `to-post`: Enriched invoices for AP routing
- `notify`: Notifications for Teams
- `*-poison`: Dead letter queues (5 retry attempts)

### Security Layer
**Managed Identity** (System-assigned)
- Graph API access (Mail.Read, Mail.Send)
- Storage operations (Tables, Blobs, Queues)
- Key Vault access (secrets retrieval)

**Key Vault** (Standard tier)
- `graph-client-secret`: Service principal secret
- `graph-client-state`: **NEW** - Webhook validation secret (security)
- `mail-webhook-url`: **NEW** - MailWebhook endpoint URL with function key
- `ap-email-address`: AP mailbox address
- `teams-webhook-url`: Teams channel webhook
- `invoice-mailbox`: Shared mailbox address

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
| ExpenseDept | string | Department code | "IT" |
| AllocationScheduleNumber | string | Billing frequency | "MONTHLY" |
| GLCode | string | General ledger code | "6100" |
| BillingParty | string | Responsible entity | "Company HQ" |
| Active | bool | Soft delete flag | true |
| UpdatedAt | datetime | Last modified | "2024-11-09T12:00:00Z" |

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
| BillingParty | string | From lookup | "Company HQ" |
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

#### Success Message (Green)
```json
{
  "@type": "MessageCard",
  "@context": "http://schema.org/extensions",
  "themeColor": "00FF00",
  "summary": "Invoice Processed",
  "sections": [{
    "activityTitle": "✅ Invoice Processed",
    "activitySubtitle": "2024-11-09 14:30:00",
    "facts": [
      {"name": "Vendor", "value": "Adobe Inc"},
      {"name": "GL Code", "value": "6100"},
      {"name": "Department", "value": "IT"},
      {"name": "Transaction ID", "value": "01JCK3Q7H8ZVXN3BARC9GWAEZM"},
      {"name": "Status", "value": "Sent to AP"}
    ]
  }]
}
```

#### Unknown Vendor Message (Orange)
```json
{
  "@type": "MessageCard",
  "@context": "http://schema.org/extensions",
  "themeColor": "FFA500",
  "summary": "Unknown Vendor",
  "sections": [{
    "activityTitle": "⚠️ Unknown Vendor Detected",
    "activitySubtitle": "Manual review required",
    "facts": [
      {"name": "Sender", "value": "newvendor@example.com"},
      {"name": "Subject", "value": "Invoice #12345"},
      {"name": "Transaction ID", "value": "01JCK3Q7H8ZVXN3BARC9GWAEZM"},
      {"name": "Action Required", "value": "Add vendor to master list"}
    ]
  }]
}
```

#### Error Message (Red)
```json
{
  "@type": "MessageCard",
  "@context": "http://schema.org/extensions",
  "themeColor": "FF0000",
  "summary": "Processing Error",
  "sections": [{
    "activityTitle": "❌ Processing Failed",
    "activitySubtitle": "Immediate attention required",
    "facts": [
      {"name": "Error", "value": "Graph API authentication failed"},
      {"name": "Transaction ID", "value": "01JCK3Q7H8ZVXN3BARC9GWAEZM"},
      {"name": "Timestamp", "value": "2024-11-09 14:30:00"},
      {"name": "Action Required", "value": "Check Application Insights logs"}
    ]
  }]
}
```

---

## Data Flow & Processing

### 1. Email Ingestion (MailIngest)

```
Timer(5min) → Graph API → Filter Unread → Download Attachments → Queue Message → Mark Read
```

**Processing Steps**:
1. Timer trigger fires every 5 minutes
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

**Enrichment Fields Applied**:
- **ExpenseDept**: Department code for allocation (e.g., "IT", "Marketing")
- **AllocationScheduleNumber**: Billing frequency (e.g., "MONTHLY", "ANNUAL")
- **GLCode**: General ledger code (e.g., "6100")
- **BillingParty**: Entity responsible for payment (e.g., "Company HQ")

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

---

## Error Handling & Retry Logic

### Transient Failures

**Retry Strategy**:
- 3 retries with exponential backoff (2s, 4s, 8s)
- Graph API throttling: Honor `Retry-After` headers
- Queue visibility timeout: 5 minutes
- Poison queue after 5 attempts

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
- Dead letter handling after 5 retries

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

### Teams Webhooks

**Purpose**: Post notifications to Teams channel

**Format**: Simple Message Cards (not Adaptive Cards)

**Authentication**: Webhook URL is the secret (no additional auth)

**Message Types**:
- Success (green): Invoice processed
- Warning (orange): Unknown vendor
- Error (red): Processing failure

**Non-Critical Path**:
- Webhook failures don't block processing
- No retry on failure
- Logged for monitoring

**Error Handling**:
- Log failures but don't retry
- Continue processing even if webhook down
- Alert on sustained webhook failures

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

#### Staging
- **Purpose**: Pre-production testing
- **Region**: Same as production
- **Redundancy**: Standard_LRS
- **Scale**: Production-like
- **Monitoring**: Full Application Insights
- **Deployment Slot**: Staging slot in production Function App

#### Production
- **Purpose**: Live invoice processing
- **Region**: East US (primary)
- **Redundancy**: Standard_GRS (geo-redundant)
- **Scale**: Auto-scale 0-200 instances
- **Monitoring**: Full Application Insights with alerts

### CI/CD Pipeline

```
GitHub → Actions → Tests → Build → Deploy Staging → Smoke Tests → Swap Slots → Production
```

**Pipeline Stages**:
1. **Test**: Run pytest (98 tests, 96% coverage)
2. **Lint**: Black, Flake8, mypy, bandit
3. **Build**: Package Python functions
4. **Deploy Staging**: Deploy to staging slot
5. **Smoke Tests**: Verify basic functionality
6. **Approval**: Manual approval gate
7. **Swap**: Blue-green deployment via slot swap
8. **Production**: Active in production

**Deployment Pattern**: Blue-Green via Staging Slots
- Zero-downtime deployments
- Instant rollback (swap back)
- Production traffic validation

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
- Swap slots back to previous version
- Restore from backup if data corruption
- See [docs/operations/ROLLBACK_PROCEDURE.md](operations/ROLLBACK_PROCEDURE.md)

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

**Functions Deployed** ✅:
- MailIngest: Email polling (timer trigger) - **ACTIVE**
- ExtractEnrich: Vendor lookup (queue trigger) - **ACTIVE**
- PostToAP: Email routing (queue trigger) - **ACTIVE**
- Notify: Teams notifications (queue trigger) - **ACTIVE**
- AddVendor: Vendor management (HTTP trigger) - **ACTIVE**

**CI/CD Pipeline** ✅:
- GitHub Actions workflow configured
- 98 tests passing (96% coverage)
- Quality gates: Black, Flake8, mypy, bandit
- Staging deployment automated
- Production approval gate
- Slot swap pattern implemented

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
1. **Staging Slot Configuration**: Must manually sync app settings from production to staging after Bicep deployment
2. **Artifact Path Handling**: GitHub Actions download-artifact@v4 creates directory automatically
3. **Function App Restart**: App settings changes require Function App restart to take effect
4. **CI/CD Workflow**: Test + Build must pass BEFORE staging deployment

**Activation Status** ✅:
- **VendorMaster table seeded**: Production ready with vendor data loaded
  - Script executed: `infrastructure/scripts/seed_vendors.py`
  - Seed data applied: `data/vendors.csv`
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
7. Begin Phase 2 planning (PDF extraction, AI matching)

---

## Future Enhancements

### Phase 2: Intelligence (Planned - Month 2)

**PDF Text Extraction**:
- Azure AI Document Intelligence (Form Recognizer)
- Extract vendor, amount, invoice number from PDF
- Reduce dependency on email sender accuracy

**AI Vendor Matching**:
- Azure OpenAI for fuzzy matching
- Handle vendor name variations
- Learn from user corrections

**Duplicate Detection**:
- Check InvoiceTransactions for duplicates
- Compare invoice number, vendor, amount
- Alert on potential duplicates

**Amount Extraction**:
- Extract invoice amount from PDF
- Validate against PO or budget
- Flag anomalies

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

**Version:** 2.1 (Production Ready - Vendor Data Seeded)
**Last Updated:** 2025-11-24
**Maintained By:** Engineering Team
**Related Documents**:
- [Development Workflow](../CLAUDE.md)
- [Local Development](LOCAL_DEVELOPMENT.md)
- [Deployment Guide](DEPLOYMENT_GUIDE.md)
- [Decision Log](DECISIONS.md)
