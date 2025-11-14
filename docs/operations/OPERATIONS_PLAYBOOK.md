# Operations Playbook

**Last Updated:** November 13, 2025

Daily, weekly, and monthly operational tasks for the Invoice Agent. This playbook ensures the system runs smoothly and potential issues are detected early.

## Table of Contents
- [Daily Operations](#daily-operations)
- [Weekly Reviews](#weekly-reviews)
- [Monthly Activities](#monthly-activities)
- [Quarterly Reviews](#quarterly-reviews)
- [Health Check Procedures](#health-check-procedures)
- [On-Call Responsibilities](#on-call-responsibilities)

---

## Daily Operations

### Morning Health Check (5 minutes)

**Time:** Start of business day (9:00 AM)
**Owner:** On-call engineer

**Checklist:**
```bash
# 1. Check function app status
az functionapp show \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "state"
# Expected: "Running"

# 2. Check error rate in last 2 hours
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "
    requests
    | where timestamp > ago(2h)
    | where success == false
    | summarize error_count = count()
  " \
  --resource-group rg-invoice-agent-prod
# Expected: <10 errors

# 3. Check queue depths (should be <100)
for q in raw-mail to-post notify; do
  count=$(az storage queue metadata show \
    --account-name stinvoiceagentprod \
    --name $q \
    --query "ApproximateMessageCount" -o tsv)
  echo "$q: $count messages"
done
# Expected: Each queue <100 messages

# 4. Check for any poison queue messages
az storage queue list \
  --account-name stinvoiceagentprod \
  --query "[?contains(name, 'poison')].name"
# Expected: Empty list or very few
```

**If Issues Found:**
- Error rate >10: Check [Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md)
- Queue depth >500: Investigate downstream function failures
- Poison messages: Review and reprocess per [Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md#poison-queue-processing)

**Action:** Document findings in #invoice-agent-status Slack channel

---

### Evening Review (10 minutes)

**Time:** End of business day (5:00 PM)
**Owner:** On-call engineer

**Checklist:**
```bash
# 1. Check daily error summary
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "
    requests
    | where timestamp > ago(24h)
    | summarize total = count(), errors = sumif(success == false) by name
  " \
  --resource-group rg-invoice-agent-prod

# 2. Monitor function invocation count
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "
    customMetrics
    | where name == 'MailIngest_InvocationCount'
    | where timestamp > ago(24h)
    | summarize total = sum(value)
  " \
  --resource-group rg-invoice-agent-prod
# Expected: >100 invoices processed

# 3. Check average response times
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "
    requests
    | where timestamp > ago(24h)
    | summarize avg_ms = avg(duration) by name
  " \
  --resource-group rg-invoice-agent-prod
# Expected: <2000ms average
```

**If Issues Found:**
- Low invocation count: May indicate email polling issue
- High response times: Check Azure subscription throttling
- Any errors: Create incident ticket

**Action:** Post daily summary to #invoice-agent-daily Slack channel

---

## Weekly Reviews

### Vendor Data Review (30 minutes)

**Day:** Monday morning
**Owner:** Ops team lead

**Purpose:** Ensure vendor data is current and identify gaps

**Procedure:**
```bash
# 1. Export current vendor list
az storage entity query \
  --account-name stinvoiceagentprod \
  --table-name VendorMaster \
  --select "RowKey,VendorName,ExpenseDept,GLCode,Active" > vendors_current_$(date +%Y%m%d).csv

# 2. Check for vendors marked as inactive
az storage entity query \
  --account-name stinvoiceagentprod \
  --table-name VendorMaster \
  --filter "Active eq false" \
  --select "RowKey,VendorName,UpdatedAt"
```

**Analysis:**
- Are there duplicate vendors with different domains?
- Are there vendors with outdated GL codes?
- Are there frequently used vendors not in the system?

**Actions:**
- Email: Ask Finance to review vendor list for accuracy
- Add: New vendors identified from invoice processing
- Update: Any vendors with changed GL codes
- Deactivate: Vendors no longer doing business with company

---

### Performance Review (20 minutes)

**Day:** Wednesday afternoon
**Owner:** DevOps engineer

**Metrics to Check:**
```bash
# 1. Throughput trend (last 7 days)
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "
    requests
    | where timestamp > ago(7d)
    | where name == 'PostToAP'  // Count successfully processed invoices
    | summarize count() by bin(timestamp, 1d)
  " \
  --resource-group rg-invoice-agent-prod

# 2. Error trend
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "
    requests
    | where timestamp > ago(7d)
    | where success == false
    | summarize count() by bin(timestamp, 1d)
  " \
  --resource-group rg-invoice-agent-prod

# 3. Cold start frequency
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "
    traces
    | where message contains 'Cold start'
    | where timestamp > ago(7d)
    | summarize count()
  " \
  --resource-group rg-invoice-agent-prod
```

**Analysis:**
- Is throughput consistent (100-200/day expected)?
- Is error rate <1%?
- Are cold starts frequent (>10/day might indicate scale issue)?

**Actions:**
- If throughput dropping: Check for business decline or system issues
- If errors increasing: Investigate root cause, create ticket
- If cold starts high: Consider Premium tier to keep functions warm

---

### Cost Review (15 minutes)

**Day:** Friday morning
**Owner:** Finance liaison

**Check Azure Bill:**
```bash
# View daily cost trend (last 7 days)
az costmanagement query \
  --timeframe WeekToDate \
  --dataset \
    name=Usage \
    aggregation={totalCost={name=PreTaxCost}} \
  --resource-group rg-invoice-agent-prod
```

**Cost Breakdown (Typical):**
- **Function Invocations:** 50% (~$20-30/month)
- **Storage (Tables + Blobs):** 30% (~$12-18/month)
- **Application Insights:** 15% (~$6-9/month)
- **Data Transfer:** 5% (~$2-3/month)

**Alerts:**
- Function costs spike: May indicate runaway processing or incorrect retry logic
- Storage costs increase: Check for blob storage growth (old invoices not cleaned)
- Transfer costs high: Review inter-region data movement

**Actions:**
- If costs up 25%+: Investigate cause, optimize if possible
- If storage quota exceeded: Implement archive/deletion policy

---

## Monthly Activities

### Vendor Data Cleanup (30 minutes)

**Day:** 1st of month
**Owner:** AP Operations team

**Procedure:**

1. **Identify Inactive Vendors**
   ```bash
   # Find vendors not used in last 30 days
   az monitor app-insights query \
     --app ai-invoice-agent-prod \
     --analytics-query "
       customEvents
       | where name == 'VendorMatched'
       | where timestamp > ago(30d)
       | distinct tostring(customDimensions.vendor_domain)
     " \
     --resource-group rg-invoice-agent-prod > active_vendors.txt

   # Compare with current vendor list to find inactive ones
   ```

2. **Review GL Code Accuracy**
   ```bash
   # Export vendor GL codes
   az storage entity query \
     --account-name stinvoiceagentprod \
     --table-name VendorMaster \
     --select "VendorName,GLCode" \
     --output table
   ```

3. **Coordinate with Finance**
   - Share active vendor list
   - Ask for validation of GL codes
   - Identify any vendors moved to different departments

4. **Update System**
   ```bash
   # For vendors with changed GL codes:
   curl -X POST https://func-invoice-agent-prod.azurewebsites.net/api/AddVendor \
     -H "Content-Type: application/json" \
     -d '{
       "vendor_name": "Adobe Inc",
       "vendor_domain": "adobe.com",
       "expense_dept": "MARKETING",  // Changed from IT
       "gl_code": "6300",
       "allocation_schedule": "MONTHLY",
       "billing_party": "Company HQ"
     }'
   ```

---

### Backup Verification (20 minutes)

**Day:** 2nd of month
**Owner:** Infrastructure team

**Procedure:**

```bash
# 1. Verify VendorMaster table backup exists
az storage blob list \
  --account-name stinvoiceagentprod \
  --container-name backups \
  --filter "VendorMaster*" | head -5

# 2. Verify InvoiceTransactions table is being archived
# Check if old records are moved to archive storage

# 3. Test restore procedure
# Take a vendor, verify it can be re-added without issues

# 4. Document backup location & access procedure
# Ensure new team members know where backups are stored
```

**Checklist:**
- [ ] VendorMaster backed up
- [ ] InvoiceTransactions archive active
- [ ] Backup retention policy confirmed (30+ days)
- [ ] DR contact list updated

---

### Security Review (30 minutes)

**Day:** 3rd of month
**Owner:** Security team

**Checklist:**

```bash
# 1. Check for any security warnings in Application Insights
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "
    traces
    | where severity >= 2  // WARNING or ERROR
    | where message contains ['security', 'auth', 'permission']
    | summarize count()
  " \
  --resource-group rg-invoice-agent-prod

# 2. Verify no secrets in logs
az monitor app-insights trace show \
  --app ai-invoice-agent-prod \
  --limit 100 | grep -i -E "password|secret|key|token"

# 3. Check function app HTTPS enforcement
az functionapp update \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --set httpsOnly=true

# 4. Review access logs
az monitor activity-log list \
  --resource-group rg-invoice-agent-prod \
  --start-time "$(date -d '30 days ago' -u +%Y-%m-%dT%H:%M:%SZ)" | grep -i "delete\|modify\|permission"
```

**Actions:**
- Verify MSAL certificates not expiring soon
- Confirm no hardcoded secrets in recent commits
- Review who has access to Function App, Storage Account

---

### Documentation Review (15 minutes)

**Day:** Last Friday of month
**Owner:** Tech lead

**Checklist:**
- [ ] Update CHANGELOG.md with any changes made this month
- [ ] Review README.md for accuracy
- [ ] Check all docs links are still valid
- [ ] Update "Last Updated" dates in all runbooks
- [ ] Verify troubleshooting guide reflects current errors
- [ ] Confirm architecture diagram matches current state

---

## Quarterly Reviews

### Performance Optimization Review (2 hours)

**Time:** Every 3 months
**Owner:** Performance engineer

**Analysis:**

1. **Throughput Trends**
   ```bash
   # Get 3-month trend data
   az monitor app-insights query \
     --app ai-invoice-agent-prod \
     --analytics-query "
       requests
       | where timestamp > ago(90d)
       | where name == 'PostToAP'
       | summarize count() by bin(timestamp, 7d)
     "
   ```

2. **Latency Distribution**
   ```bash
   # Get percentile data
   az monitor app-insights query \
     --app ai-invoice-agent-prod \
     --analytics-query "
       requests
       | where timestamp > ago(90d)
       | summarize p50 = percentile(duration, 50),
                   p95 = percentile(duration, 95),
                   p99 = percentile(duration, 99) by name
     "
   ```

3. **Resource Utilization**
   - Check CPU/Memory metrics
   - Review storage account throughput
   - Analyze Graph API call patterns

**Optimization Opportunities:**
- Caching vendor data in-memory?
- Batch processing emails?
- Parallel function processing?
- Upgrading to higher-tier App Service Plan?

---

### Security Audit (2 hours)

**Time:** Every 3 months
**Owner:** Security officer

**Full Audit Checklist:**

1. **Access Control Review**
   - Who has access to production resources?
   - Who has secrets in Key Vault?
   - Are service principals minimal-privilege?

2. **Dependency Scan**
   ```bash
   # Check for vulnerable packages
   cd src
   pip list --outdated
   ```

3. **Secrets Rotation**
   - Rotate storage account keys
   - Rotate service principal credentials
   - Rotate Teams webhook URLs (every 6 months)

4. **Network Review**
   - Is Function App restricted to internal IPs only? (if possible)
   - Are blob URLs time-limited (SAS tokens)?
   - Is Graph API access limited to required permissions?

---

### Vendor Data Audit (1 hour)

**Time:** Every 3 months
**Owner:** Finance team

**Procedure:**

1. **Completeness Check**
   ```bash
   # How many vendors do we have vs. active suppliers?
   VENDOR_COUNT=$(az storage entity query \
     --account-name stinvoiceagentprod \
     --table-name VendorMaster \
     --query "length(@)")
   echo "Total vendors: $VENDOR_COUNT"
   ```

2. **Accuracy Validation**
   - Spot-check 10 vendors for correct GL codes
   - Verify department allocations with Finance
   - Confirm billing parties are accurate

3. **Coverage Analysis**
   - What percentage of invoices matched known vendors?
   - Are there patterns in unknown vendors?
   - Should we add more vendors?

---

## Health Check Procedures

### Rapid Health Check (3 minutes)

Use when investigating potential issues:

```bash
#!/bin/bash
echo "=== Invoice Agent Health Check ==="

# Function App Status
STATUS=$(az functionapp show \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "state" -o tsv)
echo "Function App: $STATUS"

# Recent Error Count
ERRORS=$(az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "requests | where timestamp > ago(1h) and success == false | count" \
  --resource-group rg-invoice-agent-prod -o tsv | tail -1)
echo "Recent Errors (1h): $ERRORS"

# Queue Depths
for q in raw-mail to-post notify; do
  COUNT=$(az storage queue metadata show \
    --account-name stinvoiceagentprod \
    --name $q \
    --query "ApproximateMessageCount" -o tsv)
  echo "Queue [$q]: $COUNT"
done

echo "=== Health Check Complete ==="
```

---

### Deep Diagnostic Check (15 minutes)

For troubleshooting specific issues:

```bash
#!/bin/bash
# Run this when investigating problems

echo "=== Deep Diagnostic Check ==="

# Function logs from last hour
echo "--- Recent logs ---"
az functionapp log tail \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --timeout 30

# Exception summary
echo "--- Exceptions in last 2 hours ---"
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "
    exceptions
    | where timestamp > ago(2h)
    | summarize count() by type
  "

# Database connectivity
echo "--- Checking table access ---"
az storage entity query \
  --account-name stinvoiceagentprod \
  --table-name VendorMaster \
  --select "RowKey" \
  --limit 1

echo "=== Diagnostic Complete ==="
```

---

## On-Call Responsibilities

### Daily On-Call Duties

**Start of Shift:**
- [ ] Run Morning Health Check
- [ ] Review overnight alerts/logs
- [ ] Check Slack #invoice-agent-incidents for any ongoing issues
- [ ] Update status page if any known issues

**Throughout Shift:**
- [ ] Monitor #invoice-agent-alerts channel for automated alerts
- [ ] Respond to any escalations within 15 minutes
- [ ] Track any issues in incident management system
- [ ] Post any status updates to Slack #invoice-agent-status

**End of Shift:**
- [ ] Run Evening Review
- [ ] Hand off any open incidents to next on-call
- [ ] Document lessons learned in runbook if issues occurred
- [ ] Confirm next on-call engineer is ready

### Escalation Path

1. **Minor Issues (can resolve within 1 hour):**
   - Try remediation steps from [Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md)
   - Post in #invoice-agent-oncall channel

2. **Major Issues (error rate >5% or data issues):**
   - Page on-call engineer immediately
   - Post in #invoice-agent-incidents channel
   - Start incident in tracking system

3. **Critical Issues (data corruption, security breach):**
   - Page on-call lead + backup
   - Escalate to VP Engineering immediately
   - Consider rollback

---

**Next Steps:** See [Deployment Runbook](DEPLOYMENT_RUNBOOK.md) for deployment procedures.
