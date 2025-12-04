# ADR-0001: Serverless Azure Functions over Container Apps

**Date:** 2024-11-09
**Status:** Accepted

## Context

Need to choose compute platform for invoice processing. The workload is variable (5-50 invoices/day) and requires integration with Azure Storage for queues and blobs.

## Decision

Use Azure Functions on Consumption plan for all processing functions.

## Rationale

- Variable workload (5-50 invoices/day) makes pay-per-execution ideal
- No idle costs during quiet periods
- Auto-scaling handled by platform
- Faster development with less infrastructure management
- Native integration with Azure Storage queues

## Consequences

- ✅ Cost-effective for sporadic workloads
- ✅ Zero maintenance of infrastructure
- ⚠️ Cold start latency (2-4 seconds)
- ⚠️ 5-minute execution timeout limit

## Related

- [ADR-0013: Consumption Plan](0013-consumption-plan.md)
- [ADR-0009: Python 3.11 Runtime](0009-python-311-runtime.md)
