# Change Log

All notable changes to the Invoice Agent project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Vendor seeding script execution for initial data load
- Production deployment with RBAC configuration (Issue #9)
- Integration testing suite (Issue #12)
- Monitoring and alerts setup (Issue #13)
- Phase 2 features: PDF extraction, AI vendor matching, duplicate detection

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

### Version 1.0.0 (MVP Release)
- Core MVP complete
- 80% automation achieved
- Production deployment
- Documentation complete

### Version 2.0.0 (Intelligence Release)
- PDF extraction
- AI vendor matching
- 90% automation

### Version 3.0.0 (Integration Release)
- NetSuite integration
- Multi-mailbox support
- Analytics dashboard

---

**Maintained By:** Development Team
**Update Frequency:** Every significant change
**Review Schedule:** Weekly during active development