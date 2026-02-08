# Cross-Project Reference

This document tracks how architectural patterns from invoice-agent (Python) were adopted by the TypeScript sibling projects: **email-agent** and **phishing-agent**.

Invoice-agent serves as the **reference architecture** — the most mature of the three projects, with 34 ADRs, 93% test coverage, and production-proven patterns.

---

## Pattern Adoption Matrix

| Pattern | Invoice-Agent Source | Email-Agent | Phishing-Agent | Notes |
|---------|---------------------|-------------|----------------|-------|
| ADR/RFC process | `docs/adr/` (34 records) | Adopted (RFCs) | Adopted (RFCs) | TS projects use RFC naming convention |
| Webhook receiver | [ADR-0021](adr/0021-event-driven-webhooks.md), `src/MailWebhook/` | — | Adopted | Phishing agent receives Graph webhooks |
| Timer fallback | [ADR-0021](adr/0021-event-driven-webhooks.md), `src/MailIngest/` | — | Adopted | Hourly safety net for missed notifications |
| Circuit breaker | [ADR-0032](adr/0032-circuit-breaker-pattern.md), `src/shared/circuit_breaker.py` | Adopted | Adopted | TS uses `cockatiel` library (Python uses `pybreaker`) |
| Schema versioning | [ADR-0033](adr/0033-schema-versioning-strategy.md), `src/shared/models.py` | Adopted | Adopted | TS uses Zod schemas with version field |
| Cyclomatic complexity | [ADR-0026](adr/0026-cyclomatic-complexity-metric.md) | Adopted | Adopted | TS enforced via ESLint `complexity` rule (max 10) |
| Coverage threshold 85% | [ADR-0024](adr/0024-test-coverage-enforcement.md) | Adopted | Adopted | TS uses `c8`/`vitest` coverage |
| Gitleaks | `.gitleaks.toml` + CI | Adopted | Adopted | Same `.gitleaks.toml` config |
| Pre-commit hooks | `.pre-commit-config.yaml` | Adopted (husky) | Adopted (husky) | TS equivalent: husky + lint-staged |
| Email loop prevention | `src/shared/email_processor.py` `should_skip_email()` | Adopted | Adopted | Same sender/subject filtering logic |
| Health check verification | CI deploy job | Adopted | Adopted | Verify function count after deploy |
| Blob URL deployment | [ADR-0034](adr/0034-blob-url-deployment.md) | N/A | N/A | TS projects use container deployment |

---

## Key ADR Adoption Details

### ADR-0021: Event-Driven Webhooks

**Invoice-agent pattern:** Microsoft Graph Change Notifications via HTTP webhook endpoint, with automatic subscription renewal every 6 days and hourly timer fallback.

**Adopted by phishing-agent:** The phishing agent uses the same webhook + timer fallback architecture to monitor mailboxes for phishing reports. The core pattern (fast webhook path, slow timer safety net) was carried over directly.

**Deviations:**
- Phishing-agent processes different email content (phishing reports vs invoices)
- Subscription renewal timing may differ based on notification type
- email-agent does not use this pattern (different ingestion mechanism)

---

### ADR-0026: Cyclomatic Complexity Metric

**Invoice-agent pattern:** Maximum cyclomatic complexity of 10 per function, enforced via flake8 in CI. Replaced the earlier 25-line function limit (ADR-0008) with a research-backed metric.

**Adopted by both TS projects:** Enforced via ESLint's `complexity` rule with the same threshold of 10.

**Deviations:**
- Python enforcement: `flake8` with `--max-complexity=10`
- TypeScript enforcement: ESLint `complexity` rule in `.eslintrc`
- Same thresholds: 1-3 ideal, 4-7 acceptable, 8-10 review, >10 must refactor

---

### ADR-0032: Circuit Breaker Pattern

**Invoice-agent pattern:** Circuit breaker protection on all external service calls (Graph API, Azure OpenAI, Azure Blob Storage) using `pybreaker` library. Prevents cascade failures with configurable failure thresholds and automatic recovery.

**Adopted by both TS projects:** Same pattern implemented using the `cockatiel` library (TypeScript equivalent of pybreaker).

**Deviations:**
- Python: `pybreaker` library with `CircuitBreaker` class
- TypeScript: `cockatiel` library with `CircuitBreakerPolicy`
- Same concept: closed → open → half-open state transitions
- Configuration may differ per service based on latency characteristics

---

### ADR-0033: Schema Versioning Strategy

**Invoice-agent pattern:** Semantic versioning on queue message Pydantic models via `schema_version` field (default "1.0"). Enables non-breaking deployments where old and new code versions coexist with in-flight messages.

**Adopted by both TS projects:** Same `schema_version` field pattern using Zod validation schemas.

**Deviations:**
- Python: Pydantic models with `schema_version: str = "1.0"`
- TypeScript: Zod schemas with `schema_version` field
- Same deprecation policy: 30 days minor, 90 days major
- Same backward compatibility rules

---

## Technology Mapping

| Concern | Invoice-Agent (Python) | TS Projects |
|---------|----------------------|-------------|
| Runtime | Azure Functions (Python 3.11) | Azure Functions (Node.js) |
| Validation | Pydantic | Zod |
| Circuit breaker | pybreaker | cockatiel |
| Complexity check | flake8 | ESLint |
| Formatter | Black | Prettier |
| Linter | flake8 | ESLint |
| Type checker | mypy (strict) | TypeScript (strict) |
| Test framework | pytest | vitest |
| Coverage tool | pytest-cov | c8/vitest |
| Pre-commit | pre-commit | husky + lint-staged |
| Secret scanning | Gitleaks | Gitleaks |
| IaC | Bicep | Bicep |
| Decision records | ADRs | RFCs |

---

## Adding New Cross-Project Patterns

When a pattern is established in invoice-agent and should be adopted:

1. Document the pattern in an ADR in this project
2. Create corresponding RFCs in the TS projects
3. Update this reference document with the adoption details
4. Note any deviations or TypeScript-specific adaptations
