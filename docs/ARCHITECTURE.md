# Invoice Agent - System Architecture

## Overview

The Invoice Agent is an event-driven, serverless system built on Azure Functions that automates invoice processing from email ingestion through AP routing and notification. The system processes invoices in under 60 seconds with 80%+ automation rate.

## System Components

### Core Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Shared Mailbox                            │
│                    (invoices@example.com)                       │
└────────────────────────────┬────────────────────────────────────┘
                             │ Timer (5 min)
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                      MailIngest Function                         │
│  - Poll unread emails via Graph API                             │
│  - Save attachments to Blob Storage                             │
│  - Queue message with metadata                                  │
└────────────────────────────┬────────────────────────────────────┘
                             │ Queue: raw-mail
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                    ExtractEnrich Function                        │
│  - Extract vendor from email                                    │
│  - Lookup in VendorMaster table                                │
│  - Apply GL codes and metadata                                 │
└────────────────────────────┬────────────────────────────────────┘
                             │ Queue: to-post
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                      PostToAP Function                           │
│  - Compose standardized email                                   │
│  - Send to AP mailbox via Graph                                │
│  - Log to InvoiceTransactions                                  │
└────────────────────────────┬────────────────────────────────────┘
                             │ Queue: notify
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                       Notify Function                            │
│  - Format Teams message                                         │
│  - Post to webhook                                              │
│  - Non-critical (no retry)                                      │
└─────────────────────────────────────────────────────────────────┘
```

## Azure Resources

### Compute Layer
- **Azure Functions** (Consumption Plan Y1)
  - Runtime: Python 3.11 on Linux
  - Scaling: 0-200 instances auto-scale
  - Cold start: ~2-4 seconds
  - Timeout: 5 minutes default

### Storage Layer
- **Storage Account** (Standard_LRS for dev, Standard_GRS for prod)
  - **Tables:**
    - VendorMaster: Vendor lookup data
    - InvoiceTransactions: Audit log
  - **Blobs:**
    - invoices/raw/: Original attachments
    - invoices/processed/: Archived invoices
  - **Queues:**
    - raw-mail: Unprocessed emails
    - to-post: Enriched invoices
    - notify: Notifications

### Security Layer
- **Managed Identity** (System-assigned)
  - Graph API access
  - Storage operations
  - Key Vault access
- **Key Vault** (Standard tier)
  - graph-client-secret
  - ap-email-address
  - teams-webhook-url

### Monitoring Layer
- **Application Insights**
  - Custom metrics
  - Distributed tracing
  - Log aggregation
  - Alert rules

## Data Flow

### 1. Email Ingestion (MailIngest)
```python
Timer(5min) → Graph API → Filter Unread → Download Attachments → Queue Message
```
- Polls every 5 minutes
- Processes up to 50 emails per execution
- Marks emails as read after queuing

### 2. Vendor Enrichment (ExtractEnrich)
```python
Queue Message → Extract Vendor → Table Lookup → Apply Metadata → Queue Enriched
```
- Vendor extraction hierarchy:
  1. Email domain mapping
  2. Subject line parsing
  3. Default to "UNKNOWN"
- Enrichment fields:
  - ExpenseDept
  - AllocationScheduleNumber
  - GLCode
  - BillingParty

### 3. AP Routing (PostToAP)
```python
Enriched Message → Compose Email → Send via Graph → Log Transaction → Queue Notify
```
- Email format:
  - Subject: "Invoice: {Vendor} - GL {GLCode}"
  - Body: HTML with metadata table
  - Attachment: Original invoice

### 4. Notification (Notify)
```python
Notify Message → Format Card → Post to Teams → Log Response
```
- Message types:
  - ✅ Success: Processed invoices
  - ⚠️ Warning: Unknown vendors
  - ❌ Error: Processing failures

## Data Models

### VendorMaster Table Schema
| Field | Type | Description |
|-------|------|-------------|
| PartitionKey | string | Always "Vendor" |
| RowKey | string | vendor_name_lower |
| VendorName | string | Display name |
| ExpenseDept | string | Department code |
| AllocationScheduleNumber | string | Billing frequency |
| GLCode | string | General ledger code |
| BillingParty | string | Responsible entity |
| Active | bool | Soft delete flag |
| UpdatedAt | datetime | Last modified |

### InvoiceTransactions Table Schema
| Field | Type | Description |
|-------|------|-------------|
| PartitionKey | string | YYYYMM format |
| RowKey | string | ULID (unique, sortable) |
| TransactionId | string | Same as RowKey |
| VendorName | string | Identified vendor |
| SenderEmail | string | Original sender |
| ExpenseDept | string | From lookup |
| GLCode | string | From lookup |
| Status | string | processed/unknown/error |
| BlobUrl | string | Attachment location |
| ProcessedAt | datetime | Completion time |
| ErrorMessage | string | If failed |

## Queue Message Schemas

### raw-mail Queue
```json
{
  "id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
  "sender": "billing@adobe.com",
  "subject": "Invoice #12345",
  "blob_url": "https://storage/invoices/raw/file.pdf",
  "received_at": "2024-11-09T14:00:00Z"
}
```

### to-post Queue
```json
{
  "id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
  "vendor_name": "Adobe Inc",
  "expense_dept": "IT",
  "gl_code": "6100",
  "allocation_schedule": "MONTHLY",
  "billing_party": "Company HQ",
  "blob_url": "https://storage/invoices/raw/file.pdf",
  "status": "enriched"
}
```

### notify Queue
```json
{
  "type": "success",
  "message": "Processed: Adobe Inc - GL 6100",
  "transaction_id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
  "details": {
    "vendor": "Adobe Inc",
    "gl_code": "6100"
  }
}
```

## Security Architecture

### Authentication & Authorization
- **Managed Identity**: All Azure resource access
- **Graph API**: App-only authentication with client credentials
- **Key Vault**: Secret management with MI access
- **RBAC**: Least privilege for all resources

### Network Security
- **Private Endpoints**: Production storage (future)
- **IP Restrictions**: Function App allowlist (future)
- **TLS**: All communications encrypted
- **CORS**: Disabled on all functions

### Data Security
- **Encryption at Rest**: Storage service encryption
- **Encryption in Transit**: TLS 1.2 minimum
- **Audit Logging**: All operations logged
- **PII Handling**: No sensitive data in logs

## Scalability & Performance

### Design Targets
- **Throughput**: 50 concurrent invoices
- **Latency**: <60 seconds end-to-end
- **Availability**: 99.9% uptime
- **Storage**: 7-year retention

### Scaling Strategy
- **Functions**: Auto-scale 0-200 instances
- **Queues**: Parallel processing with visibility timeout
- **Storage**: Partitioned tables by month
- **Monitoring**: Adaptive sampling for high volume

### Performance Optimizations
- Connection pooling for Graph API
- Table Storage batch operations
- Queue message batching
- Lazy loading of dependencies

## Failure Handling

### Retry Logic
- **Transient Failures**: 3 retries with exponential backoff
- **Graph API Throttling**: Honor retry-after headers
- **Queue Poison**: After 5 attempts → dead letter
- **Circuit Breaker**: Fail fast after repeated errors

### Error Recovery
- **Unknown Vendors**: Flag for manual review
- **Malformed Emails**: Skip and log
- **Missing Attachments**: Process without attachment
- **Teams Webhook Down**: Continue processing (non-critical)

## Monitoring & Observability

### Metrics
- Invoice processing rate
- Vendor match rate
- Average processing time
- Queue depths
- Error rates by function

### Logging
- Structured JSON logs
- Correlation IDs (ULID)
- Log levels: ERROR, WARNING, INFO, DEBUG
- Retention: 90 days

### Alerts
- Function failures
- Queue backup (>50 messages)
- High error rate (>5%)
- SLO breaches

## Deployment Architecture

### Environments
- **Development**: Single region, minimal redundancy
- **Staging**: Production-like, reduced scale
- **Production**: Geo-redundant storage, full monitoring

### CI/CD Pipeline
```
GitHub → Actions → Tests → Build → Deploy Staging → Smoke Tests → Swap Slots → Production
```

### Configuration Management
- Infrastructure as Code (Bicep)
- App settings from Key Vault
- Environment-specific parameters
- Automated rollback capability

## Future Enhancements (Phase 2+)

### Planned Improvements
1. **PDF Text Extraction**: Extract vendor from PDF content
2. **AI Vendor Matching**: Azure OpenAI for fuzzy matching
3. **Direct NetSuite Integration**: API instead of email
4. **Multi-Mailbox Support**: Process multiple departments
5. **Advanced Analytics**: Power BI dashboards

### Architectural Considerations
- Event Grid for real-time triggers
- Cosmos DB for complex queries
- Azure Cognitive Services for OCR
- Logic Apps for complex workflows
- API Management for external access

## Decision Log

### Why Serverless?
- Variable workload (5-50 invoices/day)
- Cost-effective for sporadic processing
- Auto-scaling without management
- Fast time to market

### Why Table Storage?
- Simple key-value lookups
- 100x cheaper than Cosmos DB
- Sufficient for <1000 vendors
- No complex queries needed

### Why Queue-Based?
- Decouples processing stages
- Built-in retry mechanism
- Natural error boundaries
- Easy to monitor and debug

### Why Email Routing?
- Maintains existing AP workflow
- No NetSuite integration needed for MVP
- Familiar to finance team
- Quick implementation

---

**Version:** 1.0
**Last Updated:** 2024-11-09
**Maintained By:** Engineering Team