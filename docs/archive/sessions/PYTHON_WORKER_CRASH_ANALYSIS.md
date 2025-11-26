# Python Worker Crash Analysis & Resolution Plan
**Date:** November 19, 2024
**Issue:** Production Azure Functions Python Worker Crash
**Status:** Root cause identified, fix plan developed

## Executive Summary

Critical production issue discovered where Python runtime worker crashes repeatedly on startup, preventing ANY functions from loading. This resulted in complete service outage - no email processing occurred.

## The Problem

### Error Messages from Production
```
"Exceeded language worker restart retry count for runtime:python. Shutting down and proactively recycling the Functions Host to recover"
"No job functions found."
"0 functions loaded"
```

### Impact
- ❌ MailIngest timer never fired
- ❌ No emails were picked up
- ❌ Test emails were NOT processed
- ❌ Complete service outage

## Root Cause Analysis

### PRIMARY CAUSE (85% Confidence): Python Version Mismatch

**Evidence Found:**
1. **Local Development:** Python 3.13.5
2. **CI/CD Pipeline:** Python 3.11 (configured correctly)
3. **Azure Runtime:** Python 3.11
4. **3,742 .pyc files** found in src/ directory (Python 3.13 bytecode)
5. **No .funcignore file** exists to exclude these files
6. **Binary dependencies** (grpcio, pydantic) are version-specific

### Why This Causes Crashes

When Azure Functions Python 3.11 worker tries to load Python 3.13 bytecode or binary extensions:
- Bytecode magic numbers don't match
- Binary ABI incompatibility
- Import errors cascade to worker crash
- Host retries 5 times then gives up

### Evidence Details

**Files Examined:**
- `/src/shared/__pycache__/*.cpython-313.pyc` - Python 3.13 bytecode files
- `/src/.python_packages/lib/site-packages/*.so` - Binary extensions for Python 3.11
- `/src/.funcignore` - MISSING (critical)
- `/.github/workflows/ci-cd.yml:149` - `zip -r ../function-app.zip .` (includes everything)

## Alternative Possibilities (Cannot Rule Out)

1. **Azure platform issue** (10% chance)
2. **Missing environment variables** (20% chance)
3. **Storage connection failure** (15% chance)
4. **Corrupted deployment package** (5% chance)
5. **Different dependency conflict** (10% chance)

## Fix Plan

### Phase 1: Immediate Critical Fixes

#### 1. Create .funcignore file (`/src/.funcignore`)
```
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
.venv/
venv/
ENV/
env/
.pytest_cache/
.mypy_cache/
tests/
.coverage
*.log
local.settings.json
.vscode/
.idea/
*.md
docs/
scripts/
infrastructure/
```

#### 2. Pin Exact Dependencies (`/src/requirements.txt`)
Change from:
```
grpcio>=1.60.0,<2.0.0
grpcio-tools>=1.60.0,<2.0.0
```
To:
```
grpcio==1.60.1
grpcio-tools==1.60.1
```

#### 3. Add Pure Python Mode (`/infrastructure/bicep/modules/functionapp.bicep`)
Add to app settings:
```bicep
{
  name: 'PYDANTIC_PURE_PYTHON'
  value: '1'
}
```

#### 4. Add Deployment Validation (`/.github/workflows/ci-cd.yml`)
Add after build step:
```yaml
- name: Validate deployment package
  working-directory: ./src
  run: |
    # Check Python version
    python --version

    # Test imports
    export PYTHONPATH=.:.python_packages/lib/site-packages
    python -c "
    import sys
    print(f'Python {sys.version}')

    # Test critical imports
    import azure.functions
    import shared.models
    from functions.MailIngest import main
    print('✅ All imports successful')
    "
```

### Phase 2: Deploy and Verify

5. **Trigger deployment** - Commit changes to trigger CI/CD
6. **Run diagnostics** - Verify functions loaded
7. **Seed vendor data** - Run seed_vendors.py
8. **End-to-end test** - Send test email and monitor

