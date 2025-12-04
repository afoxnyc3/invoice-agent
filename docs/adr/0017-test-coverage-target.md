# ADR-0017: Test Coverage Target

**Date:** 2024-11-09
**Status:** Superseded by [ADR-0024](0024-test-coverage-enforcement.md)

## Context

Need testing requirements for MVP. Balance between thorough testing and delivery speed.

## Decision

Require 60% code coverage minimum for MVP.

## Rationale

- Balances quality with speed
- Focus on critical paths
- Can increase post-MVP
- Achievable in 2-week timeline

## Consequences

- ✅ Faster delivery
- ✅ Core functionality tested
- ⚠️ Some edge cases untested
- ⚠️ Technical debt for later

## Related

- **Superseded by:** [ADR-0024: 85% Test Coverage Enforcement](0024-test-coverage-enforcement.md)
- Coverage increased to 85% post-MVP
