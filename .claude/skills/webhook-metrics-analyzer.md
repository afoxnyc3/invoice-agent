# Webhook Metrics Analyzer Skill

Analyzes webhook vs fallback timer path performance, success rates, and cost savings.

## Purpose
- Measure webhook migration success
- Compare webhook vs fallback path metrics
- Validate performance targets (<10s webhook, 95/5 split)
- Calculate cost savings

## Usage
Invoke when you need to:
- Verify webhook migration is working
- Measure actual vs expected performance
- Generate webhook success rate reports
- Calculate ROI of webhook migration

## Actions

### 1. Measure Path Distribution (Webhook vs Fallback)
```bash
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "
    traces
    | where timestamp > ago(7d)
    | where operation_Name in ('MailWebhook', 'MailWebhookProcessor', 'MailIngest')
    | summarize Count=count() by operation_Name
    | extend Percentage = (Count * 100.0) / toscalar(summarize sum(Count))
    | project operation_Name, Count, Percentage
    | order by Count desc
  "
```

### 2. Calculate Webhook Path Latency
```bash
# Measure webhook end-to-end latency
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "
    dependencies
    | where timestamp > ago(7d)
    | where operation_Name == 'MailWebhook'
    | summarize
        AvgLatency=avg(duration),
        P50=percentile(duration, 50),
        P95=percentile(duration, 95),
        P99=percentile(duration, 99)
    | project AvgLatency, P50, P95, P99
  "
```

### 3. Compare Success Rates
```bash
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "
    requests
    | where timestamp > ago(7d)
    | where operation_Name in ('MailWebhook', 'MailIngest')
    | summarize
        Total=count(),
        Successful=countif(success == true),
        Failed=countif(success == false)
      by operation_Name
    | extend SuccessRate = (Successful * 100.0) / Total
    | project operation_Name, Total, Successful, Failed, SuccessRate
  "
```

### 4. Calculate Cost Savings
```bash
# Compare execution counts (cost proxy)
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "
    let BeforeMigration = 8640; // 5-min timer = 12/hr * 24hr * 30d
    let AfterWebhook = toscalar(
      requests
      | where timestamp > ago(30d)
      | where operation_Name == 'MailWebhook'
      | count
    );
    let AfterFallback = toscalar(
      requests
      | where timestamp > ago(30d)
      | where operation_Name == 'MailIngest'
      | count
    );
    print
      BeforeExecutions=BeforeMigration,
      AfterExecutions=(AfterWebhook + AfterFallback),
      Reduction=BeforeMigration - (AfterWebhook + AfterFallback),
      ReductionPercent=((BeforeMigration - (AfterWebhook + AfterFallback)) * 100.0) / BeforeMigration
  "
```

### 5. Time-Series Analysis
Generate hourly breakdown showing webhook vs fallback volume:
```bash
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "
    requests
    | where timestamp > ago(7d)
    | where operation_Name in ('MailWebhook', 'MailIngest')
    | summarize Count=count() by bin(timestamp, 1h), operation_Name
    | render timechart
  "
```

## Output Format
Generate report with:
1. **Path Distribution:** Webhook % vs Fallback %
2. **Latency Comparison:** Webhook (<10s target) vs Fallback (5-60min)
3. **Success Rates:** Both paths should be >99%
4. **Cost Savings:** Execution count reduction
5. **Recommendations:** Adjust fallback frequency if needed

## Target Metrics
- **Webhook Path:** ≥95% of emails
- **Fallback Path:** ≤5% of emails
- **Webhook Latency:** <10 seconds (P95)
- **Success Rate:** >99% for both paths
- **Cost Savings:** 70% reduction in executions

## Example Report
```
Webhook Migration Success Report
Date: 2025-11-24
Period: Last 7 days

Path Distribution:
✅ Webhook: 233 emails (95.1%) - TARGET MET
✅ Fallback: 12 emails (4.9%) - TARGET MET

Latency:
✅ Webhook P95: 8.2s - TARGET MET (<10s)
⚠️ Fallback avg: 35min (by design - hourly timer)

Success Rates:
✅ Webhook: 99.6% (232/233 successful)
✅ Fallback: 100% (12/12 successful)

Cost Savings:
✅ Before: 8,640 executions/month
✅ After: 2,592 executions/month (webhook) + 720 (fallback) = 3,312 total
✅ Reduction: 5,328 executions (61.6% reduction)
✅ Estimated savings: $1.40/month

Recommendations:
1. Webhook migration is successful - targets met
2. Fallback frequency (hourly) is appropriate
3. Monitor webhook subscription health daily
```
