# Changelog

All notable changes to the Invoice Agent project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- OCR for scanned/image-based PDFs (Azure Form Recognizer)
- NetSuite direct integration
- VNet integration (#72)

## [3.3.0] - 2026-02-07

### Added
- **Architecture Diagram** - FigJam reference architecture diagram (closes #122)

### Changed
- Consolidated changelogs into single root `CHANGELOG.md`
- Cleaned up README (removed duplication, added Figma link, fixed structure)
- Updated ROADMAP.md with current state and release history
- Fixed stale version/date stamps across core documents

## [3.2.0] - 2025-12-10

### Added
- **Cross-Project Reference Documentation** - How invoice-agent patterns were adopted by sibling TS projects (closes #121)
- **ADR-0013 (Consumption Plan)** - Synced ADR index and added missing ADR (closes #120)
- **Blob URL Deployment** (ADR-0034) - Direct blob URL deployment replaces unreliable slot swap
  - Each deployment creates version-tagged package in blob storage
  - 1-year SAS URLs for package access
  - Simplified CI/CD pipeline (~150 lines vs 520 lines)
- **Integration Tests Complete** - All 26 integration tests passing with Azurite
  - E2E flow tests, queue retry tests, vendor management tests, performance tests

### Changed
- CI/CD pipeline simplified from 520 to ~150 lines
- Deployment pattern: slot swap replaced with direct blob URL deploy (ADR-0034)

## [3.1.0] - 2025-12-08

### Added
- **Fuzzy Vendor Matching** - rapidfuzz-based fuzzy matching for vendor name variations (#116)
- **App Insights Workbook** - Operations dashboard for monitoring (#115)
- **Observability Quick Start Guide** - Getting started with monitoring (#117)

### Fixed
- **Teams Notification Failures** - Fixed deduplication logic that blocked unknown vendor notifications (#113)
  - `is_message_already_processed()` now only blocks if Status="processed" (not "unknown")
- Resolved all integration test failures (26/26 passing)
- Cleaned up stale TODOs and updated metrics (#114)

## [3.0.0] - 2025-12-06

### Added
- **AP Email Format Update** - Shows expense department and GL code in subject (#119)
- **Power Automate Integration** - Adaptive Card format for Power Automate compatibility
  - Power Automate flows expect `attachments` array, not MessageCard format
  - Expression: `triggerBody()?['attachments']?[0]?['content']`

### Fixed
- Power Automate webhook payload structure (#118)
- Added required `contentUrl` field for Power Automate
- Avoided chunked transfer encoding for Power Automate webhook
- Corrected Power Automate expression (no `string()` wrapper needed)

## [2.8.0] - 2024-12-04

### Fixed
- **Bicep Environment URLs** - Replaced hardcoded Azure URLs with `environment()` function for cloud compatibility
- **Slot Swap Resilience** - Added handling for stuck slot swap operations in deployment pipeline

### Changed
- Comprehensive documentation audit against codebase and Azure resources
- Added missing documentation for: Rate Limiting, Deduplication, Email Loop Prevention
- Added RateLimits table schema to ARCHITECTURE.md
- Updated Key Vault secrets list to match actual deployment

## [2.7.0] - 2024-12-03

### Added
- **ADR System** - 31 Architecture Decision Records documented
  - Migrated from DECISIONS.md to individual files in `docs/adr/`
  - 10 new ADRs (0022-0031)
- `docs/adr/README.md` - Full index with categories
- `docs/adr/0000-template.md` - Template for new ADRs
- ADR guidance section in CLAUDE.md

## [2.6.0] - 2024-12-03

### Added
- **AZQR Phase 1 Compliance** - Infrastructure hardening based on Azure Quick Review scan
  - Container soft delete (30 days prod, 7 days dev)
  - Key Vault diagnostics to Log Analytics (90 day retention)
  - Auto-heal on error patterns (10x 500s or 5x slow requests in 5 min)
  - Resource tags: CostCenter, Application, CreatedDate

## [2.5.0] - 2024-11-29

### Changed
- Updated test counts to 389 across all docs
- Fixed timer diagram (5min to hourly) in ARCHITECTURE.md
- Archived 3 redundant docs to `docs/archive/`
- Overhauled ROADMAP.md for webhook architecture
- Created `docs/operations/README.md` index

### Fixed
- Azure OpenAI settings now persist through CI deployments (added to functionapp.bicep)

## [2.4.0] - 2024-11-28

### Added
- Automated rollback on deployment failure
- Secrets validation in CI/CD pipeline
- GitHub workflow permissions fixes (CodeQL alerts)

## [2.3.0] - 2024-11-28

### Added
- mypy strict mode enabled
- Test coverage threshold raised to 85%
- 75 edge case tests

## [2.2.0] - 2024-11-25

### Added
- Enhanced duplicate detection (message ID + invoice hash)
- Improved deduplication logic in ExtractEnrich

## [2.1.0] - 2024-11-24

### Added
- **PDF Vendor Extraction** - pdfplumber + Azure OpenAI (gpt-4o-mini)
  - 95%+ accuracy, ~500ms latency, ~$0.001/invoice
  - Graceful fallback to email domain extraction
  - Integrated into MailWebhookProcessor

## [2.0.0] - 2024-11-20

### Added
- **Real-time Webhook Processing** - Event-driven email processing via Graph API
  - MailWebhook HTTP function receives change notifications
  - MailWebhookProcessor queue function processes notifications
  - SubscriptionManager timer function auto-renews subscriptions every 6 days
  - Health function for monitoring
  - <10 second latency, 70% cost savings vs polling

### Changed
- Architecture: Timer-based polling to event-driven webhooks
- MailIngest reduced from 5-minute polling to hourly fallback
- Function count: 5 to 9

## [1.0.0] - 2024-11-11

### Added
- **Core Pipeline** - All 5 functions implemented and production-ready
  - MailIngest (timer trigger, 5-min polling)
  - ExtractEnrich (vendor lookup + enrichment)
  - PostToAP (AP email routing with attachments)
  - Notify (Teams webhook notifications)
  - AddVendor (HTTP vendor management)
- **Shared Utilities** - Graph API client, Pydantic models, ULID generator, structured logger, retry decorator
- **Infrastructure** - Bicep templates, GitHub Actions CI/CD, Application Insights, Key Vault
- **Testing** - 98 tests, 96% coverage
- **Documentation** - ARCHITECTURE.md, 20 ADRs, ROADMAP.md, CLAUDE.md

## [0.1.0] - 2024-11-09

### Added
- Project initialization with `.claude/` AI automation tools
- System architecture and 20 architectural decision records
- Bicep templates for Azure resources (planned)
- Data models: VendorMaster, InvoiceTransactions, queue message schemas

---

[Unreleased]: https://github.com/afoxnyc3/invoice-agent/compare/v3.2.0...HEAD
[3.3.0]: https://github.com/afoxnyc3/invoice-agent/compare/v3.2.0...v3.3.0
[3.2.0]: https://github.com/afoxnyc3/invoice-agent/compare/v3.1.0...v3.2.0
[3.1.0]: https://github.com/afoxnyc3/invoice-agent/compare/v3.0.0...v3.1.0
[3.0.0]: https://github.com/afoxnyc3/invoice-agent/compare/v2.8.0...v3.0.0
[2.8.0]: https://github.com/afoxnyc3/invoice-agent/compare/v2.7.0...v2.8.0
[2.7.0]: https://github.com/afoxnyc3/invoice-agent/compare/v2.6.0...v2.7.0
[2.6.0]: https://github.com/afoxnyc3/invoice-agent/compare/v2.5.0...v2.6.0
[2.5.0]: https://github.com/afoxnyc3/invoice-agent/compare/v2.4.0...v2.5.0
[2.4.0]: https://github.com/afoxnyc3/invoice-agent/compare/v2.3.0...v2.4.0
[2.3.0]: https://github.com/afoxnyc3/invoice-agent/compare/v2.2.0...v2.3.0
[2.2.0]: https://github.com/afoxnyc3/invoice-agent/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/afoxnyc3/invoice-agent/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/afoxnyc3/invoice-agent/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/afoxnyc3/invoice-agent/compare/v0.1.0...v1.0.0
[0.1.0]: https://github.com/afoxnyc3/invoice-agent/releases/tag/v0.1.0
