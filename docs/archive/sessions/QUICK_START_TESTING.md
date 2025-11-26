# Invoice Agent Testing & Observability - Quick Start

**Get started in 5 minutes**

## What You Just Received

Three comprehensive deliverables to ensure production excellence:

1. **Testing Runbook** - Complete testing procedures
2. **Automation Scripts** - 4 ready-to-run tools
3. **Observability Proposal** - Monitoring strategy

---

## Instant Value - Try These Now

### 1. Health Check (30 seconds)

```bash
cd /Users/alex/dev/invoice-agent/scripts/automation

# Make executable (first time only)
chmod +x health-check.sh

# Run health check
./health-check.sh --environment prod
```

**What it does:** Validates all 25+ checkpoints across your system
**Output:** Color-coded pass/fail report with overall health status
**Exit code:** 0=healthy, 1=degraded, 2=unhealthy

---

### 2. Collect Logs for Analysis (2 minutes)

```bash
cd /Users/alex/dev/invoice-agent/scripts/automation

# Make executable (first time only)
chmod +x collect-logs.sh

# Collect last 24 hours of logs
./collect-logs.sh --environment prod
```

**What it does:** Gathers all logs, metrics, and diagnostics
**Output:** Organized directory + compressed tarball
**Use case:** Incident investigation, performance analysis

**View results:**
```bash
# Navigate to output directory (shown in script output)
cd /tmp/invoice-agent-logs-prod-*

# View error summary
less 10-error-summary.txt

# View recent transactions
less 30-recent-transactions.txt
```

---

### 3. Validate Your Next Deployment (60 seconds)

```bash
cd /Users/alex/dev/invoice-agent/scripts/automation

# Make executable (first time only)
chmod +x validate-deployment.sh

# After deploying to staging
./validate-deployment.sh --environment prod --slot staging

# After swapping to production
./validate-deployment.sh --environment prod
```

**What it does:** Validates deployment readiness with 10 automated checks
**Output:** Pass/fail report + ready-to-run swap command
**Use case:** Zero-downtime deployment validation

---

### 4. Performance Baseline (5 minutes)

```bash
cd /Users/alex/dev/invoice-agent/scripts/automation

# Make executable (first time only)
chmod +x performance-test.sh

# Run with 10 concurrent test invoices
./performance-test.sh --concurrent 10 --environment prod
```

**What it does:** Measures throughput, latency, error rate
**Output:** Detailed performance report with SLO compliance
**Use case:** Capacity planning, regression detection

**View report:**
```bash
cat /tmp/invoice-agent-perf-*/performance-report.txt
```

---

## Testing Reference - Top 10 Commands

From `/Users/alex/dev/invoice-agent/docs/RUNBOOK.md`:

### 1. Check Function App Status
```bash
az functionapp show \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "{State:state, DefaultHostName:defaultHostName}" \
  -o table
```

### 2. Check Queue Depths
```bash
for queue in raw-mail to-post notify; do
  az storage queue metadata show \
    --name "$queue" \
    --account-name stinvoiceagentprod \
    --query "approximateMessagesCount" -o tsv
done
```

### 3. List Active Vendors
```bash
az storage entity query \
  --table-name VendorMaster \
  --account-name stinvoiceagentprod \
  --filter "PartitionKey eq 'Vendor' and Active eq true" \
  --select "VendorName,GLCode,ExpenseDept" \
  --output table
```

### 4. View Recent Errors
```bash
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --analytics-query "exceptions | where timestamp > ago(1h) | take 10" \
  --output table
```

### 5. Check Recent Transactions
```bash
az storage entity query \
  --table-name InvoiceTransactions \
  --account-name stinvoiceagentprod \
  --filter "PartitionKey eq '$(date +%Y%m)'" \
  --select "RowKey,VendorName,Status,ProcessedAt" \
  --output table | tail -10
```

### 6. Test Teams Webhook
```bash
WEBHOOK_URL=$(az functionapp config appsettings list \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "[?name=='TEAMS_WEBHOOK_URL'].value | [0]" -o tsv)

curl -X POST "$WEBHOOK_URL" \
  -H 'Content-Type: application/json' \
  -d '{"@type":"MessageCard","summary":"Test","themeColor":"0078D4","sections":[{"activityTitle":"Test"}]}'
```

