# Architectural Decision Log

This document records all significant architectural decisions made during the development of the Invoice Agent system.

---

## ADR-001: Serverless Azure Functions over Container Apps

**Date:** 2024-11-09
**Status:** Accepted
**Context:** Need to choose compute platform for invoice processing
**Decision:** Use Azure Functions on Consumption plan

**Rationale:**
- Variable workload (5-50 invoices/day) makes pay-per-execution ideal
- No idle costs during quiet periods
- Auto-scaling handled by platform
- Faster development with less infrastructure management
- Native integration with Azure Storage queues

**Consequences:**
- ✅ Cost-effective for sporadic workloads
- ✅ Zero maintenance of infrastructure
- ⚠️ Cold start latency (2-4 seconds)
- ⚠️ 5-minute execution timeout limit

---

## ADR-002: Table Storage over Cosmos DB

**Date:** 2024-11-09
**Status:** Accepted
**Context:** Need database for vendor lookups and transaction logging
**Decision:** Use Azure Table Storage

**Rationale:**
- Simple key-value lookups only
- <1000 vendors expected
- 100x cheaper than Cosmos DB (~$5/month vs $500/month)
- No complex queries or relationships needed
- Same storage account as blobs/queues

**Consequences:**
- ✅ Extremely cost-effective
- ✅ Simple to implement and maintain
- ⚠️ Limited query capabilities
- ⚠️ No server-side aggregations

---

## ADR-003: Storage Queues over Service Bus

**Date:** 2024-11-09
**Status:** Accepted
**Context:** Need messaging between functions
**Decision:** Use Azure Storage Queues

**Rationale:**
- Same storage account (simpler permissions)
- Sufficient for <100 messages/minute
- Built-in Function bindings
- No advanced features needed (topics, sessions)
- 10x cheaper than Service Bus

**Consequences:**
- ✅ Simple integration
- ✅ Cost-effective
- ⚠️ 64KB message size limit
- ⚠️ No message ordering guarantees

---

## ADR-004: Email-Based Vendor Extraction

**Date:** 2024-11-09
**Status:** Accepted
**Context:** Need to identify vendor from invoice
**Decision:** Extract from email sender/subject for MVP

**Rationale:**
- 80% of vendors identifiable from email alone
- Avoids complex PDF parsing
- Faster implementation (2 weeks vs 6 weeks)
- Can add AI extraction in Phase 2

**Consequences:**
- ✅ Quick MVP delivery
- ✅ Simple, reliable logic
- ⚠️ 20% unknown vendor rate initially
- ⚠️ Manual intervention required for unknowns

---

## ADR-005: Simple Teams Webhooks Only

**Date:** 2024-11-09
**Status:** Accepted
**Context:** Teams integration for notifications
**Decision:** Use incoming webhooks, no bot framework

**Rationale:**
- Notifications only, no interaction needed
- No app registration required
- NetSuite handles approvals downstream
- Reduces complexity by 75%

**Consequences:**
- ✅ Simple implementation (1 day vs 1 week)
- ✅ No authentication complexity
- ⚠️ One-way communication only
- ⚠️ No interactive cards

---

## ADR-006: Graph API for Email Operations

**Date:** 2024-11-09
**Status:** Accepted
**Context:** Need to read and send emails
**Decision:** Use Microsoft Graph API for both

**Rationale:**
- Single API for both operations
- Native Azure AD integration
- Better than SMTP/IMAP
- Supports modern authentication

**Consequences:**
- ✅ Unified authentication
- ✅ Rich email metadata
- ⚠️ Rate limiting considerations
- ⚠️ Requires app registration

---

## ADR-007: ULID for Transaction IDs

**Date:** 2024-11-09
**Status:** Accepted
**Context:** Need unique, sortable transaction identifiers
**Decision:** Use ULID instead of GUID or timestamp

**Rationale:**
- Sortable by creation time
- Globally unique
- URL-safe
- Includes timestamp information
- Better than GUID for logs

**Consequences:**
- ✅ Natural time ordering
- ✅ No ID collisions
- ✅ Human-readable in logs
- ⚠️ Additional dependency

---

## ADR-008: 25-Line Function Limit

**Date:** 2024-11-09
**Status:** Accepted
**Context:** Code quality and maintainability
**Decision:** Enforce maximum 25 lines per function

**Rationale:**
- Forces single responsibility
- Improves testability
- Easier code reviews
- Team coding standard

**Consequences:**
- ✅ More maintainable code
- ✅ Better test coverage
- ⚠️ More helper functions
- ⚠️ Potential over-abstraction

---

## ADR-009: Python 3.11 Runtime

**Date:** 2024-11-09
**Status:** Accepted
**Context:** Choose Function App runtime
**Decision:** Python 3.11 on Linux

**Rationale:**
- Team expertise in Python
- Excellent Azure SDK support
- Rich ecosystem for data processing
- Latest stable version
- Linux for better performance

**Consequences:**
- ✅ Familiar to team
- ✅ Fast development
- ✅ Good library support
- ⚠️ Cold start slightly slower than .NET

---

## ADR-010: Managed Identity for All Auth

**Date:** 2024-11-09
**Status:** Accepted
**Context:** Authentication strategy
**Decision:** Use Managed Identity everywhere possible

**Rationale:**
- No secrets in code
- Automatic credential rotation
- Azure-native security
- Simplified operations

**Consequences:**
- ✅ Enhanced security
- ✅ No password management
- ⚠️ Local development complexity
- ⚠️ Requires RBAC setup

