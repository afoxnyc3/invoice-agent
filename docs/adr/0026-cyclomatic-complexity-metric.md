# ADR-0026: Cyclomatic Complexity Metric

**Date:** 2024-11
**Status:** Accepted
**Supersedes:** [ADR-0008](0008-function-line-limit.md)

## Context

The 25-line function limit (ADR-0008) proved too arbitrary. Some 30-line functions were simple and readable; some 15-line functions were complex and hard to follow. Line count doesn't measure actual complexity.

## Decision

Use cyclomatic complexity (max 10) as the primary code complexity metric instead of line count.

## Rationale

- Measures actual decision points, not arbitrary line counts
- Research-backed threshold (McCabe's original recommendation)
- Enforceable via flake8 in CI
- More meaningful for code review
- Allows reasonable orchestration functions

## Complexity Guidelines

| Complexity | Assessment | Action |
|------------|------------|--------|
| 1-3 | Ideal | Most functions should be here |
| 4-7 | Acceptable | Moderate complexity, OK |
| 8-10 | Review | Consider refactoring |
| >10 | Must refactor | Blocked in CI |

## Implementation

- `.github/workflows/ci-cd.yml`: `flake8 --max-complexity=10`
- Line count remains as soft guidance (25 typical, 50 for orchestration)

## Consequences

- ✅ More meaningful complexity measurement
- ✅ Enforceable in CI
- ✅ Allows reasonable orchestration functions
- ⚠️ Developers need to understand cyclomatic complexity
- ⚠️ Some refactoring needed for existing code

## Related

- **Supersedes:** [ADR-0008: 25-Line Function Limit](0008-function-line-limit.md)
- See `CLAUDE.md` for complexity guidelines