### 7. Check Application Settings
```bash
az functionapp config appsettings list \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "[].{Name:name, IsSet: value != null}" \
  -o table
```

### 8. Stream Live Logs
```bash
az functionapp log tail \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod
```

### 9. Check Performance Metrics
```bash
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --analytics-query "
    requests
    | where timestamp > ago(24h)
    | summarize
        Count = count(),
        AvgDuration = round(avg(duration)/1000, 2),
        P95Duration = round(percentile(duration, 95)/1000, 2),
        SuccessRate = round(countif(success == true) * 100.0 / count(), 2)
      by operation_Name
  " \
  --output table
```

### 10. Restart Function App (if needed)
```bash
az functionapp restart \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod
```

---

## Observability Quick Wins

From `/Users/alex/dev/invoice-agent/docs/OBSERVABILITY_PROPOSAL.md`:

### Immediate Actions (No Code Changes)

**1. Review Existing Dashboards**
- Navigate to Azure Portal → Application Insights → `ai-invoice-agent-prod`
- Click "Dashboards" → Review default dashboard
- Pin key metrics to your Azure Portal homepage

**2. Test Existing Alerts**
- Navigate to Azure Portal → Resource Groups → `rg-invoice-agent-prod`
- Click "Alerts" → Review 8 configured alert rules
- Verify action group email recipients

**3. Explore Application Insights**
```bash
# Open in Azure Portal
az monitor app-insights component show \
  --app ai-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "appId" -o tsv

# View Live Metrics (real-time)
# https://portal.azure.com → ai-invoice-agent-prod → Live Metrics
```

**4. Review Log Queries**
- Open `/Users/alex/dev/invoice-agent/docs/monitoring/LOG_QUERIES.md`
- Copy any query
- Run in Application Insights → Logs

---

## Schedule Automated Checks

### Option 1: Cron (Linux/Mac)

```bash
# Edit crontab
crontab -e

# Add these lines:
# Health check every 15 minutes
*/15 * * * * /Users/alex/dev/invoice-agent/scripts/automation/health-check.sh --environment prod >> /var/log/invoice-agent-health.log 2>&1

# Daily log collection at midnight
0 0 * * * /Users/alex/dev/invoice-agent/scripts/automation/collect-logs.sh --hours 24 --environment prod

# Weekly performance test (Sundays at 2am)
0 2 * * 0 /Users/alex/dev/invoice-agent/scripts/automation/performance-test.sh --concurrent 10 --environment prod
```

### Option 2: GitHub Actions

```yaml
# .github/workflows/scheduled-health-check.yml
name: Scheduled Health Check

on:
  schedule:
    - cron: '0 */4 * * *'  # Every 4 hours

jobs:
  health-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Azure Login
        uses: azure/login@v1
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Run Health Check
        run: |
          chmod +x scripts/automation/health-check.sh
          scripts/automation/health-check.sh --environment prod
```

---

## Troubleshooting - First Steps

### Issue: "Invoices not being processed"

```bash
# 1. Quick health check
cd /Users/alex/dev/invoice-agent/scripts/automation
./health-check.sh --environment prod

# 2. Check Function App state
az functionapp show \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "state" -o tsv

# 3. Check queue depths
for queue in raw-mail to-post notify; do
  echo -n "$queue: "
  az storage queue metadata show \
    --name "$queue" \
    --account-name stinvoiceagentprod \
    --query "approximateMessagesCount" -o tsv
done

# 4. Collect comprehensive logs
./collect-logs.sh --hours 2 --environment prod
```

### Issue: "High error rate"

```bash
# 1. Collect logs with error analysis
cd /Users/alex/dev/invoice-agent/scripts/automation
./collect-logs.sh --hours 4 --environment prod

# 2. View error summary
cd /tmp/invoice-agent-logs-prod-*
cat 10-error-summary.txt
cat 11-top-errors.txt

# 3. Check specific error in Application Insights
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --analytics-query "
    exceptions
    | where timestamp > ago(1h)
    | order by timestamp desc
    | take 10
  " \
  --output table
```

