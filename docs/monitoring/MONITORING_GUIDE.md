# Invoice Agent Monitoring & Alerting Guide

## Overview

This guide provides comprehensive instructions for monitoring the Invoice Agent production system, responding to alerts, and troubleshooting common issues.

**Production Environment:**
- Resource Group: `rg-invoice-agent-prod`
- Function App: `func-invoice-agent-prod`
- Application Insights: `ai-invoice-agent-prod`
- Storage Account: `stinvoiceagentprod`
- Region: East US

---

## Table of Contents

1. [Accessing Dashboards](#accessing-dashboards)
2. [Understanding Alerts](#understanding-alerts)
3. [Alert Response Procedures](#alert-response-procedures)
4. [Service Level Objectives (SLOs)](#service-level-objectives-slos)
5. [Common Troubleshooting Scenarios](#common-troubleshooting-scenarios)
6. [Escalation Procedures](#escalation-procedures)
7. [Maintenance Windows](#maintenance-windows)
8. [Cost Monitoring](#cost-monitoring)

---

## Accessing Dashboards

### Azure Portal Dashboard

1. Navigate to [Azure Portal](https://portal.azure.com)
2. Go to **Dashboards** (left sidebar)
3. Select **Invoice Agent Production Dashboard**

**Key Metrics Displayed:**
- Real-time request rate and latency
- Error rate trends
- Queue depths (raw-mail, to-post, notify)
- Vendor match rate
- Function health status
- Top 10 errors
- Unknown vendors requiring attention

### Application Insights Live Metrics

For real-time monitoring:

1. Go to Application Insights resource: `ai-invoice-agent-prod`
2. Click **Live Metrics** in left menu
3. View real-time requests, failures, and performance

**URL:** `https://portal.azure.com/#@{tenant}/resource/subscriptions/{subscription-id}/resourceGroups/rg-invoice-agent-prod/providers/Microsoft.Insights/components/ai-invoice-agent-prod/liveMetrics`

### Log Analytics Workspace

For custom queries and investigations:

1. Go to Log Analytics workspace: `log-invoice-agent-prod`
2. Click **Logs** in left menu
3. Use queries from [LOG_QUERIES.md](LOG_QUERIES.md)

---

## Understanding Alerts

### Alert Severity Levels

| Severity | Priority | Response Time | Description |
|----------|----------|---------------|-------------|
| **P0** | Critical | Immediate | System down, data loss risk |
| **P1** | High | <15 min | Degraded service, high error rates |
| **P2** | Medium | <1 hour | Performance issues, warnings |
| **P3** | Low | <4 hours | Informational, trend alerts |

### Configured Alerts

#### 1. High Error Rate (P1)
- **Condition:** Error rate >1% over 5 minutes
- **Impact:** Processing failures, invoices not reaching AP
- **Action:** Investigate errors immediately

#### 2. Function Execution Failures (P1)
- **Condition:** Any function execution fails
- **Impact:** Individual invoices may be stuck
- **Action:** Check failure logs, identify failing function

#### 3. High Queue Depth (P2)
- **Condition:** >100 messages in any queue for >10 minutes
- **Impact:** Processing backlog, delayed invoice delivery
- **Action:** Check function performance, consider scaling

#### 4. Processing Latency (P2)
- **Condition:** >5 requests taking >60 seconds in 15 minutes
- **Impact:** SLO violation, slow invoice processing
- **Action:** Investigate performance bottlenecks

#### 5. Poison Queue Messages (P0)
- **Condition:** Any messages in poison queue
- **Impact:** Invoices failed after 5 retry attempts
- **Action:** Manual intervention required, investigate root cause

#### 6. High Unknown Vendor Rate (P2)
- **Condition:** >10 unknown vendors in 1 hour
- **Impact:** Invoices require manual vendor registration
- **Action:** Update VendorMaster table with new vendors

#### 7. Low Availability (P0)
- **Condition:** Function App availability <95%
- **Impact:** System partially or fully down
- **Action:** Immediate investigation, potential failover

#### 8. Storage Throttling (P1)
- **Condition:** Storage latency >1 second
- **Impact:** Slow processing, potential failures
- **Action:** Check storage account limits, consider scaling

---

## Alert Response Procedures

### P0: Critical Alerts

#### Poison Queue Alert

**Symptoms:** Messages in dead-letter queue after 5 retries

**Investigation Steps:**

1. Query poison messages:
   ```kusto
   traces
   | where timestamp > ago(1h)
   | where message contains "poison"
   | project timestamp, operation_Name, customDimensions.transaction_id, message
   ```

2. Find transaction details:
   ```kusto
   traces
   | where customDimensions.transaction_id == "<ULID>"
   | order by timestamp asc
   ```

3. Identify error pattern (Graph API failure, storage issue, etc.)

**Resolution:**
- Fix underlying issue (credentials, permissions, etc.)
- Manually reprocess failed invoices if needed
- Update VendorMaster if vendor-related

**Escalation:** If unresolved in 30 minutes, escalate to engineering team

---

#### Low Availability Alert

**Symptoms:** Function App health check failing, requests not being processed

**Investigation Steps:**

1. Check Function App status in Azure Portal
2. Review recent deployments (potential bad release)
3. Check Application Insights for error patterns
4. Verify Key Vault access and secrets

**Resolution:**
- If recent deployment: Swap staging slot back to production
- If Key Vault issue: Verify Managed Identity permissions
- If platform issue: Check Azure Status Dashboard

**Escalation:** Immediate escalation to on-call engineer

---

### P1: High Priority Alerts

#### High Error Rate Alert

**Symptoms:** >1% of requests failing over 5 minutes

**Investigation Steps:**

1. Check error distribution by function:
   ```kusto
   requests
   | where timestamp > ago(15m)
   | where success == false
   | summarize Count = count() by operation_Name, resultCode
   | order by Count desc
   ```

2. Review recent error messages:
   ```kusto
   exceptions
   | where timestamp > ago(15m)
   | order by timestamp desc
   | take 20
   ```

3. Identify if errors are concentrated in one function or systemic

**Common Causes:**
- **Graph API throttling:** Honor retry-after headers, reduce polling frequency
- **Storage connection issues:** Check connection strings, network connectivity
- **Key Vault secrets expired:** Rotate secrets, verify permissions
- **Invalid vendor data:** Validate VendorMaster table entries

**Resolution:**
- Address specific error pattern identified
- Monitor for 15 minutes to confirm resolution

---

#### Function Execution Failures

**Symptoms:** Individual function invocations failing

**Investigation Steps:**

1. Identify which function is failing
2. Get stack trace from Application Insights
3. Check function logs for specific transaction IDs
4. Verify external dependencies (Graph API, Storage, Key Vault)

**Resolution:**
- Fix code issue if bug identified
- Update configuration if misconfiguration
- Verify external service health

---

#### Storage Throttling Alert

**Symptoms:** High storage latency, potential 503 errors

**Investigation Steps:**

1. Check Storage Account metrics:
   - Transactions per second
   - Ingress/Egress bandwidth
   - Throttling errors

2. Identify which storage service is throttled (Blob, Queue, Table)

**Resolution:**
- Short-term: Reduce polling frequency if possible
- Long-term: Consider upgrading storage tier or partitioning strategy
- Check for runaway processes creating excessive requests

---

### P2: Medium Priority Alerts

#### High Queue Depth Alert

**Symptoms:** >100 messages in queue for >10 minutes

**Investigation Steps:**

1. Check which queue has backlog (raw-mail, to-post, notify)
2. Verify downstream function is processing messages:
   ```kusto
   requests
   | where timestamp > ago(15m)
   | where operation_Name == "ExtractEnrich" // Or PostToAP, Notify
   | summarize Count = count() by bin(timestamp, 1m)
   ```

3. Check for errors in processing function

**Common Causes:**
- Function cold starts during traffic spike
- Downstream dependency slow (Graph API, Storage)
- Sudden influx of emails (end of month, bulk send)

**Resolution:**
- Wait if temporary spike (queues will drain)
- Scale function app if sustained high load
- Investigate and fix if errors blocking processing

---

#### Processing Latency Alert

**Symptoms:** Invoices taking >60 seconds end-to-end

**Investigation Steps:**

1. Identify which function is slow:
   ```kusto
   requests
   | where timestamp > ago(30m)
   | where duration > 10000
   | summarize AvgDuration = avg(duration), Count = count() by operation_Name
   | order by AvgDuration desc
   ```

2. Check for dependency latency (Graph API, Table Storage):
   ```kusto
   dependencies
   | where timestamp > ago(30m)
   | summarize AvgDuration = avg(duration) by type, target
   | order by AvgDuration desc
   ```

**Common Causes:**
- Graph API slow responses
- Table Storage query performance
- Cold starts (first request after idle period)
- Large attachments in Blob Storage

**Resolution:**
- Optimize slow queries or API calls
- Consider implementing caching
- Pre-warm functions if cold starts are frequent

---

#### High Unknown Vendor Rate

**Symptoms:** >10 unknown vendors detected in 1 hour

**Investigation Steps:**

1. List unknown vendors:
   ```kusto
   traces
   | where timestamp > ago(1h)
   | where message contains "Unknown vendor"
   | extend VendorDomain = extract(@"vendor[:\s]+([a-zA-Z0-9.-]+)", 1, message)
   | summarize Count = count() by VendorDomain
   | order by Count desc
   ```

2. Determine if new vendors or data quality issue

**Resolution:**
- Add legitimate vendors to VendorMaster table using AddVendor API
- Verify email sender domains are correct
- Check for spam or junk emails in shared mailbox

---

## Service Level Objectives (SLOs)

### Availability SLO

**Target:** 99% uptime (7.2 hours downtime/month)

**Measurement:**
```kusto
requests
| where timestamp > ago(30d)
| summarize
    TotalRequests = count(),
    SuccessfulRequests = countif(success == true)
| extend Availability = SuccessfulRequests * 100.0 / TotalRequests
```

**Review Frequency:** Weekly

---

### Latency SLO

**Target:** <60 seconds end-to-end processing for 95% of invoices

**Measurement:**
```kusto
requests
| where timestamp > ago(7d)
| summarize P95 = percentile(duration, 95), P99 = percentile(duration, 99)
| extend P95Seconds = P95 / 1000, P99Seconds = P99 / 1000
```

**Review Frequency:** Daily

---

### Error Rate SLO

**Target:** <1% error rate

**Measurement:**
```kusto
requests
| where timestamp > ago(24h)
| summarize
    Total = count(),
    Failed = countif(success == false)
| extend ErrorRate = Failed * 100.0 / Total
```

**Review Frequency:** Hourly (automated alert)

---

### Vendor Match Rate SLO

**Target:** >80% vendor match rate (known vendors)

**Measurement:**
```kusto
// See LOG_QUERIES.md - Unknown Vendor Rate query
```

**Review Frequency:** Weekly

---

## Common Troubleshooting Scenarios

### Scenario 1: Invoices Not Being Processed

**Symptoms:**
- Emails in mailbox but no activity in logs
- MailIngest function not triggering

**Checklist:**
1. Verify timer trigger is enabled (check Function App settings)
2. Check Graph API credentials in Key Vault
3. Verify shared mailbox permissions for service principal
4. Check Application Insights for MailIngest errors
5. Confirm storage connection string is valid

**Quick Fix:**
```bash
# Restart Function App
az functionapp restart --name func-invoice-agent-prod --resource-group rg-invoice-agent-prod
```

---

### Scenario 2: Emails Stuck in Queue

**Symptoms:**
- Messages in queue but not being processed
- Downstream function not consuming messages

**Checklist:**
1. Check if function is disabled
2. Verify queue connection string
3. Check for poison messages blocking the queue
4. Review function logs for exceptions

**Quick Fix:**
```bash
# Manually trigger function (if queue trigger stuck)
# Use Azure Portal: Function > Code + Test > Run
```

---

### Scenario 3: Unknown Vendor Failures

**Symptoms:**
- Many invoices flagged as "Unknown vendor"
- Registration emails being sent frequently

**Checklist:**
1. Verify VendorMaster table is accessible
2. Check for recent vendor additions that may be missing
3. Verify email domain extraction logic
4. Review vendor naming conventions

**Resolution:**
```bash
# Add vendors using AddVendor API or directly to Table Storage
curl -X POST https://func-invoice-agent-prod.azurewebsites.net/api/vendors \
  -H "Content-Type: application/json" \
  -d '{
    "vendor_name": "Acme Corp",
    "sender_domain": "acme.com",
    "gl_code": "5000-001",
    "cost_center": "IT",
    "approver_email": "manager@company.com"
  }'
```

---

### Scenario 4: Slow Processing

**Symptoms:**
- Invoices taking >60 seconds end-to-end
- Timeouts in logs

**Checklist:**
1. Check Graph API latency (may be Microsoft-side throttling)
2. Verify Table Storage performance
3. Check for large attachments causing Blob upload delays
4. Review function cold start frequency

**Resolution:**
- If Graph API slow: Consider implementing retry with backoff
- If Table Storage slow: Check query patterns, ensure PartitionKey+RowKey lookups
- If cold starts: Consider Always On or Premium plan

---

### Scenario 5: Authentication Failures

**Symptoms:**
- "401 Unauthorized" errors in logs
- Graph API calls failing

**Checklist:**
1. Verify service principal credentials in Key Vault
2. Check certificate/secret expiration
3. Verify API permissions granted to service principal
4. Check Managed Identity role assignments

**Resolution:**
```bash
# Rotate secret (if expired)
# Update Key Vault with new secret
# Restart function app to pick up new credentials
az functionapp restart --name func-invoice-agent-prod --resource-group rg-invoice-agent-prod
```

---

## Escalation Procedures

### On-Call Rotation

**Primary On-Call:** Check team calendar
**Secondary On-Call:** Engineering lead
**Escalation Contact:** IT Director

### Escalation Matrix

| Issue Type | Initial Response | Escalation Time | Escalation Contact |
|------------|------------------|-----------------|-------------------|
| P0 - Critical | Immediate | 30 minutes | Engineering Lead |
| P1 - High | <15 minutes | 1 hour | Senior Engineer |
| P2 - Medium | <1 hour | 4 hours | Team Lead |
| P3 - Low | <4 hours | Next business day | Team |

### Communication Channels

- **Slack:** #invoice-agent-alerts (automated)
- **Teams:** Invoice Agent Ops channel (manual escalation)
- **Email:** ops-team@company.com
- **Phone:** On-call rotation

---

## Maintenance Windows

### Scheduled Maintenance

**Frequency:** Monthly (first Sunday, 2am-4am EST)

**Activities:**
- Azure platform updates
- Secret rotation
- Vendor data refresh
- Log cleanup

**Notification:** 48-hour advance notice via email

---

### Deployment Windows

**Production Deployments:** Tuesdays and Thursdays, 10am-2pm EST

**Process:**
1. Deploy to staging slot
2. Run smoke tests
3. Swap to production
4. Monitor for 30 minutes
5. Rollback if errors detected

**Rollback Procedure:**
```bash
# Swap back to previous slot
az functionapp deployment slot swap \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --slot staging \
  --target-slot production
```

---

## Cost Monitoring

### Monthly Cost Targets

| Service | Target | Alert Threshold |
|---------|--------|----------------|
| Function App | $20 | $30 |
| Storage Account | $10 | $15 |
| Application Insights | $15 | $25 |
| **Total** | **$45** | **$70** |

### Cost Alerts

Azure Cost Management alerts configured:
- **Budget Alert:** 80% of $70 monthly budget
- **Forecast Alert:** Projected to exceed budget by month-end

### Cost Optimization Tips

1. **Log Analytics:** Daily cap set to 1GB to prevent runaway costs
2. **Application Insights:** 90-day retention, sampling at 100% (adjust if needed)
3. **Function App:** Consumption plan (pay-per-execution)
4. **Storage:** Cool tier for blobs older than 30 days (lifecycle policy)

**Review Frequency:** Monthly cost review meeting

---

## Monitoring Configuration Files

### Related Files

- **Alert Rules:** `/infrastructure/monitoring/alerts.bicep`
- **Dashboard:** `/infrastructure/monitoring/dashboard.json`
- **Log Queries:** `/docs/monitoring/LOG_QUERIES.md`
- **Deployment Script:** `/infrastructure/monitoring/deploy-monitoring.sh`

### Updating Alerts

To modify alert thresholds:

1. Edit `/infrastructure/monitoring/alerts.bicep`
2. Update threshold values
3. Deploy changes:
   ```bash
   cd /Users/alex/dev/invoice-agent
   ./infrastructure/monitoring/deploy-monitoring.sh --environment prod --update-alerts
   ```

---

## Health Check Endpoints

### Function App Health

```bash
# Check overall health
curl https://func-invoice-agent-prod.azurewebsites.net/api/health

# Expected Response:
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2024-11-13T12:00:00Z"
}
```

### Individual Function Status

```bash
# List all functions
az functionapp function list \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod
```

---

## Reporting

### Daily Status Report

**Automated Report:** Sent daily at 8am EST to ops-team@company.com

**Contents:**
- Invoices processed (last 24h)
- Error rate
- Average processing time
- Unknown vendor count
- Queue depths snapshot
- Top 5 errors

### Weekly SLO Report

**Manual Report:** Generated every Monday

**Metrics:**
- Availability %
- P95 latency
- Error rate trend
- Vendor match rate
- SLO compliance summary

**Query Template:** See LOG_QUERIES.md - "Hourly SLO Compliance Report"

---

## Support Contacts

### Internal Team
- **Ops Team:** ops-team@company.com
- **Development Team:** dev-team@company.com
- **On-Call Engineer:** Use PagerDuty or on-call rotation

### External Vendors
- **Microsoft Azure Support:** Azure Portal > Support
- **NetSuite Integration:** netsuite-support@company.com

---

## Appendix: Quick Reference Commands

### Restart Function App
```bash
az functionapp restart --name func-invoice-agent-prod --resource-group rg-invoice-agent-prod
```

### View Recent Logs
```bash
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "traces | where timestamp > ago(1h) | order by timestamp desc | take 50"
```

### Check Queue Depth
```bash
az storage message peek \
  --queue-name raw-mail \
  --account-name stinvoiceagentprod \
  --num-messages 10
```

### Add Vendor
```bash
curl -X POST https://func-invoice-agent-prod.azurewebsites.net/api/vendors \
  -H "Content-Type: application/json" \
  -d '{
    "vendor_name": "Example Vendor",
    "sender_domain": "example.com",
    "gl_code": "5000-001",
    "cost_center": "IT",
    "approver_email": "approver@company.com"
  }'
```

---

## Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2024-11-13 | DevOps Team | Initial monitoring guide |

---

**Last Updated:** 2024-11-13
**Document Owner:** DevOps Team
**Review Frequency:** Quarterly
