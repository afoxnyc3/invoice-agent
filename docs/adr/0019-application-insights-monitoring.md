# ADR-0019: Application Insights for Monitoring

**Date:** 2024-11-09
**Status:** Accepted

## Context

Need observability platform for monitoring, logging, and alerting. Options were Application Insights, Datadog, or custom ELK stack.

## Decision

Use Application Insights for all monitoring and observability.

## Rationale

- Native Azure Functions integration
- Automatic dependency tracking
- Built-in dashboards and alerting
- Cost-effective for our volume
- No additional infrastructure

## Consequences

- ✅ Zero-config setup
- ✅ Rich insights out of the box
- ✅ Integrated alerts
- ⚠️ Azure-only (vendor lock-in)

## Related

- [ADR-0007: ULID for Transaction IDs](0007-ulid-for-transaction-ids.md) - Correlation IDs
- See `docs/monitoring/LOG_QUERIES.md` for KQL queries
