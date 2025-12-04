# ADR-0025: Staging Slot Settings Sync

**Date:** 2024-11
**Status:** Accepted

## Context

Bicep deployment copies initial app settings to staging slot, but subsequent changes to production settings don't automatically replicate. This caused "undefined" errors when staging slot had stale or missing configuration.

## Decision

Manually sync app settings from production to staging before each deployment cycle.

## Rationale

- Bicep doesn't support automatic sync
- Staging must match production for valid smoke tests
- Prevents "undefined" errors during slot swap
- Documented process is better than failing silently

## Implementation

```bash
# Get production settings
az functionapp config appsettings list \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --output json > /tmp/prod-settings.json

# Apply to staging slot
az functionapp config appsettings set \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --slot staging \
  --settings @/tmp/prod-settings.json
```

## Consequences

- ✅ Staging accurately reflects production
- ✅ Smoke tests are valid
- ✅ Prevents configuration drift
- ⚠️ Manual step in deployment process
- ⚠️ Easy to forget (documented in runbook)

## Related

- [ADR-0020: Blue-Green Deployments](0020-blue-green-deployments.md)
- [ADR-0023: Slot Swap Resilience](0023-slot-swap-resilience.md)
- See `docs/DEPLOYMENT_GUIDE.md` Step 2.5
