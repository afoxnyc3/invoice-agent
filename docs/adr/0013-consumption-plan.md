# ADR-0013: Consumption Plan over Premium/Dedicated

**Date:** 2024-11-09
**Status:** Accepted

## Context

After deciding on Azure Functions (ADR-0001), we needed to choose the hosting plan. Options were Consumption (pay-per-execution), Premium (pre-warmed instances), or Dedicated (App Service plan).

## Decision

Use the Consumption plan for all Azure Functions.

## Rationale

- Variable workload (5-50 invoices/day) makes pay-per-execution ideal
- Zero cost during idle periods (nights, weekends)
- Auto-scaling 0-200 instances handled by platform
- Simpler to manage than Premium or Dedicated plans
- Sufficient for our latency requirements (cold start acceptable)

## Consequences

- ✅ Lowest cost for sporadic workloads (~$0/month at low volumes)
- ✅ No capacity planning required
- ✅ Automatic scale-out for burst processing
- ⚠️ Cold start latency (2-4 seconds on first invocation)
- ⚠️ 5-minute execution timeout per invocation
- ⚠️ No VNet integration without Premium plan (see issue #72)

## Related

- [ADR-0001: Serverless Azure Functions](0001-serverless-azure-functions.md)
- [ADR-0014: Single Region Deployment](0014-single-region-deployment.md)
- [ADR-0020: Blue-Green Deployments](0020-blue-green-deployments.md) (Superseded by ADR-0034)
