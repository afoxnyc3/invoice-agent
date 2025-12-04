# ADR-0014: Single Region Deployment

**Date:** 2024-11-09
**Status:** Accepted

## Context

Need to decide on geographic redundancy for the system. Options were single region, active-passive, or active-active multi-region.

## Decision

Deploy to single region (East US) for MVP.

## Rationale

- All users in same timezone
- Simplifies deployment
- Cost savings (50% less infrastructure)
- Can add DR region later if needed

## Consequences

- ✅ Simpler architecture
- ✅ Lower costs
- ⚠️ No geographic redundancy
- ⚠️ Single point of failure for region outages

## Related

- [ADR-0013: Consumption Plan](0013-consumption-plan.md)
- See `infrastructure/parameters/` for region configuration
