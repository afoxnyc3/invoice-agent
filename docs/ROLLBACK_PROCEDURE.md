# Rollback Procedure

This document provides step-by-step procedures for rolling back failed deployments of the Invoice Agent Azure Functions application.

## Table of Contents
- [When to Rollback](#when-to-rollback)
- [Rollback Methods](#rollback-methods)
- [Quick Rollback (Slot Swap Reversal)](#quick-rollback-slot-swap-reversal)
- [Rollback to Previous Version](#rollback-to-previous-version)
- [Infrastructure Rollback](#infrastructure-rollback)
- [Post-Rollback Verification](#post-rollback-verification)
- [Incident Documentation](#incident-documentation)
- [Prevention Measures](#prevention-measures)

## When to Rollback

Initiate a rollback immediately if you observe:

### Critical Issues (Immediate Rollback Required)
- **Function App crashes** or fails to start
- **HTTP 500 errors** on 50%+ of requests
- **Data corruption** or loss detected
- **Security vulnerability** introduced
- **Authentication failures** preventing operation
- **Critical business function broken** (invoice processing stopped)

### Warning Signs (Investigate Before Rollback)
- **Increased error rate** (2-5% errors)
- **Performance degradation** (>10% slower response times)
- **Intermittent failures** in specific functions
- **Increased cold start times** (>5 seconds)
- **Warning messages** in Application Insights

### Non-Critical Issues (Fix Forward)
- **Minor UI issues** in Teams notifications
- **Non-blocking warnings** in logs
- **Performance improvements** not materializing
- **Feature not working as expected** but not breaking existing functionality

**Decision Rule:** When in doubt, rollback. It's faster to rollback and fix forward than to debug a broken production system.

## Rollback Methods

Three rollback strategies, ordered by speed:

| Method | Speed | Use Case | Downtime |
|--------|-------|----------|----------|
| Slot Swap Reversal | 30 seconds | Recent deployment (within 24 hours) | <1 minute |
| Redeploy Previous Version | 3-5 minutes | Older deployment, staging slot overwritten | 2-3 minutes |
| Infrastructure Rollback | 10-15 minutes | Infrastructure change caused issue | 5-10 minutes |

## Quick Rollback (Slot Swap Reversal)

**When to use:** Recent deployment (<24 hours ago), staging slot still contains previous version

**Time to complete:** 30 seconds

**Prerequisites:**
- Azure CLI installed and logged in
- Contributor access to resource group

### Step 1: Identify the Issue

```bash
# Check Function App status
az functionapp show \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "state"

# View recent errors in Application Insights
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "exceptions | where timestamp > ago(15m) | summarize count() by type" \
  --resource-group rg-invoice-agent-prod
```

### Step 2: Swap Production Back to Staging

This reverses the most recent slot swap:

```bash
# Swap production slot with staging (rollback)
az functionapp deployment slot swap \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --slot staging \
  --target-slot production

echo "Rollback swap initiated at $(date)"
```

**What happens:**
- Current production code (broken) moves to staging slot
- Previous production code (working) moves back to production slot
- Traffic immediately routes to the working version
- Downtime: <60 seconds during swap

### Step 3: Verify Rollback Success

```bash
# Wait for swap to complete
echo "Waiting 30 seconds for swap to complete..."
sleep 30

# Check production health
PROD_URL="https://func-invoice-agent-prod.azurewebsites.net"
HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${PROD_URL}/admin/host/status")

if [ "$HEALTH_STATUS" = "200" ] || [ "$HEALTH_STATUS" = "401" ]; then
  echo "SUCCESS: Production is responding (status: $HEALTH_STATUS)"
else
  echo "ERROR: Production health check failed (status: $HEALTH_STATUS)"
  echo "Escalate to senior engineer immediately"
fi

# Check error rate
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "requests | where timestamp > ago(5m) | summarize success_rate = 100.0 * countif(success == true) / count()" \
  --resource-group rg-invoice-agent-prod
```

### Step 4: Notify Stakeholders

```bash
# Send notification to Teams (manual)
echo "ROLLBACK COMPLETED: Production rolled back to previous version at $(date)"
echo "Reason: [Describe the issue]"
echo "Impact: [Describe user impact]"
echo "Next steps: [Root cause analysis, fix, redeploy]"
```

**Timeline:**
- Detection: 0 min
- Decision: 0-2 min
- Execution: 0.5 min
- Verification: 0.5 min
- **Total: 1-3 minutes**

## Rollback to Previous Version

**When to use:** Staging slot has been overwritten, need to rollback to a specific previous version

**Time to complete:** 3-5 minutes

**Prerequisites:**
- Git tag of previous production release
- Build artifact available in GitHub Actions

### Step 1: Identify Target Version

```bash
# List recent production release tags
git fetch --tags
git tag -l "prod-*" | sort -r | head -5

# Or check GitHub Actions for successful deployments
# Navigate to: https://github.com/YOUR_ORG/invoice-agent/actions
# Find the last successful production deployment
```

### Step 2: Download Previous Build Artifact

**Option A: From GitHub Actions**
1. Go to **Actions** tab
2. Find the successful workflow run for target version
3. Download `function-app-package` artifact
4. Unzip locally

**Option B: Rebuild from Git Tag**
```bash
# Checkout the target version
git checkout prod-20241109-143022

# Rebuild
cd src
pip install -r requirements.txt --target ".python_packages/lib/site-packages"
zip -r ../function-app-rollback.zip .
cd ..
```

### Step 3: Deploy to Staging First

```bash
# Deploy to staging slot for testing
az functionapp deployment source config-zip \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --src function-app-rollback.zip \
  --slot staging

echo "Deployed to staging at $(date)"
```

### Step 4: Test Staging

```bash
# Wait for deployment
sleep 30

# Run smoke tests
STAGING_URL="https://func-invoice-agent-prod-staging.azurewebsites.net"
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" "${STAGING_URL}/admin/host/status")

if [ "$HEALTH" = "200" ] || [ "$HEALTH" = "401" ]; then
  echo "PASS: Staging is healthy"
else
  echo "FAIL: Staging health check failed"
  exit 1
fi
```

### Step 5: Swap to Production

```bash
# Swap staging to production
az functionapp deployment slot swap \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --slot staging \
  --target-slot production

echo "Rollback swap completed at $(date)"
```

### Step 6: Verify and Monitor

```bash
# Verify production
sleep 30
PROD_URL="https://func-invoice-agent-prod.azurewebsites.net"
curl -s "${PROD_URL}/admin/host/status" | jq .

# Monitor for 15 minutes
echo "Monitoring production for 15 minutes..."
for i in {1..15}; do
  sleep 60
  ERROR_COUNT=$(az monitor app-insights query \
    --app ai-invoice-agent-prod \
    --analytics-query "exceptions | where timestamp > ago(1m) | count" \
    --resource-group rg-invoice-agent-prod \
    --query "tables[0].rows[0][0]" -o tsv)
  echo "Minute $i: $ERROR_COUNT errors"
done
```

**Timeline:**
- Identify version: 1-2 min
- Download/rebuild: 1-2 min
- Deploy to staging: 1 min
- Test staging: 0.5 min
- Swap to production: 0.5 min
- **Total: 3-5 minutes**

## Infrastructure Rollback

**When to use:** Infrastructure change (Bicep template) caused the issue

**Time to complete:** 10-15 minutes

**WARNING:** Infrastructure rollbacks are complex and may cause data loss. Consider fix-forward approach first.

### Step 1: Identify Infrastructure Change

```bash
# Review recent infrastructure deployments
az deployment group list \
  --resource-group rg-invoice-agent-prod \
  --query "[?properties.provisioningState=='Succeeded'].{name:name, timestamp:properties.timestamp}" \
  --output table

# Get specific deployment details
az deployment group show \
  --resource-group rg-invoice-agent-prod \
  --name [deployment-name] \
  --query "properties.parameters"
```

### Step 2: Checkout Previous Bicep Version

```bash
# Find the commit with working infrastructure
git log --oneline infrastructure/bicep/main.bicep | head -10

# Checkout previous version
git checkout [commit-hash] -- infrastructure/bicep/
```

### Step 3: Review Changes Before Deploying

```bash
# What-if analysis (dry run)
az deployment group what-if \
  --resource-group rg-invoice-agent-prod \
  --template-file infrastructure/bicep/main.bicep \
  --parameters infrastructure/parameters/prod.json

# Review carefully:
# - Resources to be deleted (MAY CAUSE DATA LOSS)
# - Resources to be modified
# - Check for any destructive changes
```

### Step 4: Deploy Previous Infrastructure

```bash
# Deploy previous infrastructure version
az deployment group create \
  --resource-group rg-invoice-agent-prod \
  --template-file infrastructure/bicep/main.bicep \
  --parameters infrastructure/parameters/prod.json \
  --mode Incremental

echo "Infrastructure rollback deployed at $(date)"
```

### Step 5: Redeploy Application Code

```bash
# Redeploy working application version to new infrastructure
az functionapp deployment source config-zip \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --src function-app-rollback.zip
```

### Step 6: Verify All Systems

```bash
# Check Function App
az functionapp show \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "{name:name, state:state, defaultHostName:defaultHostName}"

# Check Storage Account
STORAGE_NAME=$(az storage account list \
  --resource-group rg-invoice-agent-prod \
  --query "[0].name" -o tsv)
az storage account show --name $STORAGE_NAME --query "statusOfPrimary"

# Check Key Vault
KV_NAME=$(az keyvault list \
  --resource-group rg-invoice-agent-prod \
  --query "[0].name" -o tsv)
az keyvault secret list --vault-name $KV_NAME

# Check Table Storage (VendorMaster)
az storage table list \
  --account-name $STORAGE_NAME \
  --query "[?name=='VendorMaster']"
```

**Timeline:**
- Identify change: 2-3 min
- Checkout previous version: 1 min
- What-if analysis: 2 min
- Deploy infrastructure: 5-7 min
- Redeploy code: 2 min
- Verification: 2-3 min
- **Total: 10-15 minutes**

## Post-Rollback Verification

After any rollback, perform these checks:

### 1. System Health

```bash
# Check all critical components
./scripts/health-check.sh

# Or manually:
# - Function App responding
# - Storage accessible
# - Key Vault accessible
# - Queues functioning
# - Tables readable/writable
```

### 2. Business Function Test

Manually verify core functionality:
1. Send test invoice email to shared mailbox
2. Verify email is processed within 5 minutes
3. Check AP email received formatted invoice
4. Verify Teams notification sent
5. Check InvoiceTransactions table for entry

### 3. Monitor Key Metrics

```bash
# Monitor for 30 minutes post-rollback
watch -n 60 'az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "requests | where timestamp > ago(5m) | summarize requests=count(), errors=countif(success==false), avg_duration=avg(duration)" \
  --resource-group rg-invoice-agent-prod'
```

**Success Criteria:**
- Error rate <1%
- Average response time <2 seconds
- No critical errors in logs
- Business function working end-to-end

## Incident Documentation

After rollback is complete and verified, document the incident:

### Create Incident Report

Create file: `incidents/YYYY-MM-DD-deployment-rollback.md`

```markdown
# Incident Report: Production Rollback

**Date:** YYYY-MM-DD HH:MM UTC
**Severity:** [Critical/High/Medium]
**Duration:** [Time from issue detection to rollback completion]
**Impact:** [Describe user/business impact]

## Timeline
- HH:MM - Deployment initiated
- HH:MM - Issue detected
- HH:MM - Rollback decision made
- HH:MM - Rollback executed
- HH:MM - Systems verified
- HH:MM - Incident closed

## Root Cause
[Detailed explanation of what caused the failure]

## Rollback Method
[Which rollback procedure was used]

## Lessons Learned
- What went wrong?
- What could we have caught in testing?
- What should we add to smoke tests?
- What monitoring alerts should we add?

## Action Items
- [ ] Fix the root cause
- [ ] Add test coverage for the scenario
- [ ] Update smoke tests
- [ ] Add monitoring/alerting
- [ ] Update documentation
- [ ] Schedule blameless post-mortem
```

### Update Team

Send notification:
```text
Subject: [RESOLVED] Production Rollback - Invoice Agent

The production rollback initiated at [TIME] has been completed successfully.

Current Status: STABLE
Rollback Method: [Slot swap reversal / Version redeploy / Infrastructure rollback]
Root Cause: [Brief description]
Impact: [Number of affected invoices, duration of outage]

Next Steps:
1. Root cause analysis scheduled for [DATE/TIME]
2. Fix will be developed and tested in dev environment
3. Enhanced smoke tests will be added before next deployment

Incident report: incidents/YYYY-MM-DD-deployment-rollback.md

[Your Name]
[Date/Time]
```

## Prevention Measures

To reduce the need for rollbacks:

### 1. Enhanced Smoke Tests

Add more comprehensive staging tests in `.github/workflows/ci-cd.yml`:

```bash
# Test each function endpoint
# Test queue message processing
# Test Table Storage queries
# Test Key Vault secret retrieval
# Test Graph API connectivity
# Test Teams webhook
```

### 2. Gradual Rollout

For high-risk changes, consider gradual rollout:
- Deploy to staging
- Run extended smoke tests (15 minutes)
- Manual testing in staging
- Deploy to production
- Monitor for 15 minutes before declaring success

### 3. Feature Flags

For new features, use feature flags:
- Deploy code with feature disabled
- Enable in dev/staging first
- Gradual rollout to production (10%, 50%, 100%)
- Instant rollback by disabling flag (no deployment needed)

### 4. Automated Alerts

Set up Application Insights alerts:
- Error rate >1%
- Response time >5 seconds
- Function failures
- Queue depth growing
- Storage errors

### 5. Deployment Windows

Consider deployment windows:
- Deploy during low-traffic hours (evenings/weekends)
- Avoid month-end (high invoice volume)
- Avoid Monday mornings
- Have engineer on-call during deployment

### 6. Rollback Rehearsal

Practice rollback procedures quarterly:
- Deploy to dev environment
- Intentionally break it
- Execute rollback procedure
- Time the process
- Update documentation based on learnings

## Emergency Contacts

For critical production issues requiring rollback:

- **On-Call Engineer:** [Phone/Slack]
- **DevOps Lead:** [Phone/Slack]
- **Azure Support:** [Support ticket URL]
- **Escalation Path:** [Manager contact]

## Additional Resources

- [Deployment Guide](./DEPLOYMENT_GUIDE.md)
- [Azure Functions Deployment Slots](https://learn.microsoft.com/azure/azure-functions/functions-deployment-slots)
- [Application Insights Troubleshooting](https://learn.microsoft.com/azure/azure-monitor/app/troubleshoot-availability)
- [Project README](../README.md)

---

**Remember:** When in doubt, rollback. It's always faster to rollback and fix forward than to debug a broken production system with live traffic.
