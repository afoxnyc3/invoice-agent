# Changelog

All notable changes to the Invoice Agent project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Pydantic V2 validator migration for future-proofing
- `clear_vendors.py` script for resetting VendorMaster table

### Fixed
- **Teams Notifications Not Delivered** - Fixed deduplication logic that blocked unknown vendor notifications
  - `is_message_already_processed()` now only blocks if Status="processed" (not "unknown")
  - Unknown vendor invoices now properly trigger Teams notifications
- **Power Automate Payload Format** - Fixed Adaptive Card format for Power Automate compatibility
  - Power Automate flows expect `attachments` array, not MessageCard format

## [1.2.0] - 2025-11-26

### Added
- **Enhanced Field Extraction** - Extract invoice amount, due date, and payment terms from PDF invoices
  - Invoice amount with currency detection ($, USD, EUR, CAD)
  - Due date parsing from multiple formats (ISO, MDY, DMY, written)
  - Payment terms extraction (Net 30, 2/10 net 30, Due upon receipt)
- **Application Access Policy** - Restrict Graph API app to invoice mailbox only
  - PowerShell script for automated policy setup (`infrastructure/scripts/setup_application_access_policy.ps1`)
  - Re-enabled `mark_as_read()` functionality with secure mailbox restriction
- **Duplicate Invoice Detection** - Prevent duplicate payments for same vendor/day invoices
  - MD5 hash-based detection using vendor + sender + date
  - 90-day lookback window with ProcessedAt timestamp filtering
  - Teams notification for duplicate detection

### Fixed
- P1 bug: `check_duplicate_invoice` now uses ProcessedAt timestamp instead of partition key for date filtering
- Alert threshold for function failures increased from 0 to 5 to reduce noise

## [1.1.0] - 2025-11-24

### Added
- **PDF Vendor Extraction** - Intelligent vendor name extraction from PDF invoices
  - Uses pdfplumber for text extraction
  - Azure OpenAI (gpt-4o-mini) for vendor identification
  - 95%+ accuracy, ~500ms latency, ~$0.001/invoice
  - Graceful fallback to email domain if extraction fails
- **Duplicate Processing Prevention** - Prevent duplicate vendor registration emails
  - Graph API message ID tracking for deduplication
  - InvoiceTransaction table queries by OriginalMessageId

### Fixed
- ExtractEnrich deduplication logic issues (6 critical fixes)
- Unknown vendors now queue EnrichedInvoice with status="unknown"
- Fixed EmailsSentCount initialization
- Added RecipientEmail field validation

## [1.0.0] - 2025-11-20

### Added
- **Real-time Webhook Processing** - Event-driven email processing via Graph API
  - MailWebhook HTTP function receives change notifications
  - MailWebhookProcessor queue function processes notifications
  - SubscriptionManager timer function auto-renews subscriptions every 6 days
  - <10 second latency, 70% cost savings vs polling
- **Fallback Timer** - MailIngest now runs hourly as safety net
- **Monitoring Alerts** - Azure Monitor alerts for duplicate processing and function failures
- **CI/CD Pipeline** - GitHub Actions with staging slot deployment pattern
  - 98 tests, 96% coverage
  - Automatic staging deployment and production swap

### Changed
- Migrated from 5-minute polling to webhook-based architecture
- MailIngest reduced from primary (5-min) to fallback (hourly)

### Security
- Removed Mail.ReadWrite permission requirement (v1.0.0)
- Key Vault integration for all secrets
- Application Insights for observability

## [0.1.0] - 2025-11-15

### Added
- Initial invoice processing pipeline
- MailIngest timer function (5-minute polling)
- ExtractEnrich queue function for vendor lookup
- PostToAP queue function for AP email routing
- Notify queue function for Teams webhooks
- AddVendor HTTP function for vendor management
- Pydantic models for queue messages
- Azure Table Storage for VendorMaster and InvoiceTransactions
- Azure Blob Storage for invoice attachments
- Graph API integration for email access

---

[Unreleased]: https://github.com/afoxnyc3/invoice-agent/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/afoxnyc3/invoice-agent/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/afoxnyc3/invoice-agent/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/afoxnyc3/invoice-agent/compare/v0.1.0...v1.0.0
[0.1.0]: https://github.com/afoxnyc3/invoice-agent/releases/tag/v0.1.0
