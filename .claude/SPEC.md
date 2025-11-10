# Invoice Agent - System Specification

## Executive Summary

**Problem:** Manual invoice processing from email takes 5+ minutes each, with frequent errors and no audit trail.

**Solution:** Automated Azure serverless system that extracts vendor info, applies GL codes, routes to AP, and sends Teams notifications. Approval workflow remains in NetSuite.

---

## Functional Requirements

### FR1: Email Monitoring
- Monitor shared mailbox for incoming invoices
- Poll every 5 minutes via timer trigger
- Process emails with PDF/image attachments
- Mark processed emails as read
- Store attachments in Blob Storage

### FR2: Vendor Extraction & Lookup
- Extract vendor name from email sender domain
- Fallback to subject line parsing
- Lookup vendor in VendorMaster table
- Flag unknown vendors for manual review
- Success target: 80% match rate

### FR3: Data Enrichment
Apply from VendorMaster lookup:
- **ExpenseDept** - Department code for allocation
- **AllocationScheduleNumber** - Billing frequency
- **GLCode** - General ledger code
- **BillingParty** - Entity responsible for payment

### FR4: AP Email Routing
- Send standardized email to AP mailbox
- Subject: `Invoice: {Vendor} - GL {GLCode}`
- Body: Include all enriched metadata
- Attach original invoice PDF
- Include transaction ID for tracking

### FR5: Simple Notifications
Teams webhook notifications only:
- **Success:** "✅ Processed: {vendor} - ${amount}"
- **Unknown:** "⚠️ Unknown vendor: {sender}"
- **Error:** "❌ Failed: {error_message}"
- **Daily Summary:** X processed, Y unknown, Z errors

### FR6: Audit Logging
- Log all transactions to InvoiceTransactions table
- Include: timestamp, vendor, GL codes, status, errors
- Retention: 7 years for compliance
- Query by: date range, vendor, status

---

## Non-Functional Requirements

### Performance
- End-to-end processing: ≤60 seconds
- Support 50 concurrent invoices
- Queue visibility timeout: 5 minutes

### Reliability
- 99.9% uptime (43 minutes downtime/month)
- Retry transient failures 3x
- Dead letter queue after max retries
- Graceful degradation on Teams webhook failure

### Security
- Managed Identity for all Azure resources
- Key Vault for sensitive configuration
- No credentials in code or config files
- Input validation on all external data

### Scalability
- Auto-scale with queue depth
- Consumption tier serverless
- No hardcoded limits

---

## System Architecture

### Component Flow
```
[Shared Mailbox]
    ↓ (Timer: 5 min)
[MailIngest Function] → [Blob: invoices/raw/]
    ↓ (Queue: raw-mail)
[ExtractEnrich Function] ←→ [Table: VendorMaster]
    ↓ (Queue: to-post)
[PostToAP Function] → [AP Mailbox] + [Table: InvoiceTransactions]
    ↓ (Queue: notify)
[Notify Function] → [Teams Webhook]
```

### Azure Resources
- **Function App:** Python 3.11, Consumption Plan, Linux
- **Storage Account:** Tables + Blobs + Queues
- **Key Vault:** 4 secrets (Graph creds, AP email, Teams URL)
- **Application Insights:** Logging and metrics
- **Managed Identity:** System-assigned

---

## Data Models

### VendorMaster Table
```json
{
  "PartitionKey": "Vendor",
  "RowKey": "adobe_com",  // vendor_name_lower
  "VendorName": "Adobe Inc",
  "ExpenseDept": "IT",
  "AllocationScheduleNumber": "MONTHLY",
  "GLCode": "6100",
  "BillingParty": "Company HQ",
  "Active": true,
  "UpdatedAt": "2024-11-09T12:00:00Z"
}
```

### InvoiceTransactions Table
```json
{
  "PartitionKey": "202411",  // YYYYMM
  "RowKey": "01JCK3Q7H8ZVXN3BARC9GWAEZM",  // ULID
  "VendorName": "Adobe Inc",
  "SenderEmail": "billing@adobe.com",
  "ExpenseDept": "IT",
  "GLCode": "6100",
  "Status": "processed",  // processed|unknown|error
  "BlobUrl": "https://storage.blob.core.windows.net/invoices/raw/invoice123.pdf",
  "ProcessedAt": "2024-11-09T14:30:00Z",
  "ErrorMessage": null
}
```

