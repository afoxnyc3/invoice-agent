# Invoice Agent - Product Roadmap

## Vision
Achieve 95% straight-through processing of invoices with zero manual intervention for known vendors, while maintaining complete audit compliance and financial controls.

---

## Phase 1: Core MVP + Webhooks ✅ COMPLETE

**Goal:** Real-time invoice processing with <10 second latency

### Completed (Nov 2024)

**Infrastructure:**
- [x] Azure Function App with staging slot
- [x] Storage (Tables, Blobs, Queues)
- [x] Key Vault + Managed Identity
- [x] Application Insights monitoring
- [x] Azure OpenAI (gpt-4o-mini)

**Functions (9 total):**
- [x] MailWebhook - HTTP endpoint for Graph notifications
- [x] MailWebhookProcessor - Process webhook notifications
- [x] SubscriptionManager - Auto-renew Graph subscriptions
- [x] MailIngest - Hourly fallback polling
- [x] ExtractEnrich - Vendor lookup + PDF extraction
- [x] PostToAP - Route to accounts payable
- [x] Notify - Teams notifications
- [x] AddVendor - HTTP vendor management
- [x] Health - Health check endpoint

**Features:**
- [x] Real-time webhooks (<10 sec latency vs 5 min polling)
- [x] PDF vendor extraction (pdfplumber + Azure OpenAI, 95%+ accuracy)
- [x] Duplicate detection (message ID + invoice hash)
- [x] Unknown vendor handling (registration email)
- [x] VendorMaster seeded and operational

**Quality:**
- [x] 389 tests, 85%+ coverage
- [x] CI/CD with staging slot pattern
- [x] Automated rollback on failure
- [x] Secrets validation in pipeline

### Metrics Achieved
| Metric | Target | Actual |
|--------|--------|--------|
| Latency | <60s | <10s |
| Test Coverage | 85% | 85%+ |
| Functions | 5 | 9 |
| Architecture | Polling | Webhooks |

---

## Phase 2: Intelligence & Scale 🎯 NEXT

**Goal:** Increase automation to 95% with enhanced extraction

### Planned Features
- [ ] **OCR for Scanned PDFs** - Azure Form Recognizer
- [ ] **Invoice Amount Extraction** - Parse amounts, line items
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
| 1.0 | Nov 14, 2024 | Core MVP (5 functions, timer-based) |
| 2.0 | Nov 20, 2024 | Webhook migration (9 functions, <10s) |
| 2.1 | Nov 24, 2024 | PDF vendor extraction (Azure OpenAI) |
| 2.2 | Nov 25, 2024 | Duplicate detection enhancements |
| 2.3 | Nov 28, 2024 | mypy strict + 85% coverage |
| 2.4 | Nov 28, 2024 | Auto rollback + secrets validation |
| 2.5 | Nov 29, 2024 | Documentation cleanup |

---

## Open Issues

| Issue | Priority | Description |
|-------|----------|-------------|
| #72 | P3 | VNet integration for network isolation |

---

**Last Updated:** 2025-11-29
**Version:** 2.5
