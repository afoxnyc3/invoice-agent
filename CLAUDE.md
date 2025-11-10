# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Azure serverless invoice processing system that automates email-to-AP workflow using queue-based Azure Functions, Table Storage for vendor lookups, and Teams webhooks for notifications. NetSuite handles all approval workflows downstream.

## Architecture & Flow

```
Email (5min timer) → MailIngest → Queue → ExtractEnrich → Queue → PostToAP → Queue → Notify → Teams
                         ↓                      ↓                     ↓
                    Blob Storage          VendorMaster         InvoiceTransactions
```

### Key Design Decisions
- **Serverless Functions** over containers: Variable workload (5-50/day) makes pay-per-execution ideal
- **Table Storage** over Cosmos DB: 100x cheaper for simple vendor lookups (<1000 vendors)
- **Queue-based** decoupling: Natural error boundaries and retry mechanisms
- **Email routing** to AP: Maintains existing workflow, no NetSuite integration needed for MVP
- **Simple webhooks** only: No Teams bot framework complexity

## Commands

### Local Development
```bash
# Setup environment
cd src
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure (copy template and add Azure credentials)
cp local.settings.json.template local.settings.json

# Run locally with Azure Functions Core Tools
func start

# Run specific function for testing
func start --functions MailIngest
```

### Testing
```bash
# Unit tests with coverage
pytest tests/unit --cov=functions --cov=shared --cov-fail-under=60 -v

# Integration tests (requires Azurite)
docker run -d -p 10000:10000 -p 10001:10001 -p 10002:10002 azurite
pytest tests/integration -m integration

# Type checking
mypy functions/ shared/ --strict

# Security scan
bandit -r functions/ shared/
```

### Deployment
```bash
# Deploy infrastructure (Bicep)
az deployment group create \
  --resource-group rg-invoice-agent-$ENV \
  --template-file infrastructure/bicep/main.bicep \
  --parameters infrastructure/parameters/$ENV.json

# Deploy functions
func azure functionapp publish func-invoice-agent-$ENV --python

# Seed vendor data
python infrastructure/scripts/seed_vendors.py --env $ENV
```

## Slash Commands

The project includes AI automation slash commands in `.claude/commands/`:
- `/init` - Set up local environment and Azure infrastructure
- `/build` - Generate function code from specifications
- `/test` - Run comprehensive test suite
- `/deploy` - Deploy to Azure with staging slot pattern
- `/status` - Check system health and queue depths

## Critical Constraints

### Function Design
- **25-line function limit** enforced for maintainability
- Each function must handle one specific task
- All external calls require explicit error handling
- Use ULID for transaction IDs (sortable, unique)

### Queue Message Flow
- `raw-mail`: Email metadata + blob URL
- `to-post`: Enriched vendor data with GL codes
- `notify`: Formatted notification messages
- Poison queue after 5 retry attempts

### Data Models (Pydantic)
- `RawMail`: Email ingestion schema
- `EnrichedInvoice`: Vendor-enriched data
- `NotificationMessage`: Teams webhook payload
- All models require strict validation

## Integration Points

### Microsoft Graph API
- Auth: Service principal with certificate/secret
- Permissions: `Mail.Read`, `Mail.Send`
- Throttling: Honor retry-after headers
- Mailbox: Shared inbox configured via `INVOICE_MAILBOX` env var

### Azure Table Storage
- `VendorMaster`: PartitionKey="Vendor", RowKey=vendor_name_lower
- `InvoiceTransactions`: PartitionKey=YYYYMM, RowKey=ULID
- Batch operations for performance
- No complex queries (use PartitionKey+RowKey only)

### Teams Webhooks
- Simple message cards only (no adaptive cards)
- Non-critical path (failures don't block processing)
- Three types: success (green), warning (orange), error (red)

## Error Handling Patterns

### Transient Failures
- Retry 3x with exponential backoff (2s, 4s, 8s)
- Graph API throttling: Use retry-after header
- Queue visibility timeout: 5 minutes

### Business Errors
- Unknown vendor: Flag and continue with "UNKNOWN"
- Missing attachment: Process anyway, log warning
- Malformed email: Skip and mark as read

### Critical Failures
- Storage down: Circuit breaker pattern
- Graph API auth failure: Alert ops, halt processing
- Key Vault unreachable: Use cached secrets (1hr TTL)

## Performance Targets

- End-to-end: <60 seconds per invoice
- Vendor match rate: >80%
- Error rate: <1%
- Concurrent processing: 50 invoices
- Cold start: ~2-4 seconds (Python on Linux)

## Current Implementation Status

**Phase 1 (MVP) - ACTIVE:**
- ✅ Project structure and documentation
- ✅ Infrastructure templates (Bicep)
- ✅ Data models and schemas
- 🔄 Core functions (10% complete - placeholders only)
- ⏳ Integration with Graph API
- ⏳ Vendor seeding script

**Not Started:**
- PDF extraction (Phase 2)
- AI vendor matching (Phase 2)
- NetSuite integration (Phase 3)
- Power BI analytics (Phase 3)