### Issue: "Slow performance"

```bash
# 1. Run performance test
cd /Users/alex/dev/invoice-agent/scripts/automation
./performance-test.sh --concurrent 10 --environment prod

# 2. Review performance report
cat /tmp/invoice-agent-perf-*/performance-report.txt

# 3. Check function duration breakdown
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --analytics-query "
    requests
    | where timestamp > ago(1h)
    | summarize
        AvgDuration = avg(duration)/1000,
        P95Duration = percentile(duration, 95)/1000
      by operation_Name
  " \
  --output table
```

---

## Where to Find Everything

### Documentation
```
docs/
├── RUNBOOK.md                          # ← Complete testing guide
├── OBSERVABILITY_PROPOSAL.md           # ← Monitoring strategy
├── DELIVERABLES_SUMMARY.md             # ← This package overview
├── monitoring/
│   ├── MONITORING_GUIDE.md             # ← Alert response procedures
│   └── LOG_QUERIES.md                  # ← 50+ KQL queries
└── operations/
    └── TROUBLESHOOTING_GUIDE.md        # ← Common issues & fixes
```

### Automation Scripts
```
scripts/automation/
├── README.md                           # ← Script documentation
├── health-check.sh                     # ← System health validation
├── collect-logs.sh                     # ← Log collection tool
├── validate-deployment.sh              # ← Deployment validation
└── performance-test.sh                 # ← Performance testing
```

---

## Getting Help

### Self-Service Resources

1. **Runbook** - Step-by-step testing procedures
   - Location: `docs/RUNBOOK.md`
   - Search for your component or error

2. **Troubleshooting Guide** - Common issues
   - Location: `docs/operations/TROUBLESHOOTING_GUIDE.md`
   - Decision trees for diagnosis

3. **Log Queries** - Pre-built KQL queries
   - Location: `docs/monitoring/LOG_QUERIES.md`
   - Copy and run in Application Insights

4. **Script README** - Automation tool usage
   - Location: `scripts/automation/README.md`
   - Usage examples and troubleshooting

### Team Support

- **DevOps Team:** General questions, automation issues
- **On-Call Engineer:** Production incidents
- **SRE Team:** Monitoring and alerting
- **Engineering Lead:** Strategic decisions

---

## Next Steps

### Today (5 minutes)
1. ✅ Run health check
2. ✅ Bookmark this guide
3. ✅ Review RUNBOOK.md Table of Contents

### This Week (1 hour)
1. ⏳ Test all 4 automation scripts
2. ⏳ Review observability proposal
3. ⏳ Schedule health checks (cron or GitHub Actions)
4. ⏳ Add validation to CI/CD pipeline

### This Month (4-6 hours)
1. ⏳ Implement Phase 1 of observability proposal
2. ⏳ Create custom dashboards
3. ⏳ Establish weekly performance baseline
4. ⏳ Team training on tools and processes

---

## Success Checklist

After implementing this package, you should be able to:

**Testing & Validation**
- [ ] Run comprehensive health check in <1 minute
- [ ] Validate deployments before production
- [ ] Collect diagnostic logs in <5 minutes
- [ ] Measure system performance on demand

**Monitoring & Alerting**
- [ ] View real-time system health
- [ ] Receive alerts for critical issues
- [ ] Track SLO compliance
- [ ] Investigate errors with pre-built queries

**Incident Response**
- [ ] Diagnose issues in <15 minutes
- [ ] Collect evidence for post-mortems
- [ ] Track incidents to resolution
- [ ] Prevent recurrence with improved monitoring

**Operational Excellence**
- [ ] Scheduled automated health checks
- [ ] CI/CD deployment validation
- [ ] Weekly performance baselines
- [ ] Proactive issue detection

---

**Ready to go? Start with:**
```bash
cd /Users/alex/dev/invoice-agent/scripts/automation
./health-check.sh --environment prod
```

Good luck! 🚀