---

## ADR-011: NetSuite Handles Approvals

**Date:** 2024-11-09
**Status:** Accepted
**Context:** Approval workflow requirements
**Decision:** Let NetSuite handle all approval logic

**Rationale:**
- Existing, tested workflow
- Finance team familiar with it
- Reduces scope by 50%
- Compliance already handled

**Consequences:**
- ✅ Faster MVP delivery
- ✅ Less complexity
- ✅ Proven approval process
- ⚠️ Dependency on NetSuite

---

## ADR-012: Timer Trigger over Event-Based

**Date:** 2024-11-09
**Status:** Accepted
**Context:** Email polling strategy
**Decision:** Use 5-minute timer instead of Graph webhooks

**Rationale:**
- Simpler implementation
- No webhook registration needed
- No public endpoint required
- Acceptable latency (5 minutes)

**Consequences:**
- ✅ Simple, reliable
- ✅ No external dependencies
- ⚠️ 5-minute maximum latency
- ⚠️ Unnecessary polling when no emails

---

## ADR-013: Consumption Plan over Premium

**Date:** 2024-11-09
**Status:** Accepted
**Context:** Function App hosting plan
**Decision:** Use Consumption (Serverless) plan

**Rationale:**
- Pay only for execution
- Auto-scaling included
- <50 invoices/day doesn't justify Premium
- $0 when not processing

**Consequences:**
- ✅ Cost-effective (~$20/month)
- ✅ Automatic scaling
- ⚠️ Cold starts
- ⚠️ No VNET integration

---

## ADR-014: Single Region Deployment

**Date:** 2024-11-09
**Status:** Accepted
**Context:** Geographic redundancy requirements
**Decision:** Deploy to single region (East US) for MVP

**Rationale:**
- All users in same timezone
- Simplifies deployment
- Cost savings (50% less)
- Can add DR region later

**Consequences:**
- ✅ Simpler architecture
- ✅ Lower costs
- ⚠️ No geographic redundancy
- ⚠️ Single point of failure

---

## ADR-015: Email Routing over Direct API

**Date:** 2024-11-09
**Status:** Accepted
**Context:** How to submit to AP system
**Decision:** Send enriched email to AP mailbox

**Rationale:**
- Maintains current workflow
- No NetSuite API integration needed
- Finance team can verify emails
- Quick implementation

**Consequences:**
- ✅ Familiar process
- ✅ Human verification possible
- ⚠️ Not fully automated
- ⚠️ Email delivery dependencies

---

## ADR-016: Bicep over Terraform

**Date:** 2024-11-09
**Status:** Accepted
**Context:** Infrastructure as Code tooling
**Decision:** Use Bicep for Azure resources

**Rationale:**
- Azure-native
- Cleaner syntax than ARM
- Better IntelliSense
- No state file management

**Consequences:**
- ✅ Native Azure support
- ✅ Simpler than ARM
- ⚠️ Azure-only
- ⚠️ Smaller community than Terraform

---

## ADR-017: 60% Test Coverage for MVP

**Date:** 2024-11-09
**Status:** Accepted
**Context:** Testing requirements for MVP
**Decision:** Require 60% code coverage minimum

**Rationale:**
- Balances quality with speed
- Focus on critical paths
- Can increase post-MVP
- Achievable in 2-week timeline

**Consequences:**
- ✅ Faster delivery
- ✅ Core functionality tested
- ⚠️ Some edge cases untested
- ⚠️ Technical debt for later

---

## ADR-018: GitHub Actions for CI/CD

**Date:** 2024-11-09
**Status:** Accepted
**Context:** CI/CD platform selection
**Decision:** Use GitHub Actions

**Rationale:**
- Already using GitHub
- Good Azure integration
- Free for our usage
- YAML-based configuration

**Consequences:**
- ✅ Integrated with repository
- ✅ No additional tools
- ✅ Good Azure support
- ⚠️ Vendor lock-in

---

## ADR-019: Application Insights for Monitoring

**Date:** 2024-11-09
**Status:** Accepted
**Context:** Observability platform
**Decision:** Use Application Insights

**Rationale:**
- Native Azure Functions integration
- Automatic dependency tracking
- Built-in dashboards
- Cost-effective for our volume

**Consequences:**
- ✅ Zero-config setup
- ✅ Rich insights
- ✅ Integrated alerts
- ⚠️ Azure-only

---

## ADR-020: Blue-Green Deployments

**Date:** 2024-11-09
**Status:** Proposed
**Context:** Deployment strategy
**Decision:** Use slot swapping for zero-downtime

**Rationale:**
- Zero-downtime deployments
- Easy rollback
- Built into Azure Functions
- Production safety

**Consequences:**
- ✅ Safe deployments
- ✅ Quick rollback
- ⚠️ Slightly complex setup
- ⚠️ Double resource cost during deployment

---

## Template for New Decisions

```markdown
## ADR-XXX: [Decision Title]

**Date:** YYYY-MM-DD
**Status:** Proposed|Accepted|Deprecated|Superseded
**Context:** [Why this decision is needed]
**Decision:** [What we decided]

**Rationale:**
- [Key reason 1]
- [Key reason 2]
- [Key reason 3]

**Consequences:**
- ✅ [Positive consequence]
- ⚠️ [Trade-off or risk]
```

---

**How to Use This Document:**
1. Add new decisions as they're made
2. Number them sequentially
3. Never delete - mark as Deprecated or Superseded
4. Link to related decisions
5. Review quarterly for relevance