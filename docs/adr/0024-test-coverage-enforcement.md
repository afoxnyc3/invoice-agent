# ADR-0024: 85% Test Coverage Enforcement

**Date:** 2024-11
**Status:** Accepted
**Supersedes:** [ADR-0017](0017-test-coverage-target.md)

## Context

MVP shipped with 60% coverage target (ADR-0017). Post-MVP, we needed higher quality standards to prevent regressions and support the webhook migration.

## Decision

Increase minimum test coverage to 85% and enforce in CI/CD pipeline.

## Rationale

- Higher confidence in code changes
- Webhook migration required extensive testing
- Team now has capacity for quality
- 85% achievable without excessive mocking
- Balances coverage with maintainability

## Implementation

- `pytest.ini`: `--cov-fail-under=85`
- `.github/workflows/ci-cd.yml`: Coverage check in test job
- Current: 389 tests passing

## Consequences

- ✅ Higher confidence in deployments
- ✅ Catches regressions early
- ✅ Forces testable code design
- ⚠️ Slower feature development (more test writing)
- ⚠️ Some edge cases require creative testing

## Related

- **Supersedes:** [ADR-0017: 60% Test Coverage for MVP](0017-test-coverage-target.md)
- [ADR-0030: Azurite for Integration Tests](0030-azurite-integration-tests.md)
- See `pytest.ini` for configuration