### Phase 3: Long-term Safeguards

9. **Configure alerts** - Worker crashes, execution counts
10. **Document incident** - Update postmortem docs

## Diagnostic Commands

### Quick Health Check
```bash
# Check if functions are loaded
az functionapp function list \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "[].name" --output table
```

### Get Error Details
```bash
# Query Application Insights for import errors
APP_INSIGHTS_NAME="ai-invoice-agent-prod"
az monitor app-insights query \
  --app $APP_INSIGHTS_NAME \
  --resource-group rg-invoice-agent-prod \
  --analytics-query "traces | where timestamp > ago(24h) | where message contains 'import' or message contains 'ModuleNotFoundError'" \
  --output table
```

### Check Deployment History
```bash
# See how it was deployed (GitHub vs local)
az functionapp deployment list \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "[0].{deployer:deployer, status:status, timestamp:received_time}" \
  --output table
```

### Full Diagnostic Script
```bash
#!/bin/bash
# Save as diagnose-production.sh

set -e

RG="rg-invoice-agent-prod"
FUNC_NAME="func-invoice-agent-prod"

echo "=== 1. Function App Status ==="
az functionapp show --name $FUNC_NAME --resource-group $RG \
  --query "{state:state, pythonVersion:siteConfig.pythonVersion}" --output table

echo -e "\n=== 2. Loaded Functions ==="
az functionapp function list --name $FUNC_NAME --resource-group $RG \
  --query "[].name" --output table

echo -e "\n=== 3. Last 5 Deployments ==="
az functionapp deployment list --name $FUNC_NAME --resource-group $RG \
  --query "reverse(sort_by([], &received_time))[0:5].{deployer:deployer, status:status, timestamp:received_time}" --output table

echo -e "\n=== 4. Critical App Settings ==="
az functionapp config appsettings list --name $FUNC_NAME --resource-group $RG \
  --query "[?name=='FUNCTIONS_WORKER_RUNTIME' || name=='APPLICATIONINSIGHTS_CONNECTION_STRING'].{name:name, value:value}" --output table

echo -e "\n=== 5. Application Insights Errors (Last 24h) ==="
APP_INSIGHTS=$(az resource list --resource-group $RG \
  --resource-type "Microsoft.Insights/components" --query "[0].name" --output tsv)

az monitor app-insights query --app $APP_INSIGHTS --resource-group $RG \
  --analytics-query "exceptions | where timestamp > ago(24h) | summarize count() by outerMessage | order by count_ desc" \
  --output table
```

## Confidence Assessment

- **Problem Identification:** 100% - Worker crash confirmed
- **Root Cause:** 85% - Python version mismatch most likely
- **Solution Effectiveness:** 90% - Plan addresses all known issues

**Missing Evidence for 100% Certainty:**
- Application Insights actual error logs
- Deployment method confirmation (CI/CD vs local)
- Kudu console file listing

## Rollback Plan

### Immediate (< 5 min)
```bash
# Swap staging slot back
az functionapp deployment slot swap \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --slot staging \
  --target-slot production \
  --action swap
```

### Emergency
```bash
# Disable all functions
az functionapp stop \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod
```

## Success Criteria

- ✅ All 5 functions show as loaded
- ✅ No worker crash errors in logs
- ✅ Test email processes successfully
- ✅ Error rate < 1%
- ✅ VendorMaster table seeded

## Long-term Recommendations

1. **Container Deployment** - Full control over Python environment
2. **Locked Requirements** - Use requirements-lock.txt
3. **Pre-deployment Testing** - Import validation in CI/CD
4. **Synthetic Monitoring** - Hourly test emails

## Next Session Actions

1. Run diagnostic commands to confirm root cause
2. Implement fixes in priority order
3. Deploy via CI/CD (uses correct Python version)
4. Verify functions load successfully
5. Seed vendor data
6. Run end-to-end test

---

**Note:** This analysis based on code inspection and error patterns. Running the diagnostic commands will provide definitive confirmation of root cause.