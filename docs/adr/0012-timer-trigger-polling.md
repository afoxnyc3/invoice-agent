# ADR-0012: Timer Trigger over Event-Based

**Date:** 2024-11-09
**Status:** Superseded by [ADR-0021](0021-event-driven-webhooks.md)

## Context

Need strategy for email ingestion. Options were timer-based polling or Graph API webhooks.

## Decision

Use 5-minute timer instead of Graph webhooks for MVP simplicity.

## Rationale

- Simpler implementation
- No webhook registration needed
- No public endpoint required
- Acceptable latency (5 minutes)

## Consequences

- ✅ Simple, reliable
- ✅ No external dependencies
- ⚠️ 5-minute maximum latency
- ⚠️ Unnecessary polling when no emails

## Why Superseded

- Timer triggers proved unreliable on Consumption plan (AlwaysOn not available)
- Latency requirements changed to <10 seconds
- Webhook solution provides 70% cost reduction ($0.60/month vs $2.00/month)

## Related

- **Superseded by:** [ADR-0021: Event-Driven Webhooks](0021-event-driven-webhooks.md)
