# Change Log

All notable changes to the Invoice Agent project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- OCR for scanned/image-based PDFs (Azure Form Recognizer)
- Invoice amount extraction (parse amounts, line items)
- NetSuite direct integration
- VNet integration (#72)

---

## [2.7.0] - 2024-12-03

### ADR Practices Established
Comprehensive Architecture Decision Record (ADR) system implemented:

- **31 ADRs documented** - Full architectural decision history
- **Migrated from DECISIONS.md** - 21 existing ADRs converted to individual files
- **10 new ADRs created** - Recent decisions now formally documented:
  - PDF vendor extraction (0022)
  - Slot swap resilience (0023)
  - 85% test coverage (0024)
  - Staging settings sync (0025)
  - Cyclomatic complexity (0026)
  - Email loop prevention (0027)
  - Message ID deduplication (0028)
  - Modular Bicep architecture (0029)
  - Azurite integration tests (0030)
  - AZQR security recommendations (0031)

### Added
- `docs/adr/` directory with standard ADR format
- `docs/adr/README.md` - Full index with categories
- `docs/adr/0000-template.md` - Template for new ADRs
- ADR guidance section in CLAUDE.md

### Changed
- Archived `docs/DECISIONS.md` to `docs/archive/`
- CLAUDE.md version bumped to 2.7

---

## [2.6.0] - 2024-12-03

### Infrastructure Hardening (AZQR Phase 1)
Based on Azure Quick Review security scan, implemented zero/low-cost compliance improvements:

- **Container Soft Delete** - 30 days for production, 7 days for dev (enables container recovery)
- **Key Vault Diagnostics** - AuditEvent logs to Log Analytics (90 day retention)
- **Auto-Heal** - Automatic worker recycle on error patterns (10x 500s or 5x slow requests in 5 min)
- **Resource Tags** - Added CostCenter, Application, CreatedDate for cost governance

### Cost Impact
- Estimated: $0-2/month for diagnostic log ingestion
- All other changes are free Azure features

---

## [2.5.0] - 2024-11-29

### Documentation Cleanup
- Updated test counts to 389 across all docs (from 314)
- Fixed timer diagram (5min → hourly) in ARCHITECTURE.md
- Archived 3 redundant docs to docs/archive/
- Overhauled ROADMAP.md for webhook architecture
- Created docs/operations/README.md index
- Added Azure OpenAI settings to Bicep template (permanent fix)

### Fixed
- Azure OpenAI settings now persist through CI deployments (added to functionapp.bicep)

---

## [2.4.0] - 2024-11-28

### Added
- Automated rollback on deployment failure
- Secrets validation in CI/CD pipeline
- GitHub workflow permissions fixes (CodeQL alerts)

---

## [2.3.0] - 2024-11-28

### Added
- mypy strict mode enabled
- Test coverage threshold raised to 85%
- 75 edge case tests (PR #96)

### Quality
- 389 tests passing (up from 314)
- 85%+ code coverage

---

## [2.2.0] - 2024-11-25

### Added
- Enhanced duplicate detection (message ID + invoice hash)
- Improved deduplication logic in ExtractEnrich

---

## [2.1.0] - 2024-11-24

### Added
- **PDF Vendor Extraction** (pdfplumber + Azure OpenAI gpt-4o-mini)
  - 95%+ accuracy for vendor name extraction
  - ~500ms latency, ~$0.001/invoice cost
  - Graceful fallback to email domain extraction
  - Integrated into MailWebhookProcessor

---

## [2.0.0] - 2024-11-20

### Major - Webhook Migration Complete
Migrated from timer-based polling to event-driven webhooks using Microsoft Graph Change Notifications.

### Added
- **MailWebhook Function** - HTTP endpoint for Graph API notifications
- **MailWebhookProcessor Function** - Queue-based webhook processing with PDF extraction
- **SubscriptionManager Function** - Auto-renews Graph subscriptions every 6 days
- **Health Function** - Health check endpoint for monitoring

### Changed
- **MailIngest** - Changed from 5-minute polling to hourly fallback/safety net
- Architecture: Timer-based → Event-driven webhooks
- Latency: 5 minutes → <10 seconds
- Cost: ~$2/month → ~$0.60/month (70% reduction)

### Technical
- 9 Azure Functions (up from 5)
- CI/CD with staging slot pattern
- Blue/green deployment with auto-swap

---

## [1.0.0] - 2024-11-11

### MVP Complete - All Core Functions Implemented ✅

**Status:** Production-ready code with 98 tests passing and 96% coverage

### Added - Core Pipeline Functions
- **MailIngest Function** (Issue #5)
  - Timer trigger polling every 5 minutes
  - Graph API integration with MSAL authentication
  - Email filtering for attachments
  - Blob storage upload with ULID-based naming
  - Automatic mark-as-read functionality

- **ExtractEnrich Function** (Issue #6)
  - Vendor domain extraction and normalization
  - VendorMaster Table Storage lookup
  - 4-field enrichment (ExpenseDept, GLCode, AllocationSchedule, BillingParty)
  - Unknown vendor handling with email alerts
  - Queue-based message passing

- **PostToAP Function** (Issue #7)
  - Standardized HTML email composition
  - Graph API email sending with attachments
  - InvoiceTransactions audit logging
  - ULID transaction ID generation
  - Notification queue messaging

- **Notify Function** (Issue #8)
  - Teams webhook integration
  - Three message types: success (green), unknown (orange), error (red)
  - Non-blocking failure handling
  - Graceful degradation design

- **AddVendor HTTP Function**
  - HTTP endpoint for vendor management
  - RESTful API for VendorMaster CRUD operations

### Added - Azure Storage Integration (Issue #3)
- Direct Azure SDK usage (BlobServiceClient, TableServiceClient)
- Connection pooling via SDK session management
- Proper error handling for entity not found
- Efficient blob upload/download operations

### Added - Shared Utilities & Infrastructure
- **Graph API Client** (`shared/graph_client.py`)
  - MSAL-based authentication with token caching
  - Retry logic with exponential backoff
  - Throttling support (429 handling)
  - Methods: get_unread_emails, get_attachments, mark_as_read, send_email

- **Data Models** (`shared/models.py`)
  - Pydantic validation for all queue messages
  - RawMail, EnrichedInvoice, NotificationMessage schemas
  - VendorMaster, InvoiceTransaction table entities
  - TeamsMessageCard webhook format

- **ULID Generator** (`shared/ulid_generator.py`)
  - Sortable, unique transaction IDs
  - Timestamp extraction utilities

- **Structured Logger** (`shared/logger.py`)
  - Correlation ID support
  - Application Insights integration

- **Retry Decorator** (`shared/retry.py`)
  - Configurable exponential backoff
  - Transient failure handling

### Infrastructure
- Complete Bicep templates for all Azure resources
- GitHub Actions CI workflow with automated testing
- Application Insights monitoring integration
- Key Vault secret management configuration
- Local development setup with Azurite support

### Testing - Comprehensive Test Suite
- **98 tests passing** across all functions and utilities
- **96% code coverage** (exceeds 60% MVP target)
- Unit tests with pytest and pytest-mock
- Integration test infrastructure (Azurite-ready)
- Test fixtures for queue messages and entities
- Mock implementations for Graph API and Azure Storage

### Documentation
- System architecture documentation (ARCHITECTURE.md)
- 20 architectural decision records (DECISIONS.md)
- 5-phase product roadmap (ROADMAP.md)
- AI development instructions (CLAUDE.md)
- Development workflow guides
- API specifications

### Changed
- Achieved 96% test coverage (exceeded 60% MVP target by 36%)
- Implemented comprehensive error handling across all functions
- Added structured logging with correlation IDs throughout
- Enforced 25-line function limit with helper function extraction

### Technical Decisions
- Chose Azure Functions over Container Apps for serverless benefits
- Selected Table Storage over Cosmos DB for cost efficiency (100x cheaper)
- Implemented ULID for transaction IDs instead of GUIDs (sortable)
- Enforced 25-line function limit for maintainability
- Direct Azure SDK usage over custom wrappers (simpler, follows best practices)
- Simplified Teams integration (webhooks only, no bot framework)
- Removed approval workflow (handled by NetSuite downstream)

---

## [0.1.0] - 2024-11-09

### Added
- Project initialization
- `.claude/` directory with AI automation tools
  - CLAUDE.md - AI development instructions
  - SPEC.md - System specification
  - 5 sub-agents (infrastructure, function, data-model, test, deploy)
  - 5 slash commands (/init, /build, /test, /deploy, /status)

### Documentation
- ARCHITECTURE.md - Complete system design
- DECISIONS.md - Architectural decision records (20 ADRs)
- ROADMAP.md - 5-phase product roadmap
- CHANGE-LOG.md - This file

### Infrastructure
- Bicep templates for Azure resources (planned)
- GitHub Actions CI/CD pipeline (planned)
- Local development setup scripts

### Data Models
- VendorMaster table schema
- InvoiceTransactions table schema
- Queue message schemas (RawMail, Enriched, Notify)

---

## [0.0.1] - 2024-11-08

### Added
- Initial research documents
  - aips-prd.md - Product requirements document
  - aips-architecture.md - Technical architecture
  - aips-sprint1-setup.md - Sprint planning

- Concept implementation
  - Basic Azure Function structure
  - Placeholder functions (MailIngest, ExtractEnrich, PostToAP, Notify)
  - Shared utilities (models.py, kv.py)
  - Basic requirements.txt

### Planned Features
- Email ingestion from shared mailbox
- Vendor extraction and enrichment
- AP email routing
- Teams notifications
- Transaction logging

---

## Versioning Strategy

### Version Format: MAJOR.MINOR.PATCH

- **MAJOR**: Incompatible API changes or major feature additions
- **MINOR**: Backwards-compatible functionality additions
- **PATCH**: Backwards-compatible bug fixes

### Pre-release Versions
- Alpha: 0.0.x - Initial development
- Beta: 0.x.0 - Feature complete, testing
- RC: 1.0.0-rc.x - Release candidates

---

## Release Types

### Production Releases
- Tagged in git with version number
- Deployed to production environment
- Full testing suite passed
- Documentation updated

### Preview Releases
- Deployed to staging only
- For stakeholder feedback
- May contain experimental features

### Hotfix Releases
- Critical bug fixes only
- Expedited testing and deployment
- Increment patch version

---

## Commit Message Format

```
type(scope): description

[optional body]

[optional footer]
```

### Types:
- **feat**: New feature
- **fix**: Bug fix
- **docs**: Documentation change
- **style**: Code style change (formatting, etc)
- **refactor**: Code change that neither fixes a bug nor adds a feature
- **perf**: Performance improvement
- **test**: Adding missing tests
- **chore**: Changes to build process or auxiliary tools

### Examples:
```
feat(mailingest): add Graph API email polling
fix(enrichment): handle missing vendor gracefully
docs(readme): update deployment instructions
perf(storage): implement connection pooling
```

---

## Definition of Done

A feature is considered complete when:

- [ ] Code is written and follows standards
- [ ] Unit tests written and passing
- [ ] Integration tests passing
- [ ] Documentation updated
- [ ] Code reviewed and approved
- [ ] Deployed to staging
- [ ] Smoke tests passing
- [ ] Stakeholder acceptance received

---

## Breaking Changes Policy

### What Constitutes a Breaking Change:
- Removing or renaming a function
- Changing queue message schema
- Modifying table structure
- Altering API contracts
- Changing configuration requirements

### How to Handle:
1. Document in BREAKING_CHANGES.md
2. Provide migration guide
3. Deprecation notice (1 sprint minimum)
4. Major version increment
5. Stakeholder communication

---

## Archive of Significant Changes

### 2024-11-09: Simplified Scope
- **What**: Removed interactive Teams cards and approval workflows
- **Why**: NetSuite handles approvals, reducing complexity by 50%
- **Impact**: Faster delivery, simpler maintenance

### 2024-11-08: Technology Stack Finalized
- **What**: Chose Azure Functions, Table Storage, Python 3.11
- **Why**: Cost-effective, team expertise, fast delivery
- **Impact**: Significant cost savings vs alternative solutions

### 2024-11-07: Project Approval
- **What**: Invoice automation project greenlit
- **Why**: Manual processing inefficiency
- **Impact**: Significant time and cost savings

---

## Future Milestones

### Version 1.0.0 (MVP Release) ✅ COMPLETE
- Core MVP complete
- 80% automation achieved
- Production deployment
- Documentation complete

### Version 2.0.0 (Webhook Migration) ✅ COMPLETE
- Real-time webhooks (<10s latency)
- PDF vendor extraction (95%+ accuracy)
- 9 Azure Functions
- 85%+ test coverage

### Version 3.0.0 (Intelligence Release) 🎯 NEXT
- OCR for scanned PDFs
- Invoice amount extraction
- Enhanced accuracy

### Version 4.0.0 (Integration Release)
- NetSuite direct integration
- Multi-mailbox support
- Analytics dashboard

---

**Maintained By:** Development Team
**Update Frequency:** Every significant change
**Review Schedule:** Weekly during active development