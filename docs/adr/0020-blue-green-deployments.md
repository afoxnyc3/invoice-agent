# ADR-0020: Blue-Green Deployments

**Date:** 2024-11-09
**Status:** Accepted

## Context

Need deployment strategy for zero-downtime updates. Options were direct deployment, rolling updates, or blue-green (slot swapping).

## Decision

Use slot swapping for zero-downtime blue-green deployments.

## Rationale

- Zero-downtime deployments
- Easy rollback (swap back)
- Built into Azure Functions
- Production safety

## Consequences

- ✅ Safe deployments
- ✅ Quick rollback (<30 seconds)
- ⚠️ Slightly complex setup (staging slot configuration)
- ⚠️ Double resource cost during deployment

## Related

- [ADR-0023: Slot Swap Resilience](0023-slot-swap-resilience.md)
- [ADR-0025: Staging Slot Settings Sync](0025-staging-slot-settings-sync.md)
- See `.github/workflows/ci-cd.yml` for slot swap implementation
