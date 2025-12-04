# ADR-0023: Slot Swap Resilience Pattern

**Date:** 2024-12-03
**Status:** Accepted

## Context

During Azure Function App slot swaps, environment variables become temporarily unavailable (~30 seconds). This caused KeyError crashes in functions when accessing `AzureWebJobsStorage` during the transition period.

## Decision

Implement "fail-open" pattern: check storage availability before operations, skip gracefully rather than crash if unavailable.

## Rationale

- Slot swaps are critical for zero-downtime deployments
- 30-second unavailability is expected behavior
- Crashing degrades user experience
- Operations can resume normally after swap completes
- Webhooks will retry if needed

## Implementation

- `shared/config.py` - `is_storage_available` property with defensive handling
- `SubscriptionManager/` - Check storage availability before operations
- `deduplication.py` - Fail open if storage unavailable
- Bicep: `slotConfigNames` documents storage should NOT be slot-sticky

## Pattern

```python
if not config.is_storage_available:
    logging.warning("Storage unavailable during slot swap, skipping operation")
    return  # Fail open
```

## Consequences

- ✅ Zero crashes during slot swaps
- ✅ Operations resume automatically after swap
- ✅ Webhook retries cover any missed operations
- ⚠️ Brief window where some operations are skipped
- ⚠️ More defensive code patterns needed

## Related

- [ADR-0020: Blue-Green Deployments](0020-blue-green-deployments.md)
- [ADR-0025: Staging Slot Settings Sync](0025-staging-slot-settings-sync.md)
- Commit: `66190c1 fix: add slot swap resilience for AzureWebJobsStorage`
