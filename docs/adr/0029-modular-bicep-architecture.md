# ADR-0029: Modular Bicep Architecture

**Date:** 2024-11
**Status:** Accepted

## Context

Infrastructure code was growing complex. Single-file Bicep templates became hard to maintain and review. Needed separation of concerns for different Azure resources.

## Decision

Use modular Bicep templates with separate files for each resource type.

## Rationale

- Separation of concerns
- Easier to review changes
- Reusable modules across environments
- Clearer dependencies
- Better IntelliSense support

## Directory Structure

```
infrastructure/bicep/
├── main.bicep           # Orchestrator
├── modules/
│   ├── storage.bicep    # Storage account + containers
│   ├── keyvault.bicep   # Key Vault + secrets
│   ├── functionapp.bicep # Function App + slots
│   ├── monitoring.bicep  # App Insights + Log Analytics
│   └── identity.bicep    # Managed identity + RBAC
└── parameters/
    ├── dev.json
    └── prod.json
```

## Consequences

- ✅ Cleaner code organization
- ✅ Easier to modify individual resources
- ✅ Better code review experience
- ⚠️ More files to manage
- ⚠️ Must understand module dependencies

## Related

- [ADR-0016: Bicep over Terraform](0016-bicep-over-terraform.md)
- [ADR-0031: AZQR Security Recommendations](0031-azqr-security-recommendations.md)
- See `infrastructure/bicep/` for templates
