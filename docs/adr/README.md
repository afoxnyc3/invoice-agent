# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for the Invoice Agent project.

## What is an ADR?

An ADR captures a significant architectural decision along with its context and consequences. They help us:
- Remember *why* decisions were made
- Onboard new team members faster
- Avoid relitigating settled decisions
- Know when to revisit outdated decisions

## ADR Index

| # | Title | Status | Date |
|---|-------|--------|------|
| [0000](0000-template.md) | Template | N/A | N/A |
| [0001](0001-serverless-azure-functions.md) | Serverless Azure Functions | Accepted | 2024-11-09 |
| [0002](0002-table-storage-over-cosmos.md) | Table Storage over Cosmos DB | Accepted | 2024-11-09 |
| [0003](0003-storage-queues-over-service-bus.md) | Storage Queues over Service Bus | Accepted | 2024-11-09 |
| [0004](0004-email-based-vendor-extraction.md) | Email-Based Vendor Extraction | Superseded | 2024-11-09 |
| [0005](0005-simple-teams-webhooks.md) | Simple Teams Webhooks | Accepted | 2024-11-09 |
| [0006](0006-graph-api-for-email.md) | Graph API for Email Operations | Accepted | 2024-11-09 |
| [0007](0007-ulid-for-transaction-ids.md) | ULID for Transaction IDs | Accepted | 2024-11-09 |
| [0008](0008-function-line-limit.md) | 25-Line Function Limit | Superseded | 2024-11-09 |
| [0009](0009-python-311-runtime.md) | Python 3.11 Runtime | Accepted | 2024-11-09 |
| [0010](0010-managed-identity-auth.md) | Managed Identity for Auth | Accepted | 2024-11-09 |
| [0011](0011-netsuite-handles-approvals.md) | NetSuite Handles Approvals | Accepted | 2024-11-09 |
| [0012](0012-timer-trigger-polling.md) | Timer Trigger Polling | Superseded | 2024-11-09 |
| [0013](0013-consumption-plan.md) | Consumption Plan | Accepted | 2024-11-09 |
| [0014](0014-single-region-deployment.md) | Single Region Deployment | Accepted | 2024-11-09 |
| [0015](0015-email-routing-to-ap.md) | Email Routing to AP | Accepted | 2024-11-09 |
| [0016](0016-bicep-over-terraform.md) | Bicep over Terraform | Accepted | 2024-11-09 |
| [0017](0017-test-coverage-target.md) | Test Coverage Target (60%) | Superseded | 2024-11-09 |
| [0018](0018-github-actions-cicd.md) | GitHub Actions CI/CD | Accepted | 2024-11-09 |
| [0019](0019-application-insights-monitoring.md) | Application Insights Monitoring | Accepted | 2024-11-09 |
| [0020](0020-blue-green-deployments.md) | Blue-Green Deployments | Superseded | 2024-11-09 |
| [0021](0021-event-driven-webhooks.md) | Event-Driven Webhooks | Accepted | 2024-11-20 |
| [0022](0022-pdf-vendor-extraction.md) | PDF Vendor Extraction | Accepted | 2024-11-24 |
| [0023](0023-slot-swap-resilience.md) | Slot Swap Resilience | Accepted | 2024-12-03 |
| [0024](0024-test-coverage-enforcement.md) | 85% Test Coverage Enforcement | Accepted | 2024-11 |
| [0025](0025-staging-slot-settings-sync.md) | Staging Slot Settings Sync | Accepted | 2024-11 |
| [0026](0026-cyclomatic-complexity-metric.md) | Cyclomatic Complexity Metric | Accepted | 2024-11 |
| [0027](0027-email-loop-prevention.md) | Email Loop Prevention | Accepted | 2024-11 |
| [0028](0028-message-id-deduplication.md) | Message ID Deduplication | Accepted | 2024-11 |
| [0029](0029-modular-bicep-architecture.md) | Modular Bicep Architecture | Accepted | 2024-11 |
| [0030](0030-azurite-integration-tests.md) | Azurite for Integration Tests | Accepted | 2024-11 |
| [0031](0031-azqr-security-recommendations.md) | AZQR Security Recommendations | Accepted | 2024-12-03 |
| [0032](0032-circuit-breaker-pattern.md) | Circuit Breaker Pattern | Accepted | 2024-12-05 |
| [0033](0033-schema-versioning-strategy.md) | Schema Versioning Strategy | Accepted | 2024-12-05 |
| [0034](0034-blob-url-deployment.md) | Blob URL Deployment | Accepted | 2025-12-06 |

## ADR Status Legend

| Status | Meaning |
|--------|---------|
| **Proposed** | Under discussion, not yet decided |
| **Accepted** | Decision made and in effect |
| **Deprecated** | No longer applies, but not replaced |
| **Superseded** | Replaced by a newer ADR |

## Superseded ADRs

The following ADRs have been replaced:

| Original | Superseded By | Reason |
|----------|--------------|--------|
| [0004](0004-email-based-vendor-extraction.md) | [0022](0022-pdf-vendor-extraction.md) | AI-powered PDF extraction improved accuracy from 80% to 95% |
| [0008](0008-function-line-limit.md) | [0026](0026-cyclomatic-complexity-metric.md) | Cyclomatic complexity better measures actual complexity |
| [0012](0012-timer-trigger-polling.md) | [0021](0021-event-driven-webhooks.md) | Webhooks provide <10s latency and 70% cost savings |
| [0017](0017-test-coverage-target.md) | [0024](0024-test-coverage-enforcement.md) | Coverage increased from 60% to 85% post-MVP |
| [0020](0020-blue-green-deployments.md) | [0034](0034-blob-url-deployment.md) | Slot swap unreliable on Linux Consumption; blob URL is more reliable |

## Creating a New ADR

1. Copy `0000-template.md` to `NNNN-short-title.md` (next number in sequence)
2. Fill in all sections
3. Submit for review via PR
4. Update this index once accepted

## ADR Categories

### Infrastructure & Deployment
0001, 0013, 0014, 0016, 0018, 0020, 0023, 0025, 0029, 0031, 0034

### Data & Storage
0002, 0003, 0007, 0028, 0033

### Email Processing
0004, 0006, 0012, 0021, 0022, 0027

### Integration
0005, 0011, 0015

### Security & Auth
0010

### Code Quality
0008, 0009, 0017, 0024, 0026, 0030

### Monitoring & Resilience
0019, 0032

## Cross-Project Adoption

Several ADRs from this project have been adopted by sibling TypeScript projects (email-agent, phishing-agent) via their RFC processes. Key adopted patterns:

- **ADR-0021** (Webhooks) — Adopted by phishing-agent
- **ADR-0026** (Cyclomatic Complexity) — Adopted by both TS projects via ESLint
- **ADR-0032** (Circuit Breaker) — Adopted by both TS projects via cockatiel
- **ADR-0033** (Schema Versioning) — Adopted by both TS projects via Zod

See [Cross-Project Reference](../CROSS_PROJECT_REFERENCE.md) for full details.
