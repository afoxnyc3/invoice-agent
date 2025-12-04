# ADR-0018: GitHub Actions for CI/CD

**Date:** 2024-11-09
**Status:** Accepted

## Context

Need CI/CD platform for automated testing and deployment. Options were GitHub Actions, Azure DevOps, or Jenkins.

## Decision

Use GitHub Actions for all CI/CD pipelines.

## Rationale

- Already using GitHub for source control
- Good Azure integration via actions
- Free for our usage tier
- YAML-based configuration
- Built-in secret management

## Consequences

- ✅ Integrated with repository
- ✅ No additional tools needed
- ✅ Good Azure support
- ⚠️ Vendor lock-in to GitHub

## Related

- [ADR-0020: Blue-Green Deployments](0020-blue-green-deployments.md)
- See `.github/workflows/ci-cd.yml` for pipeline
