# Invoice Agent - AI Development Instructions

## Project Context
You are working on an automated invoice processing system using Azure Functions. This system reads emails from a shared mailbox, extracts vendor information, enriches it with GL codes from a lookup table, sends the processed invoice to AP, and provides simple notifications via Teams webhooks.

**Current Sprint:** MVP Implementation
**Approval Workflow:** Handled downstream in NetSuite (not our concern)

## Architecture Principles
1. **Serverless-first** - Azure Functions on Consumption tier for cost efficiency
2. **Queue-based decoupling** - Resilient message flow between functions
3. **Table Storage** - Simple, fast, cheap for vendor lookups
4. **Managed Identity** - All authentication, no hardcoded secrets
5. **Simple Teams webhooks** - Notifications only, no complex interactions
6. **Let NetSuite handle complexity** - We automate, they approve

## Core Flow
```
Email → Extract Vendor → Apply GL Codes → Send to AP → Notify Teams
```

## Scope Boundaries

### IN SCOPE ✅
- Email polling from shared mailbox every 5 minutes
- Attachment storage to Azure Blob
- Vendor extraction from email sender/subject
- Vendor lookup and enrichment (4 fields)
- AP email routing with standardized format
- Simple Teams webhook notifications
- Error handling and logging
- Transaction audit trail

### OUT OF SCOPE ❌
- Approval workflows (NetSuite handles)
- Payment processing (NetSuite handles)
- Complex vendor management UI (NetSuite handles)
- Interactive Teams cards with buttons
- PDF parsing (Phase 2)
- AI/LLM extraction (Phase 2)
- Multi-mailbox support (Phase 3)

## Development Standards

### Code Quality
- **Max 25 lines per function** - Forces atomic, testable functions
- **Full type hints** - mypy in strict mode
- **Explicit error handling** - try/except on all external calls
- **No silent failures** - Log and notify on errors
- **ULID for IDs** - Sortable, unique transaction identifiers

### Testing
- **60% coverage minimum** for MVP
- **Unit tests** for business logic
- **Integration tests** for queue flow
- **Fixtures** for queue messages

### Logging
- **Structured logging** with correlation IDs
- **Log levels:** ERROR for failures, INFO for success, DEBUG for details
- **Application Insights** integration
- **Correlation ID** (ULID) in all log entries

## Key Integrations

### Microsoft Graph API
- **Purpose:** Read emails, send to AP
- **Auth:** Service principal with certificate
- **Permissions:** Mail.Read, Mail.Send
- **Mailbox:** Shared inbox for invoice processing

### Azure Table Storage
- **VendorMaster:** Vendor lookup table
- **InvoiceTransactions:** Audit log
- **Pattern:** PartitionKey + RowKey queries

### Teams Webhooks
- **Purpose:** Simple notifications only
- **Format:** Plain message cards
- **No interactions:** Just informational

## Function Specifications

### MailIngest
- Timer trigger (0 */5 * * * *)
- Read unread emails from shared mailbox
- Save attachments to Blob Storage
- Queue message to raw-mail
- Mark email as read

### ExtractEnrich
- Queue trigger (raw-mail)
- Extract vendor from sender/subject
- Lookup in VendorMaster table
- Apply 4 enrichment fields
- Queue to to-post

### PostToAP
- Queue trigger (to-post)
- Compose standardized email
- Send via Graph API
- Log to InvoiceTransactions
- Queue to notify

### Notify
- Queue trigger (notify)
- Format simple Teams message
- Post to webhook
- No error retry (not critical)

## Error Handling Strategy

### Transient Errors
- Retry 3x with exponential backoff
- Log warning on retry
- Move to poison queue after max retries

### Business Errors
- Unknown vendor → Flag and notify
- Missing data → Use defaults
- Invalid format → Log and skip

### Critical Errors
- Graph API down → Alert ops team
- Storage unavailable → Circuit breaker
- Teams webhook fail → Log only (non-critical)

## MVP Success Criteria
- Process invoice in <60 seconds
- 80% auto-routing (known vendors)
- <10% unknown vendor rate
- <1% error rate
- Simple notifications working

## Development Workflow
1. Use `/init` to set up environment
2. Use `/build` to generate functions
3. Use `/test` to validate
4. Use `/deploy` for production
5. Use `/status` to monitor health

## Communication Style
- **Be concise** - No fluff, get to the point
- **Show status** - ✅ Done, 🔄 In Progress, ❌ Failed
- **Explain errors** - What failed and why
- **Suggest fixes** - Don't just report problems

## Current Focus
Building MVP with simplest possible implementation that works reliably. Complexity can be added later if needed. NetSuite handles all the complex approval logic - we just need to get the invoice there with the right metadata.