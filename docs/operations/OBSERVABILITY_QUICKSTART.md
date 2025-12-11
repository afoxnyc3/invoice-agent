# Observability Quick Start Guide

A practical guide to monitoring the Invoice Agent system.

---

## Quick Access Links

| Resource | URL |
|----------|-----|
| **Azure Portal** | https://portal.azure.com |
| **App Insights** | Portal → Application Insights → ai-invoice-agent-prod |
| **Function App** | Portal → Function Apps → func-invoice-agent-prod |
| **Workbook Dashboard** | App Insights → Workbooks → "Invoice Agent Operations" |

---

## 1. Deploy the Dashboard (One-Time Setup)

```bash
# From repo root
./infrastructure/scripts/deploy_workbook.sh --env prod
```

After deployment, access via:
1. Azure Portal → Application Insights → ai-invoice-agent-prod
2. Click **Workbooks** in left menu
3. Open **"Invoice Agent Operations"**

---

## 2. Dashboard Sections

### Processing Overview (KPIs)
Four tiles showing real-time metrics:
- **Total Processed** - Invoice count in selected time range
- **Vendor Match Rate** - % of invoices matched to known vendors
- **Avg Processing Time** - End-to-end latency in milliseconds
- **Error Rate** - % of failed function executions

### Function Performance
Table showing each function's health:
| Column | Meaning |
|--------|---------|
| Executions | How many times the function ran |
| AvgDuration | Average execution time (ms) |
| P95Duration | 95th percentile (worst case) |
| FailureRate | % of executions that failed |

**Healthy values:**
- FailureRate < 1% (green)
- AvgDuration < 5000ms for most functions

### Queue Health
- **Pie chart**: Shows message distribution across queues
- **Bar chart**: Poison queue messages (errors requiring attention)

**If poison queue has messages**: Check App Insights logs for error details.

### Webhook vs Fallback
Shows how invoices are being processed:
- **Webhook (Real-time)**: Graph API notifications (<10 sec)
- **Fallback (Timer)**: Hourly polling (safety net)

**Healthy**: Webhook should handle 95%+ of invoices.

### Vendor Analytics
- **Top 10 Vendors**: Most common invoice senders
- **Unknown Vendors**: Vendors not in VendorMaster (need to be added)

### Recent Errors
- **Exceptions**: Application errors with stack traces
- **Failed Requests**: HTTP/queue failures with status codes

---

## 3. Common Monitoring Tasks

### Check if invoices are processing

1. Open workbook, set time range to **1 hour**
2. Look at **Processing Overview** → Total Processed
3. Check **Function Performance** → all functions should have recent executions

### Investigate a failed invoice

1. Open workbook → **Recent Errors** section
2. Find the exception or failed request
3. Note the timestamp and error message
4. For more detail:
   ```
   App Insights → Logs → Run query:

   exceptions
   | where timestamp > ago(1h)
   | order by timestamp desc
   ```

### Check why notifications aren't arriving

1. Open workbook → **Function Performance**
2. Look for **Notify** function - is it executing?
3. Check **FailureRate** - if high, check Recent Errors
4. Verify webhook URL in Key Vault is correct

### Find unknown vendors to add

1. Open workbook → **Vendor Analytics**
2. Look at **Unknown Vendors** table
3. Add frequently appearing vendors to VendorMaster via AddVendor API

---

## 4. Useful KQL Queries

Run these in App Insights → Logs:

### Recent invoice processing
```kusto
traces
| where timestamp > ago(1h)
| where message contains "Enriched" or message contains "Posted"
| project timestamp, message
| order by timestamp desc
```

### Errors by function
```kusto
exceptions
| where timestamp > ago(24h)
| summarize count() by outerType, cloud_RoleName
| order by count_ desc
```

### Queue message flow
```kusto
traces
| where timestamp > ago(1h)
| where message contains "Queue" or message contains "Queued"
| project timestamp, message
| order by timestamp desc
```

### Webhook subscription status
```kusto
traces
| where timestamp > ago(7d)
| where message contains "subscription"
| project timestamp, message
| order by timestamp desc
```

### Vendor match rate
```kusto
traces
| where timestamp > ago(24h)
| where message contains "Vendor lookup" or message contains "Unknown vendor"
| extend IsKnown = message !contains "Unknown"
| summarize Known = countif(IsKnown), Unknown = countif(not(IsKnown))
| extend MatchRate = round(Known * 100.0 / (Known + Unknown), 1)
```

---

## 5. Alerts (Pre-Configured)

The system has automatic alerts for:

| Alert | Condition | Action |
|-------|-----------|--------|
| High Error Rate | >1% failures over 5 min | Email notification |
| Function Failures | Any function failure | Email notification |
| Poison Queue | Messages in dead-letter | Email notification |
| Low Availability | <95% uptime | Email notification |

To view/modify alerts:
- Azure Portal → Resource Groups → rg-invoice-agent-prod → Alerts

---

## 6. Quick Health Check

Run this 30-second check to verify system health:

1. **Functions running?**
   - Portal → func-invoice-agent-prod → Functions
   - Should show 9 functions, all enabled

2. **Recent activity?**
   - App Insights → Overview → Server requests chart
   - Should show recent requests

3. **Errors?**
   - App Insights → Failures
   - Check for red spikes

4. **Queues clear?**
   - Portal → Storage Account → Queues
   - Poison queues should be empty

---

## 7. Troubleshooting

### No data in dashboard
- Verify time range is correct (try "Last 24 hours")
- Check App Insights is receiving data: Overview → Live Metrics
- Ensure `{subscription-id}` was replaced in workbook template

### Dashboard queries timeout
- Reduce time range
- App Insights may have high latency during high ingestion

### Can't find workbook
- Verify deployment completed: check script output
- Try refreshing the Workbooks page
- Check you're in the correct App Insights resource

---

## Related Documentation

- [TROUBLESHOOTING_GUIDE.md](TROUBLESHOOTING_GUIDE.md) - Detailed issue resolution
- [../monitoring/README.md](../../infrastructure/monitoring/README.md) - Alert configuration
- [TESTING_PLAYBOOK.md](TESTING_PLAYBOOK.md) - End-to-end testing procedures

---

**Last Updated:** 2024-12-10
