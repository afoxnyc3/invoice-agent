# ADR-0010: Managed Identity for All Auth

**Date:** 2024-11-09
**Status:** Accepted

## Context

Need authentication strategy for accessing Azure resources (Key Vault, Storage, Graph API). Options were service principals with secrets, certificates, or managed identity.

## Decision

Use Managed Identity everywhere possible for Azure resource authentication.

## Rationale

- No secrets in code
- Automatic credential rotation
- Azure-native security
- Simplified operations
- RBAC-based access control

## Consequences

- ✅ Enhanced security
- ✅ No password management
- ⚠️ Local development complexity (requires azurite or connection strings)
- ⚠️ Requires RBAC setup for each resource

## Related

- [ADR-0006: Graph API for Email Operations](0006-graph-api-for-email.md)
- See `infrastructure/bicep/` for RBAC assignments
