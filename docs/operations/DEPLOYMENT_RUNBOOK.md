# Deployment Runbook

**Last Updated:** November 13, 2025

Step-by-step production deployment checklist for Invoice Agent. This runbook provides exact commands and decision points for safely deploying to production.

## Table of Contents
- [Pre-Deployment Checklist](#pre-deployment-checklist)
- [Deployment Steps](#deployment-steps)
- [Post-Deployment Validation](#post-deployment-validation)
- [Rollback Decision Tree](#rollback-decision-tree)
- [Deployment Timing](#deployment-timing)

---

## Pre-Deployment Checklist

### 24 Hours Before Deployment

- [ ] **Verify all tests pass locally**
  ```bash
  cd /path/to/invoice-agent
  make test  # Should show 100% pass rate, >60% coverage
  ```

- [ ] **Run security and linting checks**
  ```bash
  make lint      # Black, Flake8, mypy
  make security  # Bandit scan
  ```

- [ ] **Check Azure subscription and permissions**
  ```bash
  az account show
  az functionapp list --resource-group rg-invoice-agent-prod
  ```

- [ ] **Verify staging slot exists and is clean**
  ```bash
  az functionapp deployment slot list \
    --name func-invoice-agent-prod \
    --resource-group rg-invoice-agent-prod
  ```

- [ ] **Backup current vendor data**
  ```bash
  az storage table download \
    --account-name stinvoiceagentprod \
    --name VendorMaster \
    --file vendor_backup_$(date +%Y%m%d_%H%M%S).csv
  ```

### 2 Hours Before Deployment

- [ ] **Notify on-call team** (via Slack/Teams channel)
- [ ] **Schedule deployment window** (off-peak hours recommended)
- [ ] **Assign deployment lead and observer**
- [ ] **Prepare rollback contacts** (availability confirmed)
- [ ] **Take screenshot of current Application Insights dashboard**

---

## Deployment Steps

### Step 1: Prepare Deployment Artifacts

```bash
# Navigate to project root
cd /path/to/invoice-agent

# Verify you're on main branch
git status
git log --oneline -1  # Confirm the commit being deployed

# Create deployment tag
git tag -a "deploy-prod-$(date +%Y%m%d-%H%M%S)" \
  -m "Production deployment $(date)"
```

### Step 2: Build and Package Functions

```bash
# Activate virtual environment
source src/venv/bin/activate

# Install dependencies (fresh install)
cd src
pip install -r requirements.txt

# Run comprehensive tests
cd ..
export PYTHONPATH=./src
pytest tests/unit tests/integration -v --cov=functions --cov=shared

# Verify coverage threshold
pytest --cov=functions --cov=shared --cov-report=term-only | grep -E "TOTAL|coverage"
```

**Expected Output:**
```
TOTAL                    2847     981      65%  # Must be ≥60%
```

### Step 3: Verify Staging Slot Configuration

```bash
# Get staging slot settings
az functionapp config appsettings list \
  --name func-invoice-agent-prod \
  --slot staging \
  --resource-group rg-invoice-agent-prod

# Verify critical settings exist
# Should see: AzureWebJobsStorage, INVOICE_MAILBOX, TEAMS_WEBHOOK_URL, etc.
```

### Step 4: Deploy to Staging Slot

```bash
# Build the function package
cd src
func azure functionapp publish func-invoice-agent-prod \
  --slot staging \
  --python \
  --remote-build

# Wait for deployment to complete (3-5 minutes)
# You should see: "Remote build succeeded"
```

### Step 5: Run Smoke Tests on Staging

```bash
# Get staging function app URL
STAGING_URL=$(az functionapp show \
  --name func-invoice-agent-prod \
  --slot staging \
  --resource-group rg-invoice-agent-prod \
  --query "hostNames[0]" -o tsv)

# Test AddVendor endpoint (basic health check)
curl -X POST https://$STAGING_URL/api/AddVendor \
  -H "Content-Type: application/json" \
  -d '{
    "vendor_name": "Test Vendor",
    "vendor_domain": "test.example.com",
    "expense_dept": "IT",
    "gl_code": "9999",
    "allocation_schedule": "MONTHLY",
    "billing_party": "Test"
  }'

# Expected response: 201 Created with vendor name
```

### Step 6: Monitor Staging for 5 Minutes

```bash
# Monitor staging logs
az functionapp log tail \
  --name func-invoice-agent-prod \
  --slot staging \
  --resource-group rg-invoice-agent-prod

# Check for errors: Look for ERROR level logs (should see none)
# Ctrl+C after 5 minutes of monitoring
```

### Step 7: Perform Slot Swap to Production

```bash
# Perform the swap (30 seconds, nearly instant)
az functionapp deployment slot swap \
  --name func-invoice-agent-prod \
  --slot staging \
  --resource-group rg-invoice-agent-prod

# Verify swap completed
az functionapp show \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "state"  # Should be "Running"
```

---

## Post-Deployment Validation

### Immediate Validation (0-5 minutes)

```bash
# Get production function URL
PROD_URL=$(az functionapp show \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "hostNames[0]" -o tsv)

# 1. Test AddVendor endpoint
curl -X POST https://$PROD_URL/api/AddVendor \
  -H "Content-Type: application/json" \
  -d '{
    "vendor_name": "Post-Deploy Test",
    "vendor_domain": "deploy-test.example.com",
    "expense_dept": "IT",
    "gl_code": "8888",
    "allocation_schedule": "MONTHLY",
    "billing_party": "Test"
  }'

# 2. Check Application Insights for errors
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "exceptions | where timestamp > ago(5m)" \
  --resource-group rg-invoice-agent-prod

# 3. Verify function app is running
az functionapp show \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "{State:state, DefaultHostName:defaultHostName}"
```

### Extended Validation (5-30 minutes)

```bash
# Monitor logs for 10 minutes
az functionapp log tail \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod

# Expected: No ERROR logs, normal INFO logs appearing
# Each function should log successfully at least once if running
```

### Health Check Metrics

Check these in Azure Portal or via CLI:

| Metric | Expected | Command |
|--------|----------|---------|
| HTTP Success Rate | >99% | `az monitor metrics list --resource /subscriptions/.../func-invoice-agent-prod` |
| Function Invocations | >0 | Application Insights → Functions → Invocations |
| Error Rate | 0% | Application Insights → Exceptions |
| Average Duration | <2000ms | Application Insights → Performance |

---

## Rollback Decision Tree

### Decision Point: Did deployment succeed?

**❌ NO - Function App Status is "Stopped" or "Unknown"**
- → Execute **Quick Rollback** (30 seconds)
- Command: See [Rollback Procedure](../ROLLBACK_PROCEDURE.md)

**❌ NO - AddVendor endpoint returns 500 errors**
- → Check logs for specific error
- If deployment code issue: **Quick Rollback**
- If configuration issue: **Fix Forward** (faster than rollback)

**❌ NO - Application Insights shows >5% error rate**
- → Investigate error details for 2 minutes
- If critical (data corruption, auth failure): **Quick Rollback**
- If fixable (missing env var): **Fix Forward**

**✅ YES - All checks pass, no errors in logs**
- → Proceed to verification phase
- Monitor continuously for 30 minutes
- If issues emerge: **Quick Rollback** within first hour

### Rollback Command (If Needed)

```bash
# Reverse the slot swap (30 seconds)
az functionapp deployment slot swap \
  --name func-invoice-agent-prod \
  --slot staging \
  --resource-group rg-invoice-agent-prod \
  --action swap  # Swaps again, reverting to old version

# Verify rollback
az functionapp show \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod
```

---

## Deployment Timing

### Recommended Windows

**Best Times (off-peak):**
- Tuesday - Thursday: 2:00 AM - 6:00 AM (Eastern)
- Rationale: Post-weekend, pre-Friday deployments; minimal invoice processing

**Acceptable Times:**
- Early morning (6:00 AM - 9:00 AM): Monitoring available
- Evening (7:00 PM - 10:00 PM): After business hours

**Avoid:**
- Monday mornings: Weekend backlog of invoices likely
- Friday afternoons: Risk vs. weekend support coverage
- End of month: Peak invoice volume

### Deployment Duration

| Phase | Duration | Window Needed |
|-------|----------|---------------|
| Pre-deployment checks | 10 min | 10 min |
| Build & test | 5 min | 5 min |
| Deploy to staging | 5 min | 5 min |
| Smoke tests & monitoring | 5 min | 5 min |
| Slot swap | 1 min | 1 min |
| Post-deploy validation | 5 min | 5 min |
| **Total** | **31 min** | **30 min** |

**Plan for:** 45 minutes (includes buffer for troubleshooting)

---

## Deployment Checklist Summary

```bash
# Quick reference - paste into chat during deployment
PRE:     [ ] Tests pass [ ] Lint passes [ ] Backup taken [ ] Team notified
BUILD:   [ ] Package built [ ] Tests re-run [ ] Staging ready
STAGING: [ ] Deployed [ ] Smoke tested [ ] 5-min monitoring OK
SWAP:    [ ] Slot swap executed [ ] Production running
POST:    [ ] Errors checked [ ] AddVendor tested [ ] 10-min logs clean
```

---

## Common Issues & Quick Fixes

| Issue | Symptom | Fix |
|-------|---------|-----|
| Staging deployment fails | "Remote build failed" | Check Python version: `python --version` |
| AddVendor returns 500 | "Internal server error" | Check env vars: `az functionapp config appsettings list ...` |
| Slot swap fails | "Swap operation failed" | Ensure staging slot exists and has latest code |
| High error rate post-deploy | >5% errors in logs | Check Application Insights for exception details |

---

## Post-Deployment Communication

After successful deployment, post to team channel:

```
Deployment Complete ✅

Deployed: [commit hash]
Time: [HH:MM UTC]
Duration: [X minutes]
Status: [Success/Rollback]

Health Checks:
✅ Function App running
✅ AddVendor responding
✅ Error rate: <1%
✅ No critical logs

Deployed by: [your name]
```

---

**Next Steps:** See [Operations Playbook](OPERATIONS_PLAYBOOK.md) for ongoing monitoring and maintenance.
