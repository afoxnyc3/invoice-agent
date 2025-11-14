# Performance Tuning Guide

**Last Updated:** November 13, 2025

Optimization strategies and configuration tuning for Invoice Agent. This guide explains performance bottlenecks and how to resolve them.

## Table of Contents
- [Performance Targets](#performance-targets)
- [Monitoring Performance](#monitoring-performance)
- [Function-Level Tuning](#function-level-tuning)
- [Queue Configuration](#queue-configuration)
- [Storage Optimization](#storage-optimization)
- [Application Insights Tuning](#application-insights-tuning)
- [Cost vs Performance Tradeoffs](#cost-vs-performance-tradeoffs)

---

## Performance Targets

**Current SLA:** Process invoice in <60 seconds end-to-end

**Component Targets:**

| Component | Target | Current | Status |
|-----------|--------|---------|--------|
| MailIngest | <3 seconds | 2-3s | ✅ |
| ExtractEnrich | <5 seconds | 2-4s | ✅ |
| PostToAP | <8 seconds | 5-7s | ✅ |
| Notify | <2 seconds | 1-2s | ✅ |
| **Total** | **<60 seconds** | **45-55s** | **✅ Good** |

**Error Rate Target:** <1%
**Current:** <0.5% ✅

---

## Monitoring Performance

### Real-Time Performance Dashboard

Check Application Insights regularly:

```bash
# Get last hour performance metrics
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "
    requests
    | where timestamp > ago(1h)
    | summarize
        total=count(),
        avg_duration=avg(duration),
        p50=percentile(duration, 50),
        p95=percentile(duration, 95),
        p99=percentile(duration, 99),
        errors=sumif(success == false)
        by name
  " \
  --resource-group rg-invoice-agent-prod
```

**Expected Output:**
```
name           total  avg_duration  p50   p95   p99   errors
MailIngest     12     2500          2400  2800  3100  0
ExtractEnrich  47     3200          3000  4200  4800  2
PostToAP       45     6500          6200  7800  8200  1
Notify         45     1800          1600  2100  2300  0
```

### Set Up Alerts

Create alerts for performance degradation:

```bash
# Alert if average duration exceeds 10 seconds
az monitor metrics alert create \
  --name "invoice-agent-slow-functions" \
  --resource-group rg-invoice-agent-prod \
  --scopes "/subscriptions/{sub}/resourceGroups/rg-invoice-agent-prod/providers/Microsoft.Insights/components/ai-invoice-agent-prod" \
  --condition "avg Duration > 10000" \
  --description "Alert when any function takes >10 seconds"
```

---

## Function-Level Tuning

### Cold Start Mitigation

**Problem:** First invocation takes 2-4 seconds (Python loading)

**Diagnosis:**
```bash
# Check cold start frequency
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "
    traces
    | where message contains 'Cold start'
    | where timestamp > ago(24h)
    | summarize count()
  "

# If >20 per day: May indicate excessive scaling
```

**Solutions (by cost):**

1. **Premium Plan (Recommended) - $50-150/month**
   ```bash
   # Upgrade App Service Plan to Premium
   az appservice plan update \
     --name asp-invoice-agent-prod \
     --resource-group rg-invoice-agent-prod \
     --sku P1V2  # Always-on instances
   ```
   **Impact:** Eliminates cold starts, +500ms overhead gone
   **Cost:** +$50-100/month

2. **Always-On with Consumption Plan**
   ```bash
   # Enable Premium tier with auto-scale
   # No premium plan needed, but keep at least 1 instance warm
   ```

3. **Lightweight Imports (Free)**
   - Move heavy imports inside functions (lazy loading)
   - Reduces Python startup time by 10-15%

### MailIngest Optimization

**Current:** 2-3 seconds per invocation

**Improvement: Graph API Batching**
```python
# Current: Sequential email reads
messages = get_messages(client)  # One API call per email

# Better: Batch processing
messages = get_messages_batch(client, batch_size=10)  # Single call for 10
```

**Impact:** -50% latency if >5 emails per cycle

**Implementation:** See GitHub issue #XX

### ExtractEnrich Optimization

**Current:** 2-4 seconds (VendorMaster lookup time)

**Bottleneck Analysis:**
- If 90% of time is table lookup: Need caching
- If 10% is business logic: Already optimized

**Check:**
```bash
# Profile function execution
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "
    requests
    | where name == 'ExtractEnrich'
    | where timestamp > ago(24h)
    | order by duration desc
    | limit 10
  "
```

**Solution 1: In-Memory Cache (Free)**
```python
# Cache vendor data for 1 hour
from functools import lru_cache
import time

@lru_cache(maxsize=500)
def get_vendor_cached(domain: str, ttl: float = 3600):
    if time.time() > get_vendor_cached.ttl:
        get_vendor_cached.cache_clear()
    return get_vendor_from_table(domain)
```

**Impact:** -70% latency for repeat vendors
**Trade-off:** Stale data up to 1 hour (acceptable for vendor list)

**Solution 2: Redis Cache (12-20/month)**
```bash
# Create Azure Cache for Redis
az redis create \
  --name invoice-agent-cache \
  --resource-group rg-invoice-agent-prod \
  --sku basic \
  --size c0  # 250MB
```

**Impact:** -80% latency, globally consistent
**Trade-off:** +$12/month cost, complexity

### PostToAP Optimization

**Current:** 5-7 seconds (mostly Graph API latency)

**Bottleneck:** Sending email via Graph API takes 5-6 seconds

**Solution 1: Batch Emails (Medium effort)**
- Queue multiple invoices
- Send batch email digest instead of individual emails
- Reduces from 45 emails/day to 4-5 batches

```python
# Current: 1 email per invoice
# New: 1 email per batch

# Impact: -80% API calls, -30% total time
```

**Solution 2: Graph API Optimization (Free)**
```python
# Use async calls where possible
# Batch Graph API requests

# Current: Sequential send
for invoice in invoices:
    send_via_graph_api(invoice)  # 5-7s each

# Better: Batch
send_batch_via_graph_api(invoices)  # 10-12s for batch of 5
```

**Impact:** -50% latency per email

---

## Queue Configuration

### Visibility Timeout

**Current Setting:** 5 minutes

**When to adjust:**
- If functions take >5 min: Increase visibility
- If functions fail quickly: Decrease visibility

```bash
# Update visibility timeout (in seconds)
az storage queue metadata update \
  --account-name stinvoiceagentprod \
  --name to-post \
  --visibility-timeout 900  # 15 minutes
```

**Analysis:**
```bash
# Check how often messages are re-queued
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "
    requests
    | where name == 'PostToAP'
    | where resultCode == '500'
    | summarize failures = count()
  "

# If >10% retry rate: Messages likely timing out
```

### Queue Message Batch Size

**Current:** 32 messages per batch

**Tuning:**
```python
# In function code, change batch trigger
# binding in function.json

{
  "batchSize": 32  # Increase to 64 for better throughput
}
```

**Impact:**
- Larger batch: Better throughput, higher memory
- Smaller batch: Better latency, more invocations

**Recommendation:** Increase to 64 if memory allows

### Poison Queue Handling

**Current:** Messages after 5 retries → poison queue

**Configuration:**
```bash
# Set max delivery attempts
# (Currently hard-coded in function, configurable)
```

**Monitor poison queues:**
```bash
# Alert on poison queue growth
az monitor metrics alert create \
  --name "poison-queue-alert" \
  --scopes "storageAccounts/stinvoiceagentprod" \
  --condition "avg ApproximateMessageCount > 10"
```

---

## Storage Optimization

### Table Storage

**Current:** VendorMaster with 25 vendors, InvoiceTransactions with 10k records

**Partition Strategy:**
- Current: PartitionKey="Vendor" (single partition for all vendors)
- Optimal for <10k entities (acceptable)
- If >100k vendors: Partition by vendor_domain prefix

**Query Performance:**
```bash
# Check storage account throughput metrics
az monitor metrics list \
  --resource /subscriptions/{sub}/resourceGroups/rg-invoice-agent-prod/providers/Microsoft.Storage/storageAccounts/stinvoiceagentprod \
  --metric Transactions \
  --start-time "$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --interval PT1M
```

**Expected:** <1000 transactions/second (Table Storage max: 20,000)

### Blob Storage

**Current:** Invoices stored in blob, links in queue messages

**Optimization:**
- Set blob expiration policy (delete after 90 days)
- Use hot/cool storage tiers

```bash
# Set lifecycle policy - delete old invoices
az storage account management-policy create \
  --account-name stinvoiceagentprod \
  --policy @- << 'EOF'
{
  "rules": [{
    "name": "archive-old-invoices",
    "enabled": true,
    "type": "Lifecycle",
    "definition": {
      "filters": {"blobTypes": ["blockBlob"]},
      "actions": {
        "baseBlob": {
          "delete": {"daysAfterModificationGreaterThan": 90}
        }
      }
    }
  }]
}
EOF
```

**Impact:** -70% storage cost after 90 days

---

## Application Insights Tuning

### Sampling Strategy

**Current:** All traces captured (100% sampling)

**Cost Impact:** ~$0.50 per GB ingested

**Optimization:**
```bash
# Enable adaptive sampling - capture only anomalies
az functionapp config appsettings set \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --settings "APPINSIGHTS_SAMPLING_PERCENTAGE=25"
```

**Trade-off:**
- Reduces cost 75%
- May miss rare issues
- Recommended for production (keep 100% in dev)

**Alternative: Selective Logging**
```python
# Log only errors and slow requests, not everything
if duration > 8000:  # Only log slow functions
    logger.info(f"Slow function: {duration}ms")
elif error:
    logger.error(f"Function failed: {error}")
```

### Retention Policy

**Current:** 90 days retention

**Tuning:**
```bash
# Increase retention to 1 year for compliance
az monitor app-insights component update \
  --app ai-invoice-agent-prod \
  --retention-time 365 \
  --resource-group rg-invoice-agent-prod
```

**Cost:** +$2-3 per month per GB

---

## Cost vs Performance Tradeoffs

### Optimization Matrix

| Optimization | Cost | Effort | Latency Impact | Recommended |
|--------------|------|--------|----------------|-------------|
| Premium Plan | +$50/mo | 5 min | -500ms (cold start) | Yes |
| In-Memory Cache | Free | 1 hour | -70% (vendor lookup) | Yes |
| Redis Cache | +$12/mo | 2 hours | -80% (global) | Maybe |
| Batch Graph API | Free | 4 hours | -50% (email send) | Yes |
| Blob Lifecycle | Free | 30 min | 0 (savings only) | Yes |
| Increase Batch Size | Free | 10 min | +5% (throughput) | Yes |
| AI Sampling | -$3/mo | 10 min | 0 (logging only) | Yes |

### Current Cost Breakdown

**Monthly Estimate (100-200 invoices/day):**
- Function invocations: $25 (450 executions/day)
- Storage (Table + Blob): $15 (minimal usage)
- Application Insights: $7 (100% sampling)
- Data transfer: $2
- **Total: ~$50/month**

**With All Optimizations:**
- Premium Plan: +$50
- In-Memory Cache: +0
- Blob Lifecycle: -$5
- AI Sampling: -$3
- **New Total: ~$92/month (+84%)**

**But Performance Gain:** -1-2 seconds per invoice

**ROI:** Not justified unless SLA critical

---

## Recommended Tuning Plan

### Phase 1: Immediate (Free, <1 hour)
```bash
# 1. Enable blob lifecycle (free, saves cost)
# 2. Increase queue batch size (free, 5% throughput)
# 3. Enable adaptive AI sampling (free, saves $3-5/mo)
# 4. Add in-memory vendor cache (free, -70% lookup time)
```

### Phase 2: Optional (Premium, <4 hours)
```bash
# Only if SLA failing or cold starts excessive:
# 1. Upgrade to Premium Plan (+$50/mo, -500ms)
# 2. Batch Graph API calls (+0, -30% API latency)
```

### Phase 3: Advanced (Redis, 2+ hours)
```bash
# Only if vendor cache hit rate low (<50%):
# 1. Add Redis cache (+$12/mo, -80% global latency)
# 2. Implement cache invalidation strategy
```

---

## Benchmarking

### Run Baseline Test

Before making changes, capture baseline:

```bash
# Get baseline metrics
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "
    requests
    | where timestamp > ago(7d)
    | summarize
        count,
        avg_duration=avg(duration),
        p95=percentile(duration, 95),
        errors=sumif(success == false)
        by name
  " > baseline_$(date +%Y%m%d).txt
```

### Measure After Optimization

Run same query after making changes:

```bash
# Same query after optimization
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "
    requests
    | where timestamp > ago(7d)
    | summarize
        count,
        avg_duration=avg(duration),
        p95=percentile(duration, 95),
        errors=sumif(success == false)
        by name
  " > after_$(date +%Y%m%d).txt

# Compare
diff baseline_*.txt after_*.txt
```

---

## Common Performance Issues

### Issue: Functions Taking >10 Seconds

**Diagnosis:**
```bash
# Check which function is slow
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "
    requests
    | where duration > 10000
    | summarize count() by name
  "
```

**Solutions by Function:**

**MailIngest Slow:**
- Too many emails in mailbox (>1000)
- Graph API throttling (reduce batch size)

**ExtractEnrich Slow:**
- VendorMaster table too large (>100k)
- No caching (implement cache)
- Network latency to storage

**PostToAP Slow:**
- Graph API rate limiting
- Email attachment too large
- Network latency to Microsoft services

**Notify Slow:**
- Teams webhook unresponsive
- Not a critical path, ignore if <5s

### Issue: Cold Starts Every Hour

**Root Cause:** Functions being unloaded due to Consumption Plan inactivity

**Solution:** Upgrade to Premium Plan

```bash
az appservice plan update \
  --name asp-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --sku P1V2
```

### Issue: Queue Messages Piling Up

**Diagnosis:**
```bash
# Check queue depths
for q in raw-mail to-post notify; do
  az storage queue metadata show \
    --account-name stinvoiceagentprod \
    --name $q
done
```

**Solutions:**
- If upstream (raw-mail growing): MailIngest too slow
- If downstream (to-post growing): ExtractEnrich too slow
- If notify growing: PostToAP is slow

Investigate slowest function first

---

## Performance Checklist

**Before Deploying Changes:**
- [ ] Run baseline performance test
- [ ] Document current metrics
- [ ] Identify optimization target (function/query)

**After Optimization:**
- [ ] Re-run performance test
- [ ] Compare baseline vs optimized
- [ ] Document improvement percentage
- [ ] Update this guide with findings

**Monthly Review:**
- [ ] Check alert thresholds still appropriate
- [ ] Review cost trend
- [ ] Adjust targets based on business needs

---

**See Also:**
- [Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md) - Performance degradation diagnosis
- [Operations Playbook](OPERATIONS_PLAYBOOK.md) - Weekly performance reviews
- [ARCHITECTURE.md](../ARCHITECTURE.md) - Design decisions affecting performance
