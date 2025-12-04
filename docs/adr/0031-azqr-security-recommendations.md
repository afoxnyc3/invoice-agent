# ADR-0031: AZQR Security Recommendations

**Date:** 2024-12-03
**Status:** Accepted

## Context

Azure Quick Review (AZQR) scan identified security and reliability improvements. Needed to prioritize recommendations by cost and impact.

## Decision

Implement Phase 1 (zero/low cost) AZQR recommendations immediately, defer Phase 2 items requiring budget approval.

## Phase 1 Implementations (Dec 2024)

### Storage Account
- Container soft delete policy (30 days prod, 7 days dev)
- Enables recovery of accidentally deleted containers

### Key Vault
- Diagnostic settings for audit logging
- Logs AuditEvent category and AllMetrics
- 90-day retention for compliance

### Function App
- Auto-heal configuration
- Triggers: 10x 500 errors in 5 min, or 5x slow requests (>60s) in 5 min
- Action: Recycle worker process

### Resource Tags
- Added CostCenter, Application, CreatedDate tags
- Enables cost tracking and governance

## Rationale

- Zero/minimal cost ($0-2/month for diagnostic logs)
- Immediate security improvements
- Compliance readiness
- Auto-heal improves reliability

## Consequences

- ✅ Better security posture
- ✅ Compliance audit trail
- ✅ Automatic recovery from failures
- ✅ Cost tracking enabled
- ⚠️ Slight increase in log storage costs

## Phase 2 (Deferred)

- VNet integration (requires Premium plan)
- Private endpoints (cost implications)
- Geo-redundant storage (budget required)

## Related

- Commit: `1d0a175 infra: implement AZQR Phase 1 recommendations`
- [ADR-0029: Modular Bicep Architecture](0029-modular-bicep-architecture.md)
- See `infrastructure/bicep/modules/` for implementations
