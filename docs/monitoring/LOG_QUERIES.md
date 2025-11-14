# Log Analytics Queries for Invoice Agent

This document contains a collection of useful KQL (Kusto Query Language) queries for monitoring, troubleshooting, and analyzing the Invoice Agent production system.

## Table of Contents
- [Invoice Tracking](#invoice-tracking)
- [Performance Analysis](#performance-analysis)
- [Error Investigation](#error-investigation)
- [Business Metrics](#business-metrics)
- [Queue Analysis](#queue-analysis)
- [Vendor Analysis](#vendor-analysis)

---

## Invoice Tracking

### Track Invoice End-to-End by Transaction ID

Follow a single invoice through all processing stages using its ULID transaction ID.

```kusto
let txnId = "01JCK3Q7H8ZVXN3BARC9GWAEZM"; // Replace with actual ULID
traces
| union requests
| where customDimensions.transaction_id == txnId or customDimensions contains txnId
| project
    timestamp,
    type = itemType,
    operation = operation_Name,
    message,
    severity = severityLevel,
    success,
    duration
| order by timestamp asc
```

**Use Case:** Debug a specific invoice that failed or took too long to process.

---

### Find All Invoices from a Specific Vendor

```kusto
traces
| where timestamp > ago(7d)
| where message contains "vendor" or message contains "sender"
| extend VendorDomain = extract(@"([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", 1, tostring(customDimensions.sender))
| where VendorDomain == "acme.com" // Replace with target vendor
| summarize
    InvoiceCount = count(),
    FirstSeen = min(timestamp),
    LastSeen = max(timestamp),
    TransactionIds = make_set(tostring(customDimensions.transaction_id), 100)
| project VendorDomain, InvoiceCount, FirstSeen, LastSeen, SampleTransactionIds = TransactionIds
```

**Use Case:** Investigate all activity from a specific vendor (e.g., after vendor complaints or data quality issues).

---

### List Recent Invoice Processing (Last 24 Hours)

```kusto
requests
| where timestamp > ago(24h)
| where operation_Name == "MailIngest"
| extend
    txnId = tostring(customDimensions.transaction_id),
    sender = tostring(customDimensions.sender)
| summarize
    ProcessedAt = max(timestamp),
    Status = iff(max(toint(success)) == 1, "✅ Success", "❌ Failed"),
    Duration = max(duration)
    by txnId, sender
| order by ProcessedAt desc
| take 50
```

**Use Case:** Quick overview of recent invoice processing activity.

---

## Performance Analysis

### Identify Slow Processing (>60 seconds)

```kusto
requests
| where timestamp > ago(24h)
| where duration > 60000 // 60 seconds in milliseconds
| extend DurationSeconds = duration / 1000
| project
    timestamp,
    operation_Name,
    DurationSeconds,
    txnId = tostring(customDimensions.transaction_id),
    resultCode,
    success
| order by DurationSeconds desc
| take 20
```

**Use Case:** Find invoices that exceeded the 60-second SLO target.

---

### Average Latency by Function (Last 7 Days)

```kusto
requests
| where timestamp > ago(7d)
| summarize
    AvgDuration = avg(duration),
    P50 = percentile(duration, 50),
    P95 = percentile(duration, 95),
    P99 = percentile(duration, 99),
    Count = count()
    by operation_Name
| extend
    AvgDurationSec = round(AvgDuration / 1000, 2),
    P50Sec = round(P50 / 1000, 2),
    P95Sec = round(P95 / 1000, 2),
    P99Sec = round(P99 / 1000, 2)
| project operation_Name, Count, AvgDurationSec, P50Sec, P95Sec, P99Sec
| order by AvgDurationSec desc
```

**Use Case:** Understand performance characteristics of each function and identify slow operations.

---

### Cold Start Frequency

```kusto
traces
| where timestamp > ago(24h)
| where message contains "cold start" or message contains "Function started"
| summarize ColdStarts = count() by operation_Name, bin(timestamp, 1h)
| order by timestamp desc
```

**Use Case:** Monitor cold start frequency to understand function warm-up patterns.

---

### Hourly Processing Throughput

```kusto
requests
| where timestamp > ago(7d)
| where operation_Name in ("MailIngest", "ExtractEnrich", "PostToAP", "Notify")
| summarize RequestsPerHour = count() by operation_Name, bin(timestamp, 1h)
| order by timestamp desc, operation_Name
```

**Use Case:** Understand daily processing patterns and peak usage times.

---

## Error Investigation

### All Errors in Last 24 Hours

```kusto
exceptions
| union (requests | where success == false)
| where timestamp > ago(24h)
| extend
    ErrorType = iff(itemType == "exception", type, "Failed Request"),
    ErrorMessage = iff(itemType == "exception", outerMessage, tostring(customDimensions.error))
| project
    timestamp,
    operation_Name,
    ErrorType,
    ErrorMessage,
    problemId,
    txnId = tostring(customDimensions.transaction_id)
| order by timestamp desc
| take 100
```

**Use Case:** Get comprehensive error log for troubleshooting.

---

### Error Rate by Function

```kusto
requests
| where timestamp > ago(24h)
| summarize
    TotalRequests = count(),
    FailedRequests = countif(success == false),
    SuccessRate = round(countif(success == true) * 100.0 / count(), 2)
    by operation_Name
| extend ErrorRate = round(100.0 - SuccessRate, 2)
| project operation_Name, TotalRequests, FailedRequests, ErrorRate, SuccessRate
| order by ErrorRate desc
```

**Use Case:** Identify which functions have the highest failure rates.

---

### Stack Trace Analysis for Repeated Errors

```kusto
exceptions
| where timestamp > ago(7d)
| summarize
    Count = count(),
    FirstOccurrence = min(timestamp),
    LastOccurrence = max(timestamp),
    SampleMessage = any(outerMessage),
    SampleStack = any(details[0].parsedStack)
    by problemId, type
| order by Count desc
| take 10
```

**Use Case:** Group similar errors to identify systemic issues vs. one-off failures.

---

### Failed Requests by Result Code

```kusto
requests
| where timestamp > ago(24h)
| where success == false
| summarize Count = count(), SampleMessage = any(tostring(customDimensions.error)) by resultCode, operation_Name
| order by Count desc
```

**Use Case:** Understand failure modes (4xx vs 5xx errors, etc.).

---

## Business Metrics

### Invoice Processing Success Rate (Daily)

```kusto
requests
| where timestamp > ago(30d)
| where operation_Name == "PostToAP"
| summarize
    TotalInvoices = count(),
    SuccessfulInvoices = countif(success == true),
    FailedInvoices = countif(success == false)
    by bin(timestamp, 1d)
| extend SuccessRate = round(SuccessfulInvoices * 100.0 / TotalInvoices, 2)
| project Date = format_datetime(timestamp, 'yyyy-MM-dd'), TotalInvoices, SuccessfulInvoices, FailedInvoices, SuccessRate
| order by Date desc
```

**Use Case:** Track daily SLO compliance and invoice throughput.

---

### Unknown Vendor Rate

```kusto
let timeRange = ago(7d);
let unknownVendors = traces
    | where timestamp > timeRange
    | where message contains "Unknown vendor" or message contains "vendor not found"
    | summarize UnknownCount = count();
let totalProcessed = requests
    | where timestamp > timeRange
    | where operation_Name == "ExtractEnrich"
    | summarize TotalCount = count();
unknownVendors
| extend Total = toscalar(totalProcessed)
| extend
    UnknownRate = round(UnknownCount * 100.0 / Total, 2),
    KnownRate = round(100.0 - (UnknownCount * 100.0 / Total), 2)
| project UnknownCount, TotalProcessed = Total, UnknownRate, KnownRate
```

**Use Case:** Monitor vendor match rate to ensure VendorMaster completeness.

---

### Top 10 Vendors by Volume (Last 30 Days)

```kusto
traces
| where timestamp > ago(30d)
| where message contains "Queued:" or message contains "sender"
| extend VendorDomain = extract(@"([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", 1, tostring(customDimensions.sender))
| where isnotempty(VendorDomain)
| summarize InvoiceCount = count() by VendorDomain
| top 10 by InvoiceCount desc
| project Rank = row_number(), VendorDomain, InvoiceCount
```

**Use Case:** Identify high-volume vendors for prioritization or optimization.

---

### Processing Time Distribution

```kusto
requests
| where timestamp > ago(7d)
| extend DurationSeconds = duration / 1000
| summarize
    Count = count(),
    AvgDuration = avg(DurationSeconds),
    MinDuration = min(DurationSeconds),
    MaxDuration = max(DurationSeconds)
    by DurationBucket = bin(DurationSeconds, 10)
| order by DurationBucket asc
```

**Use Case:** Understand distribution of processing times to identify outliers.

---

## Queue Analysis

### Queue Message Flow Rate

```kusto
traces
| where timestamp > ago(1h)
| where message contains "Queued" or message contains "Dequeued"
| extend
    Action = iff(message contains "Queued", "Enqueued", "Dequeued"),
    QueueName = extract(@"queue[:\s]+([a-z-]+)", 1, message)
| summarize Count = count() by QueueName, Action, bin(timestamp, 5m)
| order by timestamp desc
```

**Use Case:** Monitor queue throughput and identify bottlenecks.

---

### Estimated Current Queue Depths

```kusto
// Note: This is an estimate based on enqueue/dequeue events
let timeWindow = ago(15m);
traces
| where timestamp > timeWindow
| where message contains "Queued" or message contains "Dequeued" or message contains "queue"
| extend QueueName = extract(@"(raw-mail|to-post|notify|poison)", 1, message)
| where isnotempty(QueueName)
| summarize
    Enqueued = countif(message contains "Queued"),
    Dequeued = countif(message contains "Processed" or message contains "Dequeued")
    by QueueName
| extend EstimatedDepth = Enqueued - Dequeued
| project QueueName, EstimatedDepth, Enqueued, Dequeued
| order by EstimatedDepth desc
```

**Use Case:** Estimate queue backlog (note: for accurate counts, query Storage Account metrics directly).

---

### Poison Queue Messages (Dead Letter)

```kusto
traces
| where timestamp > ago(7d)
| where message contains "poison" or message contains "dead-letter" or message contains "max retry"
| extend
    txnId = tostring(customDimensions.transaction_id),
    errorReason = tostring(customDimensions.error)
| project timestamp, operation_Name, txnId, message, errorReason
| order by timestamp desc
```

**Use Case:** Identify messages that failed repeatedly and ended up in poison queue.

---

## Vendor Analysis

### Unknown Vendors (Last 24 Hours)

```kusto
traces
| where timestamp > ago(24h)
| where message contains "Unknown vendor" or message contains "vendor not found"
| extend
    VendorDomain = extract(@"vendor[:\s]+([a-zA-Z0-9.-]+)", 1, message),
    txnId = tostring(customDimensions.transaction_id)
| summarize
    Count = count(),
    FirstSeen = min(timestamp),
    LastSeen = max(timestamp),
    SampleTransactionIds = make_list(txnId, 5)
    by VendorDomain
| order by Count desc
| take 20
```

**Use Case:** Identify candidates for adding to VendorMaster table.

---

### Vendor Lookup Performance

```kusto
dependencies
| where timestamp > ago(24h)
| where type == "Azure table"
| where target contains "VendorMaster"
| summarize
    LookupCount = count(),
    AvgDuration = avg(duration),
    P95Duration = percentile(duration, 95),
    SuccessRate = countif(success == true) * 100.0 / count()
    by bin(timestamp, 1h)
| order by timestamp desc
```

**Use Case:** Monitor VendorMaster table query performance.

---

### Vendors Added Recently (via AddVendor function)

```kusto
requests
| where timestamp > ago(7d)
| where operation_Name == "AddVendor"
| where success == true
| extend
    VendorName = tostring(customDimensions.vendor_name),
    AddedBy = tostring(customDimensions.requester)
| project timestamp, VendorName, AddedBy
| order by timestamp desc
```

**Use Case:** Track vendor additions for audit purposes.

---

## Custom Metrics Queries

### Hourly SLO Compliance Report

```kusto
requests
| where timestamp > ago(7d)
| extend
    MeetsLatencySLO = iff(duration <= 60000, 1, 0),
    IsSuccess = iff(success == true, 1, 0)
| summarize
    TotalRequests = count(),
    SuccessCount = sum(IsSuccess),
    WithinSLOCount = sum(MeetsLatencySLO),
    AvgDuration = avg(duration)
    by bin(timestamp, 1h)
| extend
    SuccessRate = round(SuccessCount * 100.0 / TotalRequests, 2),
    SLOComplianceRate = round(WithinSLOCount * 100.0 / TotalRequests, 2),
    AvgDurationSec = round(AvgDuration / 1000, 2)
| project
    Hour = format_datetime(timestamp, 'yyyy-MM-dd HH:00'),
    TotalRequests,
    SuccessRate,
    SLOComplianceRate,
    AvgDurationSec
| order by Hour desc
```

**Use Case:** Generate SLO compliance report for stakeholders.

---

### Error Budget Calculation (99% Availability Target)

```kusto
let startDate = ago(30d);
let totalMinutes = datetime_diff('minute', now(), startDate);
requests
| where timestamp > startDate
| summarize
    TotalRequests = count(),
    FailedRequests = countif(success == false)
| extend
    ActualAvailability = round((TotalRequests - FailedRequests) * 100.0 / TotalRequests, 4),
    TargetAvailability = 99.0,
    ErrorBudgetMinutes = totalMinutes * 0.01, // 1% of total time
    ActualDowntimeMinutes = round((FailedRequests * 1.0 / TotalRequests) * totalMinutes, 2)
| extend
    ErrorBudgetRemaining = round(ErrorBudgetMinutes - ActualDowntimeMinutes, 2),
    ErrorBudgetUsedPercent = round((ActualDowntimeMinutes / ErrorBudgetMinutes) * 100, 2)
| project
    Period = "Last 30 Days",
    TotalRequests,
    FailedRequests,
    ActualAvailability,
    TargetAvailability,
    ErrorBudgetMinutes,
    ActualDowntimeMinutes,
    ErrorBudgetRemaining,
    ErrorBudgetUsedPercent
```

**Use Case:** Track error budget consumption for SRE practices.

---

## Ad-Hoc Investigation Queries

### Correlation ID Trace (Find All Related Events)

```kusto
let correlationId = "01JCK3Q7H8ZVXN3BARC9GWAEZM"; // Replace with actual ID
union traces, requests, dependencies, exceptions
| where
    operation_Id == correlationId
    or customDimensions.transaction_id == correlationId
    or customDimensions contains correlationId
| project
    timestamp,
    itemType,
    operation_Name,
    message,
    severityLevel,
    duration,
    success,
    resultCode
| order by timestamp asc
```

**Use Case:** Complete event timeline for a specific correlation ID.

---

### Anomaly Detection (Sudden Spike in Errors)

```kusto
requests
| where timestamp > ago(7d)
| summarize
    ErrorCount = countif(success == false),
    TotalCount = count()
    by bin(timestamp, 15m)
| extend ErrorRate = ErrorCount * 100.0 / TotalCount
| extend AvgErrorRate = avg(ErrorRate)
| extend StdDev = stdev(ErrorRate)
| extend IsAnomaly = ErrorRate > (AvgErrorRate + (2 * StdDev))
| where IsAnomaly == true
| project timestamp, ErrorCount, TotalCount, ErrorRate, AvgErrorRate, Threshold = AvgErrorRate + (2 * StdDev)
| order by timestamp desc
```

**Use Case:** Detect unusual spikes in error rates automatically.

---

## Query Tips

### Performance Optimization
- Always use `where timestamp > ago(Xd)` to limit time range
- Filter early in the query pipeline
- Use `take` or `top` to limit results
- Avoid `union` when possible; use specific tables

### Using Parameters
Replace hardcoded values with variables:
```kusto
let txnId = "YOUR_TRANSACTION_ID";
let startTime = ago(24h);
let endTime = now();
traces | where timestamp between(startTime .. endTime) | where customDimensions.transaction_id == txnId
```

### Saving Queries
- Save frequently-used queries as Functions in Log Analytics
- Pin important queries to the dashboard
- Share queries with the team via this document

---

## Related Documentation
- [Monitoring Guide](/Users/alex/dev/invoice-agent/docs/monitoring/MONITORING_GUIDE.md)
- [Alert Configuration](/Users/alex/dev/invoice-agent/infrastructure/monitoring/alerts.bicep)
- [Dashboard Definition](/Users/alex/dev/invoice-agent/infrastructure/monitoring/dashboard.json)
