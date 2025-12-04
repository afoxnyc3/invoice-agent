# ADR-0009: Python 3.11 Runtime

**Date:** 2024-11-09
**Status:** Accepted

## Context

Need to choose Function App runtime. Team has Python expertise and the ecosystem has strong Azure SDK support.

## Decision

Use Python 3.11 on Linux for all Azure Functions.

## Rationale

- Team expertise in Python
- Excellent Azure SDK support
- Rich ecosystem for data processing
- Latest stable version at time of decision
- Linux for better performance

## Consequences

- ✅ Familiar to team
- ✅ Fast development
- ✅ Good library support
- ⚠️ Cold start slightly slower than .NET

## Related

- [ADR-0001: Serverless Azure Functions](0001-serverless-azure-functions.md)
- See `requirements.txt` for dependencies
