# ADR-0008: 25-Line Function Limit

**Date:** 2024-11-09
**Status:** Superseded by [ADR-0026](0026-cyclomatic-complexity-metric.md)

## Context

Need code quality standards for maintainability. Team wanted objective, enforceable limits on function size.

## Decision

Enforce maximum 25 lines per function as a team coding standard.

## Rationale

- Forces single responsibility
- Improves testability
- Easier code reviews
- Team coding standard

## Consequences

- ✅ More maintainable code
- ✅ Better test coverage
- ⚠️ More helper functions
- ⚠️ Potential over-abstraction

## Related

- **Superseded by:** [ADR-0026: Cyclomatic Complexity Metric](0026-cyclomatic-complexity-metric.md)
- Line count proved too arbitrary; cyclomatic complexity better measures actual complexity
