# ADR-0016: Bicep over Terraform

**Date:** 2024-11-09
**Status:** Accepted

## Context

Need Infrastructure as Code tooling for Azure resources. Options were Bicep (Azure-native), Terraform (multi-cloud), or ARM templates (legacy).

## Decision

Use Bicep for all Azure infrastructure.

## Rationale

- Azure-native (first-party support)
- Cleaner syntax than ARM templates
- Better IntelliSense in VS Code
- No state file management
- Simpler than Terraform for Azure-only

## Consequences

- ✅ Native Azure support
- ✅ Simpler than ARM templates
- ⚠️ Azure-only (not multi-cloud)
- ⚠️ Smaller community than Terraform

## Related

- [ADR-0029: Modular Bicep Architecture](0029-modular-bicep-architecture.md)
- See `infrastructure/bicep/` for templates
