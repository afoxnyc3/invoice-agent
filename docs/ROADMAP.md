# Invoice Agent - Product Roadmap

## Vision
Achieve 95% straight-through processing of invoices with zero manual intervention for known vendors, while maintaining complete audit compliance and financial controls.

---

## Phase 1: Core MVP + Webhooks + Intelligence ✅ COMPLETE

**Goal:** Real-time invoice processing with <10 second latency and AI-powered vendor extraction

### Completed (Nov-Dec 2024)

**Infrastructure:**
- [x] Azure Function App (Consumption Plan, Python 3.11)
- [x] Storage (Tables, Blobs, Queues)
- [x] Key Vault + Managed Identity
- [x] Application Insights monitoring
- [x] Azure OpenAI (gpt-4o-mini)
- [x] AZQR Phase 1 compliance (container soft delete, Key Vault diagnostics, auto-heal, cost tags)

**Functions (9 total):**
- [x] MailWebhook - HTTP endpoint for Graph notifications
- [x] MailWebhookProcessor - Process webhook notifications with PDF extraction
- [x] SubscriptionManager - Auto-renew Graph subscriptions
- [x] MailIngest - Hourly fallback polling
- [x] ExtractEnrich - Vendor lookup + PDF extraction + AI enrichment
- [x] PostToAP - Route to accounts payable
- [x] Notify - Teams notifications (Adaptive Cards via Power Automate)
- [x] AddVendor - HTTP vendor management
- [x] Health - Health check endpoint

**Features:**
- [x] Real-time webhooks (<10 sec latency vs 5 min polling)
- [x] PDF vendor extraction (pdfplumber + Azure OpenAI, 95%+ accuracy)
- [x] Fuzzy vendor matching (rapidfuzz)
- [x] Duplicate detection (message ID + invoice hash)
- [x] Unknown vendor handling (registration email)
- [x] Power Automate Teams integration (Adaptive Cards v1.4)
- [x] Direct blob URL deployment (ADR-0034)
- [x] VendorMaster seeded and operational

**Quality:**
- [x] 472 tests (446 unit + 26 integration), 93% coverage
- [x] CI/CD with blob URL deployment + health check verification
- [x] 34 Architecture Decision Records
- [x] Cross-project reference documentation

### Metrics Achieved
| Metric | Target | Actual |
|--------|--------|--------|
| Latency | <60s | <10s |
| Test Coverage | 85% | 93% |
| Functions | 5 | 9 |
| Architecture | Polling | Webhooks |
| ADRs | - | 34 |

---

## Phase 2: Scale & OCR 🎯 NEXT

**Goal:** Handle edge cases and expand extraction capabilities

### Planned Features
- [ ] **OCR for Scanned PDFs** - Azure Form Recognizer for image-based invoices
- [ ] **Multi-Currency Support** - Beyond USD/EUR/CAD
- [ ] **Batch Processing** - Handle high-volume periods
- [ ] **VNet Integration** - Network isolation (#72)

### Technical Improvements
- [ ] Performance optimization under load
- [ ] Enhanced retry logic
- [ ] Connection pooling
- [ ] Caching for vendor lookups

### Success Metrics
- 95% automation rate
- <5% unknown vendors
- 99% duplicate detection
- 20-second average processing

---

## Phase 3: Integration 📈

**Goal:** Direct system integration

### Features
- [ ] **NetSuite Direct Integration** - Skip email, post to API
- [ ] **Multi-Mailbox Support** - Multiple departments
- [ ] **Power BI Dashboard** - Analytics and reporting
- [ ] **Vendor Self-Service** - Portal for vendor management

---

## Phase 4: Enterprise 🏢

**Goal:** Full enterprise platform

### Features
- [ ] Multi-entity support
- [ ] Advanced compliance (SOX)
- [ ] Mobile approval app
- [ ] AI assistant (natural language queries)

---

## Release History

| Version | Date | Key Changes |
|---------|------|-------------|
| 0.1 | Nov 9, 2024 | Project initialization, architecture, data models |
| 1.0 | Nov 11, 2024 | Core MVP (5 functions, timer-based, 98 tests) |
| 2.0 | Nov 20, 2024 | Webhook migration (9 functions, <10s latency) |
| 2.1 | Nov 24, 2024 | PDF vendor extraction (Azure OpenAI) |
| 2.2 | Nov 25, 2024 | Duplicate detection enhancements |
| 2.3 | Nov 28, 2024 | mypy strict + 85% coverage |
| 2.4 | Nov 28, 2024 | Auto rollback + secrets validation |
| 2.5 | Nov 29, 2024 | Documentation cleanup |
| 2.6 | Dec 3, 2024 | AZQR Phase 1 compliance |
| 2.7 | Dec 3, 2024 | ADR system (31 records) |
| 2.8 | Dec 4, 2024 | Bicep fixes + documentation audit |
| 3.0 | Dec 6, 2025 | Power Automate integration, AP email format |
| 3.1 | Dec 8, 2025 | Fuzzy matching, App Insights workbook, test fixes |
| 3.2 | Dec 10, 2025 | Blob URL deployment, integration tests, cross-project docs |
| 3.3 | Feb 7, 2026 | Architecture diagram, documentation cleanup |

---

## Open Issues

| Issue | Priority | Description |
|-------|----------|-------------|
| #72 | P3 | VNet integration for network isolation |

---

**Last Updated:** 2026-02-07
**Version:** 3.3