### Queue Messages

**raw-mail**
```json
{
  "id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
  "sender": "billing@adobe.com",
  "subject": "Invoice #12345 - November 2024",
  "blob_url": "https://storage/invoices/raw/invoice123.pdf",
  "received_at": "2024-11-09T14:00:00Z"
}
```

**to-post**
```json
{
  "id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
  "vendor_name": "Adobe Inc",
  "expense_dept": "IT",
  "gl_code": "6100",
  "allocation_schedule": "MONTHLY",
  "billing_party": "Company HQ",
  "blob_url": "https://storage/invoices/raw/invoice123.pdf",
  "status": "enriched"
}
```

**notify**
```json
{
  "type": "success",  // success|unknown|error
  "message": "Processed: Adobe Inc - GL 6100",
  "details": {
    "vendor": "Adobe Inc",
    "gl_code": "6100",
    "transaction_id": "01JCK3Q7H8ZVXN3BARC9GWAEZM"
  }
}
```

---

## Teams Notifications (Simple Webhooks)

### Success Message
```json
{
  "@type": "MessageCard",
  "themeColor": "00FF00",
  "text": "✅ Invoice Processed",
  "sections": [{
    "facts": [
      {"name": "Vendor", "value": "Adobe Inc"},
      {"name": "GL Code", "value": "6100"},
      {"name": "Department", "value": "IT"},
      {"name": "Status", "value": "Sent to AP"}
    ]
  }]
}
```

### Unknown Vendor Message
```json
{
  "@type": "MessageCard",
  "themeColor": "FFA500",
  "text": "⚠️ Unknown Vendor Detected",
  "sections": [{
    "facts": [
      {"name": "Sender", "value": "newvendor@example.com"},
      {"name": "Subject", "value": "Invoice #12345"},
      {"name": "Action Required", "value": "Add vendor to master list"}
    ]
  }]
}
```

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Auto-routing rate | ≥80% | processed/(processed+unknown) |
| Processing time | ≤60s | End-to-end latency |
| Unknown vendor rate | ≤10% | unknown/total |
| Error rate | ≤1% | errors/total |
| Daily volume | 20-50 | Invoices processed |

---

## Implementation Phases

### Phase 1: MVP (Weeks 1-2) - CURRENT
- Core email processing pipeline
- Vendor lookup and enrichment
- AP routing
- Simple Teams notifications
- Basic error handling

### Phase 2: Intelligence (Month 2)
- PDF text extraction
- Azure OpenAI for vendor matching
- Duplicate detection
- Amount extraction

### Phase 3: Integration (Month 3+)
- Direct NetSuite API
- Multi-mailbox support
- Analytics dashboard
- Mobile notifications

---

## Constraints & Assumptions

### Constraints
- Must use Azure native services
- Must integrate with Teams (no custom UI)
- 7-year retention requirement
- Cannot modify NetSuite workflow

### Assumptions
- Vendors mostly identifiable from email
- Finance maintains VendorMaster list
- AP monitors their mailbox
- Teams webhooks remain available
- Invoice format relatively consistent

---

## Risk Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Graph API throttling | High | Low | Implement backoff, cache tokens |
| Unknown vendor rate >10% | Medium | Medium | Weekly vendor list updates |
| Teams webhook down | Low | Low | Continue processing, log only |
| Storage account failure | High | Very Low | Geo-redundant storage |
| Malformed emails | Medium | Medium | Defensive parsing, skip bad emails |

---

## Dependencies

### External
- Microsoft 365 licenses with Graph API access
- Azure subscription (already have)
- Teams with webhook capability
- NetSuite for downstream processing

### Internal
- Finance team to maintain vendor list
- IT to provision Azure resources
- AP to monitor enriched emails
- Weekly vendor list updates

---

## Definition of Done

### MVP Checklist
- [ ] Emails being read from shared mailbox
- [ ] Attachments saved to Blob Storage
- [ ] Vendor extraction working (80% success)
- [ ] VendorMaster lookups returning GL codes
- [ ] AP receiving enriched emails
- [ ] Teams notifications posting
- [ ] Transaction log writing
- [ ] Error handling implemented
- [ ] 60% test coverage
- [ ] Deployed to production
- [ ] Monitoring configured
- [ ] Runbook documented

---

**Version:** 1.0
**Last Updated:** 2024-11-09
**Status:** Building MVP