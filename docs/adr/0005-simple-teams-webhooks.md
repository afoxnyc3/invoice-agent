# ADR-0005: Simple Teams Webhooks Only

**Date:** 2024-11-09
**Status:** Accepted

## Context

Teams integration needed for notifications. Options were incoming webhooks (simple) vs Bot Framework (full interactive).

## Decision

Use incoming webhooks for Teams notifications, no bot framework.

## Rationale

- Notifications only, no interaction needed
- No app registration required
- NetSuite handles approvals downstream
- Reduces complexity by 75%

## Consequences

- ✅ Simple implementation (1 day vs 1 week)
- ✅ No authentication complexity
- ⚠️ One-way communication only
- ⚠️ No interactive cards

## Related

- [ADR-0011: NetSuite Handles Approvals](0011-netsuite-handles-approvals.md)
- See `Notify/` function for implementation
