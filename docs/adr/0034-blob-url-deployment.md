# ADR-0034: Replace Slot Swap with Direct Blob URL Deployment

## Status

Accepted

## Date

2025-12-06

## Context

The Invoice Agent uses Azure Functions on a Linux Consumption plan. The previous CI/CD pipeline used a staging slot + slot swap deployment pattern with `WEBSITE_RUN_FROM_PACKAGE=1`.

### The Problem

After slot swaps, production functions would fail to load:
- Health endpoint returns 404
- Azure portal shows "0 functions loaded"
- Restarts don't resolve the issue

### Root Cause

When `WEBSITE_RUN_FROM_PACKAGE=1` is set:
1. Azure Functions runtime looks for deployment metadata in `/home/data/SitePackages/`
2. This metadata points to the actual package location
3. During slot swap, app settings swap correctly, but the package metadata doesn't align
4. The `=1` convention is Azure-specific shorthand that breaks in edge cases on Linux Consumption

### Evidence

- Issue occurs consistently after every CI/CD slot swap
- Staging smoke tests pass, but production fails after swap
- Only manual deployment using explicit blob URL resolves the issue
- This is a known limitation of Linux Consumption plans

## Decision

Replace the staging + slot swap deployment pattern with direct blob URL deployment to production:

1. **Remove** the staging slot deployment job
2. **Remove** the slot swap to production job
3. **Remove** the automatic rollback job (no longer applicable)
4. **Add** direct deployment using explicit blob URL:
   - Upload package to blob storage with git SHA in filename
   - Generate 1-year SAS URL
   - Set `WEBSITE_RUN_FROM_PACKAGE` to the explicit URL
   - Restart function app
   - Verify health and function count

### New Deployment Flow

```
Test → Build → Upload to Blob → Generate SAS → Update App Setting → Restart → Health Check → Tag Release
```

### Rollback Procedure

Without slot swap, rollback is performed by:
```bash
# List available packages
az storage blob list --container-name function-releases --query "[].name" -o tsv

# Generate SAS for previous version
az storage blob generate-sas --name "function-app-<prev-sha>.zip" ...

# Update app setting and restart
az functionapp config appsettings set --settings "WEBSITE_RUN_FROM_PACKAGE=<sas-url>"
az functionapp restart --name func-invoice-agent-prod
```

## Consequences

### Positive

- **Reliability**: Explicit blob URLs always work; no metadata synchronization issues
- **Simplicity**: Reduced CI/CD complexity (eliminated 370+ lines of YAML)
- **Versioning**: Each deployment creates a version-tagged package (`function-app-{sha}.zip`)
- **Auditability**: Clear record of all deployed packages in blob storage
- **Cost**: No change (same storage, same compute)

### Negative

- **Deployment time**: Slightly longer (~90s vs ~60s for slot swap)
- **Instant rollback**: Lost instant rollback capability of slot swap (now requires manual steps)
- **Staging testing**: Lost automated staging smoke tests (can be added back if needed)
- **SAS management**: SAS URLs expire after 1 year; need monitoring/rotation

### Neutral

- **Blob cleanup**: Old packages accumulate; recommend periodic cleanup (keep last 10-20)
- **Service principal**: Requires Storage Blob Data Contributor role (already configured)

## Alternatives Considered

### Option B: Keep Staging for Smoke Tests
- Deploy to both staging and production using blob URL
- Run smoke tests against staging before production
- Rejected: Added complexity for marginal benefit; tests run in CI anyway

### Option C: Hybrid (Blob URL + Slot Swap)
- Use blob URLs but keep slot swap for rollback
- Rejected: Doesn't solve the root cause; slot swap itself is problematic

### Option D: Switch to Windows Consumption
- Slot swaps work more reliably on Windows
- Rejected: Migration effort, potential performance differences

### Option E: Switch to Premium Plan (EP1)
- More reliable deployment, VNET integration
- Rejected: Cost increase (~$150/month vs ~$2/month)

## Related ADRs

- ADR-0012: Deployment Slots for Zero-Downtime (superseded by this ADR)
- ADR-0023: CI/CD Pipeline Structure

## References

- [Azure Functions deployment best practices](https://docs.microsoft.com/en-us/azure/azure-functions/functions-deployment-technologies)
- [Run from package documentation](https://docs.microsoft.com/en-us/azure/azure-functions/run-functions-from-deployment-package)
- [Known issues with Linux Consumption](https://github.com/Azure/azure-functions-host/issues)
