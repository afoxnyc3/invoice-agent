# ADR-0005: Simple Teams Webhooks Only

**Date:** 2024-11-09
**Status:** Accepted

> **Note (Dec 2024):** Implementation updated to use Power Automate with Adaptive Cards v1.4.
> The decision to avoid Bot Framework remains valid. See `src/Notify/__init__.py` for current format
> and `docs/integrations/TEAMS_POWER_AUTOMATE.md` for setup guide.

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
