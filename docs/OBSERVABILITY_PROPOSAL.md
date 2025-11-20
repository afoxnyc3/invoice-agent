# Invoice Agent Observability Proposal

**Version:** 1.0.0
**Date:** 2025-11-19
**Status:** Proposed
**Owner:** DevOps Team

## Executive Summary

This proposal outlines a comprehensive observability strategy for the Invoice Agent production system, leveraging Azure-native monitoring tools to ensure high availability, performance, and reliability. The proposed solution balances operational excellence with cost-effectiveness, suitable for the system's scale (5-50 invoices/day, ~1500/month).

### Key Recommendations

1. **Application Insights** as primary telemetry platform
2. **Log Analytics Workspace** for advanced querying and correlation
3. **Azure Monitor Alerts** for proactive incident detection
4. **Custom Dashboards** for real-time visibility
5. **Synthetic Monitoring** for availability validation

### Expected Outcomes

- **Availability:** 99%+ uptime
- **MTTR:** <15 minutes for P1 incidents
- **Observability:** Complete request tracing across all functions
- **Cost:** ~$7-10/month for comprehensive monitoring

---

## Table of Contents

- [Current State Assessment](#current-state-assessment)
- [Proposed Architecture](#proposed-architecture)
- [Implementation Plan](#implementation-plan)
- [Custom Metrics & KPIs](#custom-metrics--kpis)
- [Alert Rules Configuration](#alert-rules-configuration)
- [Dashboard Specifications](#dashboard-specifications)
- [Log Analytics Queries](#log-analytics-queries)
- [Synthetic Monitoring](#synthetic-monitoring)
- [Cost Analysis](#cost-analysis)
- [Maintenance & Operations](#maintenance--operations)

---

## Current State Assessment

### What's Already Configured

✅ **Application Insights**
- Resource: `ai-invoice-agent-prod`
- Workspace-based ingestion mode
- 90-day retention
- 100% sampling (no data loss)
- Connected to Log Analytics

✅ **Log Analytics Workspace**
- Resource: `log-invoice-agent-prod`
- 90-day retention
- 1GB daily cap (cost control)
- PerGB2018 pricing tier

✅ **Basic Alert Rules** (from `infrastructure/monitoring/alerts.bicep`)
- High error rate alert (P1)
- Function execution failures (P1)
- Queue depth monitoring (P2)
- Processing latency alert (P2)
- Poison queue detection (P0)
- Unknown vendor rate (P2)
- Availability monitoring (P0)
- Storage throttling (P1)

✅ **Action Groups**
- Email notifications configured
- Optional Teams webhook integration
- Optional SMS for critical alerts

### Gaps Identified

❌ **Missing Custom Metrics**
- No business-level KPIs tracked
- No vendor match rate metrics
- No end-to-end latency tracking per invoice

❌ **Limited Dashboards**
- No real-time operational dashboard
- No business metrics visualization
- No SLO compliance tracking

❌ **No Synthetic Monitoring**
- No proactive availability checks
- No API endpoint health validation

❌ **Incomplete Correlation**
- Transaction IDs not consistently logged
- Distributed tracing not optimized
- Dependency tracking could be enhanced

---

## Proposed Architecture

### Observability Stack

```
┌────────────────────────────────────────────────────────┐
│                   Azure Functions                      │
│  (MailIngest, ExtractEnrich, PostToAP, Notify, etc.)  │
└───────────────────┬────────────────────────────────────┘
                    │
                    │ SDK Auto-Instrumentation
                    │
┌───────────────────▼────────────────────────────────────┐
│            Application Insights                        │
│  • Request telemetry                                   │
│  • Exception tracking                                  │
│  • Dependency calls (Graph API, Storage)               │
│  • Custom events & metrics                             │
│  • Distributed tracing                                 │
└───────────────────┬────────────────────────────────────┘
                    │
                    │ Continuous Export
                    │
┌───────────────────▼────────────────────────────────────┐
│          Log Analytics Workspace                       │
│  • Long-term storage                                   │
│  • Advanced KQL queries                                │
│  • Cross-resource correlation                          │
│  • Alert rule evaluation                               │
└───────────────────┬────────────────────────────────────┘
                    │
        ┌───────────┼───────────┐
        │           │           │
        ▼           ▼           ▼
   ┌────────┐  ┌────────┐  ┌──────────┐
   │ Alerts │  │Dashboard│  │ Workbooks│
   └────────┘  └────────┘  └──────────┘
        │           │           │
        └───────────┼───────────┘
                    │
                    ▼
         ┌──────────────────┐
         │  Action Groups   │
         │  • Email         │
         │  • Teams         │
         │  • SMS (optional)│
         └──────────────────┘
```

### Data Flow

1. **Ingestion:** Functions emit telemetry automatically + custom metrics
2. **Storage:** Application Insights → Log Analytics Workspace
3. **Analysis:** KQL queries for metrics, trends, anomalies
4. **Alerting:** Alert rules evaluate queries at intervals
5. **Notification:** Action groups dispatch to email/Teams/SMS
6. **Visualization:** Dashboards and workbooks for real-time monitoring

---

## Implementation Plan

### Phase 1: Enhanced Telemetry (Week 1)

**Objective:** Improve instrumentation quality and completeness

#### Tasks

1. **Add Custom Metrics to Functions**

```python
# In shared/logger.py, add custom metric tracking

from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import metrics

# Initialize meter
meter = metrics.get_meter(__name__)

# Create counters
invoice_processed_counter = meter.create_counter(
    "invoice.processed",
    description="Number of invoices successfully processed"
)

vendor_match_counter = meter.create_counter(
    "vendor.matched",
    description="Number of invoices with known vendors"
)

vendor_unknown_counter = meter.create_counter(
    "vendor.unknown",
    description="Number of invoices with unknown vendors"
)

# Create histogram for latency
invoice_duration_histogram = meter.create_histogram(
    "invoice.duration",
    description="End-to-end invoice processing duration in seconds"
)

# Usage in functions
def track_invoice_processed(vendor_name: str, duration_seconds: float):
    invoice_processed_counter.add(1, {"vendor": vendor_name})
    invoice_duration_histogram.record(duration_seconds)

def track_vendor_match(matched: bool):
    if matched:
        vendor_match_counter.add(1)
    else:
        vendor_unknown_counter.add(1)
```

2. **Enhance Correlation ID Usage**

```python
# Ensure transaction_id (ULID) is logged in all log statements
# and included in customDimensions

logger.info(
    "Processing invoice",
    extra={
        "transaction_id": transaction_id,
        "vendor": vendor_name,
        "sender": sender_email
    }
)
```

3. **Add Dependency Tracking**

```python
# Explicitly track Graph API and Table Storage calls
from applicationinsights import TelemetryClient

tc = TelemetryClient()

with tc.track_dependency(
    name="Microsoft Graph",
    data=f"GET /users/{mailbox}/messages",
    type="HTTP",
    target="graph.microsoft.com",
    duration=response_time,
    success=True
):
    # Perform Graph API call
    pass
```

**Deliverables:**
- Updated `shared/logger.py` with custom metrics
- All functions instrumented with business metrics
- Correlation IDs consistently used
- Documentation updated

**Effort:** 4-6 hours

---

### Phase 2: Custom Dashboards (Week 2)

**Objective:** Create operational and business dashboards

#### Dashboard 1: Operations Dashboard

**Purpose:** Real-time system health monitoring for on-call engineers

**Metrics:**
- Request rate (requests/minute) - Last 4 hours
- Error rate (%) - Last 4 hours
- Average latency by function - Last 4 hours
- Queue depths (real-time)
- Function execution count - Last hour
- Top 5 errors - Last 24 hours

**Visualizations:**
- Line charts for trends
- Gauge charts for error rate
- Bar charts for function execution counts
- Table for top errors

**Query Examples:**

```kusto
// Request rate over time
requests
| where timestamp > ago(4h)
| summarize RequestsPerMinute = count() by bin(timestamp, 1m)
| render timechart

// Error rate gauge
requests
| where timestamp > ago(4h)
| summarize ErrorRate = round(countif(success == false) * 100.0 / count(), 2)
| extend Threshold = 1.0
| render table

// Queue depths (combine with Storage metrics)
AzureMetrics
| where TimeGenerated > ago(30m)
| where MetricName == "QueueMessageCount"
| where ResourceId contains "stinvoiceagentprod"
| summarize AvgQueueDepth = avg(Average) by bin(TimeGenerated, 1m), Resource
| render timechart
```

#### Dashboard 2: Business Metrics Dashboard

**Purpose:** Track business KPIs for stakeholders

**Metrics:**
- Daily invoice volume
- Vendor match rate (%)
- Unknown vendors requiring registration
- Processing success rate
- Average processing time
- Top 10 vendors by volume
- Monthly trends

**Visualizations:**
- Area charts for daily volume
- Pie chart for vendor match rate
- Bar chart for top vendors
- KPI tiles for success rate

**Query Examples:**

```kusto
// Daily invoice volume
requests
| where timestamp > ago(30d)
| where operation_Name == "PostToAP"
| summarize InvoiceCount = count() by bin(timestamp, 1d)
| render columnchart

// Vendor match rate
let totalInvoices = requests
    | where timestamp > ago(7d)
    | where operation_Name == "ExtractEnrich"
    | count;
let unknownVendors = traces
    | where timestamp > ago(7d)
    | where message contains "Unknown vendor"
    | count;
print MatchRate = round((1 - (todouble(unknownVendors) / todouble(totalInvoices))) * 100, 2)
```

**Deliverables:**
- Operations Dashboard deployed to Azure Portal
- Business Metrics Dashboard deployed
- Dashboard JSON exported to `infrastructure/monitoring/`
- README with dashboard access instructions

**Effort:** 6-8 hours

---

### Phase 3: Advanced Alerting (Week 3)

**Objective:** Implement intelligent, actionable alerts

#### New Alert Rules

1. **End-to-End SLO Violation Alert (P2)**

```kusto
// Trigger when >5% of invoices exceed 60s processing time in 15 min window
requests
| where timestamp > ago(15m)
| where operation_Name in ("MailIngest", "ExtractEnrich", "PostToAP", "Notify")
| extend Duration_Seconds = duration / 1000
| summarize
    TotalCount = count(),
    SlowCount = countif(Duration_Seconds > 60)
| extend ViolationRate = SlowCount * 100.0 / TotalCount
| where ViolationRate > 5
```

**Configuration:**
- Severity: 2 (Warning)
- Evaluation frequency: 5 minutes
- Window size: 15 minutes
- Action: Email + Teams notification

2. **Vendor Master Staleness Alert (P3)**

```kusto
// Trigger when >25% unknown vendor rate sustained for 1 hour
let timeRange = 1h;
let unknownRate = traces
    | where timestamp > ago(timeRange)
    | where message contains "Unknown vendor"
    | count
    | extend Total = toscalar(requests
        | where timestamp > ago(timeRange)
        | where operation_Name == "ExtractEnrich"
        | count)
    | extend UnknownRate = todouble(Count) * 100.0 / todouble(Total);
unknownRate
| where UnknownRate > 25
```

**Configuration:**
- Severity: 3 (Informational)
- Evaluation frequency: 15 minutes
- Window size: 1 hour
- Action: Email notification

3. **Dependency Failure Alert (P1)**

```kusto
// Trigger when Graph API or Storage calls fail >10% in 10 min
dependencies
| where timestamp > ago(10m)
| where type in ("HTTP", "Azure table", "Azure blob")
| summarize
    TotalCalls = count(),
    FailedCalls = countif(success == false)
    by target
| extend FailureRate = FailedCalls * 100.0 / TotalCalls
| where FailureRate > 10
```

**Configuration:**
- Severity: 1 (High)
- Evaluation frequency: 5 minutes
- Window size: 10 minutes
- Action: Email + Teams + SMS (if enabled)

**Deliverables:**
- 3 new alert rules deployed
- Alert documentation updated
- Runbook entries for new alerts

**Effort:** 4 hours

---

### Phase 4: Synthetic Monitoring (Week 4)

**Objective:** Proactively detect availability issues

#### Application Insights Availability Tests

**Standard Availability Test**
- Type: URL ping test
- Target: `https://func-invoice-agent-prod.azurewebsites.net`
- Frequency: Every 5 minutes
- Locations: 3 Azure regions (East US, West Europe, Southeast Asia)
- Alert threshold: 2/3 locations failing

**Configuration:**

```bicep
// In infrastructure/bicep/modules/monitoring.bicep

resource availabilityTest 'Microsoft.Insights/webtests@2022-06-15' = {
  name: 'webtest-invoice-agent-prod'
  location: location
  tags: {
    'hidden-link:${appInsights.id}': 'Resource'
  }
  properties: {
    Name: 'Invoice Agent Availability Test'
    Kind: 'ping'
    Frequency: 300  // 5 minutes
    Timeout: 30
    Enabled: true
    Locations: [
      {
        Id: 'us-va-ash-azr'  // East US
      }
      {
        Id: 'emea-nl-ams-azr'  // West Europe
      }
      {
        Id: 'apac-sg-sin-azr'  // Southeast Asia
      }
    ]
    Configuration: {
      WebTest: '<WebTest Name="Invoice Agent Availability" Enabled="True" Timeout="30"><Items><Request Url="https://func-invoice-agent-prod.azurewebsites.net" ThinkTime="0" Timeout="30" /></Items></WebTest>'
    }
    SyntheticMonitorId: 'invoice-agent-prod'
  }
}

resource availabilityAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'alert-invoice-agent-prod-availability'
  location: 'global'
  properties: {
    description: 'Alert when availability test fails from multiple locations'
    severity: 0  // Critical
    enabled: true
    scopes: [
      availabilityTest.id
      appInsights.id
    ]
    evaluationFrequency: 'PT1M'
    windowSize: 'PT5M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.WebtestLocationAvailabilityCriteria'
      webTestId: availabilityTest.id
      componentId: appInsights.id
      failedLocationCount: 2
    }
    actions: [
      {
        actionGroupId: actionGroup.id
      }
    ]
  }
}
```

**Multi-Step Test (Advanced)**

For more comprehensive testing, create a multi-step availability test:

```xml
<WebTest Name="Invoice Agent End-to-End" Enabled="True" Timeout="120">
  <Items>
    <!-- Step 1: Check homepage -->
    <Request Url="https://func-invoice-agent-prod.azurewebsites.net"
             Method="GET"
             Timeout="30"
             ExpectedHttpStatusCode="200,401" />

    <!-- Step 2: Check AddVendor API exists -->
    <Request Url="https://func-invoice-agent-prod.azurewebsites.net/api/AddVendor"
             Method="GET"
             Timeout="30"
             ExpectedHttpStatusCode="401,405" />
  </Items>
</WebTest>
```

**Deliverables:**
- Availability test deployed
- Multi-location monitoring active
- Availability alert configured
- Documentation updated

**Effort:** 2-3 hours

---

### Phase 5: Log Retention & Archival (Ongoing)

**Objective:** Balance cost and compliance requirements

#### Retention Strategy

**Hot Tier (0-90 days)**
- **Storage:** Application Insights + Log Analytics
- **Access:** Interactive queries, dashboards, alerts
- **Cost:** Standard pricing

**Warm Tier (91-365 days)**
- **Storage:** Log Analytics (basic logs)
- **Access:** Query with additional latency
- **Cost:** 50% cheaper than hot tier

**Cold Tier (366+ days)**
- **Storage:** Azure Blob Storage (archive tier)
- **Access:** Restore required before query
- **Cost:** $0.002/GB/month (~90% cheaper)

#### Configuration

```bicep
// In monitoring.bicep

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: workspaceName
  location: location
  properties: {
    retentionInDays: 90  // Hot tier
    features: {
      enableDataExport: true  // Export to blob for archival
    }
    dataExport: {
      dataExportId: 'invoice-agent-log-export'
      tableNames: [
        'requests'
        'exceptions'
        'traces'
      ]
      destination: {
        resourceId: archiveStorageAccount.id
        metaData: {
          eventHubName: null
        }
      }
      enable: true
    }
  }
}

// Archive storage account
resource archiveStorageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: 'stinvoiceagentarchive'
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Cool'
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    networkAcls: {
      defaultAction: 'Allow'
    }
  }
}

// Lifecycle management policy
resource lifecyclePolicy 'Microsoft.Storage/storageAccounts/managementPolicies@2023-05-01' = {
  parent: archiveStorageAccount
  name: 'default'
  properties: {
    policy: {
      rules: [
        {
          name: 'archiveOldLogs'
          type: 'Lifecycle'
          definition: {
            actions: {
              baseBlob: {
                tierToCool: {
                  daysAfterModificationGreaterThan: 90
                }
                tierToArchive: {
                  daysAfterModificationGreaterThan: 365
                }
                delete: {
                  daysAfterModificationGreaterThan: 2555  // 7 years
                }
              }
            }
            filters: {
              blobTypes: ['blockBlob']
              prefixMatch: ['invoice-agent-logs/']
            }
          }
        }
      ]
    }
  }
}
```

**Deliverables:**
- Data export configured
- Archive storage account deployed
- Lifecycle policy active
- Compliance documentation

**Effort:** 3-4 hours

---

## Custom Metrics & KPIs

### Business Metrics

| Metric | Description | Target | Alert Threshold |
|--------|-------------|--------|----------------|
| Invoice Processing Rate | Invoices processed per hour | 5-10/hour during business hours | <1/hour for 2 hours |
| Vendor Match Rate | % of invoices with known vendors | >80% | <70% sustained 1 hour |
| End-to-End Latency (P95) | 95th percentile processing time | <60 seconds | >90 seconds |
| Success Rate | % of invoices successfully processed | >99% | <95% over 1 hour |
| Unknown Vendor Count | New vendors per day | <5/day | >20/day |

### Technical Metrics

| Metric | Description | Target | Alert Threshold |
|--------|-------------|--------|----------------|
| Function Availability | % uptime for each function | >99.5% | <99% over 5 minutes |
| Cold Start Rate | % of executions with cold start | <10% | >25% sustained |
| Queue Depth | Messages waiting in each queue | 0-10 | >100 for 10 minutes |
| Poison Queue Count | Failed messages after retries | 0 | >0 |
| Graph API Latency (P95) | 95th percentile Graph API response time | <2 seconds | >5 seconds |
| Storage Latency (P95) | 95th percentile storage operations | <100ms | >500ms |
| Error Rate | % of failed requests | <1% | >5% over 5 minutes |

### Custom Events to Track

```python
# In functions, emit custom events for business milestones

from applicationinsights import TelemetryClient

tc = TelemetryClient()

# Invoice successfully processed
tc.track_event(
    "InvoiceProcessed",
    properties={
        "transaction_id": transaction_id,
        "vendor": vendor_name,
        "gl_code": gl_code,
        "duration_seconds": duration
    },
    measurements={
        "processing_time": duration,
        "attachment_size_bytes": blob_size
    }
)

# Unknown vendor detected
tc.track_event(
    "UnknownVendorDetected",
    properties={
        "vendor_domain": sender_domain,
        "sender_email": sender,
        "transaction_id": transaction_id
    }
)

# Vendor registered
tc.track_event(
    "VendorRegistered",
    properties={
        "vendor_name": vendor_name,
        "registered_by": requester_email
    }
)

tc.flush()  # Ensure telemetry is sent
```

---

## Alert Rules Configuration

### Alert Priority Matrix

| Priority | Response Time | Notification Channels | Examples |
|----------|---------------|----------------------|----------|
| P0 (Critical) | Immediate | Email + Teams + SMS | System down, poison queue messages |
| P1 (High) | <15 minutes | Email + Teams | High error rate, dependency failures |
| P2 (Medium) | <1 hour | Email | Queue backlog, slow processing |
| P3 (Low) | <4 hours | Email | Vendor master updates needed |

### Recommended Alert Rules

#### Critical (P0)

1. **System Availability < 95%**
   - Condition: Health check endpoint failing
   - Window: 5 minutes
   - Action: Immediate notification to on-call

2. **Poison Queue Has Messages**
   - Condition: Any message in poison queue
   - Window: 5 minutes
   - Action: Immediate notification + escalation

#### High (P1)

3. **Error Rate > 5%**
   - Condition: Failed requests > 5% of total
   - Window: 5 minutes
   - Action: Notify ops team

4. **Graph API Dependency Failure**
   - Condition: Graph API calls failing >10%
   - Window: 10 minutes
   - Action: Notify ops team + check Graph API status

5. **Storage Throttling**
   - Condition: 429 errors from storage
   - Window: 5 minutes
   - Action: Notify ops team

#### Medium (P2)

6. **Queue Depth > 100**
   - Condition: Any queue depth >100 messages
   - Window: 10 minutes
   - Action: Email notification

7. **Processing Latency > 60s**
   - Condition: >5 requests taking >60s
   - Window: 15 minutes
   - Action: Email notification

8. **Unknown Vendor Rate > 20%**
   - Condition: >10 unknown vendors in 1 hour
   - Window: 1 hour
   - Action: Email notification

#### Low (P3)

9. **Daily Invoice Volume Anomaly**
   - Condition: Daily volume deviates >50% from 7-day average
   - Window: 24 hours
   - Action: Email notification

10. **Vendor Master Not Updated in 30 Days**
    - Condition: No vendor additions in 30 days
    - Window: Daily check
    - Action: Email notification

---

## Dashboard Specifications

### Dashboard 1: Real-Time Operations Dashboard

**Target Audience:** On-call engineers, DevOps team

**Layout:**

```
┌─────────────────────────────────────────────────────────────┐
│                   Invoice Agent - Operations                │
├──────────────┬──────────────┬──────────────┬────────────────┤
│ Availability │ Error Rate   │ Request Rate │ Avg Latency    │
│   99.8%      │    0.5%      │  12 req/min  │   2.3s         │
│   (gauge)    │   (gauge)    │   (number)   │   (number)     │
├──────────────┴──────────────┴──────────────┴────────────────┤
│                                                              │
│  Request Rate Over Time (Last 4 Hours)                      │
│  [Line chart: requests/minute by operation_Name]            │
│                                                              │
├──────────────────────────────┬───────────────────────────────┤
│                              │                               │
│  Error Rate by Function      │   Queue Depths (Real-Time)    │
│  [Bar chart]                 │   [Table with color coding]   │
│                              │                               │
├──────────────────────────────┴───────────────────────────────┤
│                                                              │
│  Function Execution Count (Last Hour)                       │
│  [Stacked bar chart by function]                            │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Top 10 Errors (Last 24 Hours)                              │
│  [Table: Error Type | Count | Last Occurrence]              │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Refresh Rate:** 1 minute

### Dashboard 2: Business Metrics Dashboard

**Target Audience:** Product managers, business stakeholders

**Layout:**

```
┌─────────────────────────────────────────────────────────────┐
│              Invoice Agent - Business Metrics                │
├──────────────┬──────────────┬──────────────┬────────────────┤
│ Today's      │ Success Rate │ Vendor Match │ Avg Processing │
│ Invoices     │              │ Rate         │ Time           │
│   47         │   99.2%      │   85%        │   45s          │
│   (number)   │   (gauge)    │   (gauge)    │   (number)     │
├──────────────┴──────────────┴──────────────┴────────────────┤
│                                                              │
│  Daily Invoice Volume (Last 30 Days)                        │
│  [Area chart with trend line]                               │
│                                                              │
├──────────────────────────────┬───────────────────────────────┤
│                              │                               │
│  Top 10 Vendors (This Month) │   Unknown Vendors This Week   │
│  [Bar chart: vendor | count] │   [Table with action links]   │
│                              │                               │
├──────────────────────────────┴───────────────────────────────┤
│                                                              │
│  Processing Time Distribution                               │
│  [Histogram: <30s | 30-60s | 60-90s | >90s]                 │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Monthly Trends                                             │
│  [Multi-line chart: Invoices | Success Rate | Match Rate]  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Refresh Rate:** 5 minutes

### Dashboard 3: SLO Compliance Dashboard

**Target Audience:** Engineering leadership, SRE team

**Layout:**

```
┌─────────────────────────────────────────────────────────────┐
│                   Invoice Agent - SLO Tracking               │
├──────────────┬──────────────┬──────────────┬────────────────┤
│ Availability │ Latency SLO  │ Error Budget │ Vendor Match   │
│ SLO: 99%     │ SLO: <60s    │ Remaining    │ SLO: >80%      │
│ Actual: 99.5%│ P95: 45s     │   87%        │ Actual: 85%    │
│   ✅         │   ✅         │   ✅         │   ✅           │
├──────────────┴──────────────┴──────────────┴────────────────┤
│                                                              │
│  SLO Compliance Over Time (Last 30 Days)                    │
│  [Multi-line chart: Availability | Latency | Match Rate]    │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Error Budget Burn Rate                                     │
│  [Gauge: Current burn rate vs. sustainable rate]            │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  SLO Violations (Last 30 Days)                              │
│  [Table: Date | SLO | Target | Actual | Duration]           │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Refresh Rate:** 15 minutes

---

## Log Analytics Queries

### Query Library (50+ Queries)

All queries are documented in `/Users/alex/dev/invoice-agent/docs/monitoring/LOG_QUERIES.md`.

**Key Query Categories:**
1. Invoice Tracking (10 queries)
2. Performance Analysis (12 queries)
3. Error Investigation (15 queries)
4. Business Metrics (8 queries)
5. Queue Analysis (5 queries)
6. Vendor Analysis (6 queries)
7. Custom Metrics (5 queries)
8. Ad-Hoc Investigation (5 queries)

**Saved Queries in Log Analytics:**

Create saved queries for frequently-used investigations:

```bash
# Deploy saved queries
az monitor log-analytics workspace saved-search create \
  --resource-group rg-invoice-agent-prod \
  --workspace-name log-invoice-agent-prod \
  --name "InvoiceTrackingByTransactionId" \
  --category "Invoice Agent" \
  --query "let txnId = 'REPLACE_WITH_ULID'; traces | union requests | where customDimensions.transaction_id == txnId or customDimensions contains txnId | project timestamp, type = itemType, operation = operation_Name, message, severity = severityLevel, success, duration | order by timestamp asc" \
  --display-name "Track Invoice by Transaction ID"
```

---

## Synthetic Monitoring

### Availability Tests Configuration

**Test 1: Basic Availability (Ping Test)**
- **URL:** `https://func-invoice-agent-prod.azurewebsites.net`
- **Frequency:** Every 5 minutes
- **Locations:** East US, West Europe, Southeast Asia
- **Timeout:** 30 seconds
- **Expected:** HTTP 200 or 401
- **Alert:** Fail from 2/3 locations

**Test 2: AddVendor API Check**
- **URL:** `https://func-invoice-agent-prod.azurewebsites.net/api/AddVendor`
- **Method:** GET (expect 401 or 405)
- **Frequency:** Every 15 minutes
- **Locations:** East US
- **Timeout:** 30 seconds
- **Alert:** 3 consecutive failures

**Test 3: End-to-End Simulation (Optional)**

For deeper validation, create a multi-step test that:
1. Calls AddVendor API with test data
2. Verifies response contains expected fields
3. Queries InvoiceTransactions table for test transaction
4. Cleans up test data

This requires authenticated requests and is more complex but provides end-to-end validation.

### Synthetic Test Alerts

```kusto
// Alert when availability test fails
availabilityResults
| where timestamp > ago(15m)
| where success == false
| summarize FailureCount = count() by location
| where FailureCount > 2
```

---

## Cost Analysis

### Current Monthly Costs (Estimated)

| Service | Component | Volume | Unit Cost | Monthly Cost |
|---------|-----------|--------|-----------|--------------|
| Application Insights | Data ingestion | 30GB/month | $2.30/GB | $69.00 |
| Application Insights | Data retention (90 days) | 30GB * 3 months | $0.10/GB | $9.00 |
| Log Analytics | Data ingestion | 30GB/month | $2.76/GB | $82.80 |
| Log Analytics | Data retention (90 days) | 30GB | Included | $0.00 |
| Alert Rules | 8 rules | 8 | $0.10/rule | $0.80 |
| Availability Tests | 2 tests | 2 | $0.001/test | $0.00* |
| Action Groups | Emails | Unlimited | Free | $0.00 |
| **Subtotal (Current)** | | | | **$161.60** |

*First availability test per App Insights resource is free; additional tests are $0.001 per test execution

### Daily Cap Impact

With **1GB daily cap** configured:
- Actual data: ~1GB/day = 30GB/month
- Capped ingestion prevents runaway costs
- Current configuration is optimal for volume

### Proposed Additions (Phase 1-5)

| Addition | Monthly Cost |
|----------|--------------|
| Custom metrics (OpenTelemetry) | Included in ingestion |
| 3 new alert rules | $0.30 |
| Synthetic monitoring (2 tests) | $0.00 (within free tier) |
| Archive storage (Cool tier) | $5.00 |
| Dashboard (Azure Portal) | Free |
| Workbooks | Free |
| **Total Additional Cost** | **~$5.30** |

### Optimized Monthly Cost Projection

**Total: ~$167/month** (with all proposed enhancements)

### Cost Optimization Recommendations

1. **Reduce Sampling to 50%** (if acceptable)
   - Cuts data ingestion in half
   - Saves ~$75/month
   - Trade-off: Less detailed telemetry

2. **Reduce Retention to 30 Days**
   - Saves ~$6/month on App Insights retention
   - Rely on archive for historical data

3. **Use Basic Logs for Non-Critical Tables**
   - 50% cheaper ingestion
   - Slightly higher query latency
   - Applies to traces and dependencies tables

**Optimized Cost: ~$90/month** (with 50% sampling, 30-day retention, basic logs)

### Cost Breakdown by Feature

| Feature | Monthly Cost | Value |
|---------|--------------|-------|
| Real-time monitoring & alerting | $80 | High |
| Historical analysis (90 days) | $15 | Medium |
| Dashboards & visualization | $0 | High |
| Synthetic monitoring | $0 | High |
| Custom metrics | $0 | Medium |
| Archive storage | $5 | Low (compliance) |
| **Total** | **$100** | |

### ROI Justification

**Benefits:**
- Reduced MTTR: 30 min → 15 min (saves 15 min per incident)
- Proactive issue detection: Prevents ~2 incidents/month (saves 1 hour downtime)
- Business insights: Enables data-driven decisions
- Compliance: Audit trail for 7 years

**Cost avoidance:**
- 1 hour downtime = ~50 invoices delayed = $X business impact
- Reduced on-call burden = improved team satisfaction

**Recommendation:** Maintain comprehensive monitoring at ~$100-167/month. Cost is negligible compared to value provided.

---

## Maintenance & Operations

### Weekly Tasks

**Operator Responsibilities:**

- Review SLO compliance dashboard
- Check for new unknown vendors
- Verify alert effectiveness (no alert fatigue)
- Review top 10 errors

**Estimated time:** 15 minutes/week

### Monthly Tasks

- Review cost reports (Azure Cost Management)
- Analyze monthly trends
- Update vendor master if needed
- Review and tune alert thresholds
- Archive logs older than 90 days

**Estimated time:** 1 hour/month

### Quarterly Tasks

- Review and update dashboards
- Add new queries based on team needs
- Evaluate SLO targets (adjust if needed)
- Review retention policy
- Conduct observability training

**Estimated time:** 2 hours/quarter

### Annual Tasks

- Review compliance requirements
- Audit log retention (7-year requirement)
- Renew monitoring strategy
- Update runbooks
- Disaster recovery test

**Estimated time:** 4 hours/year

---

## Appendix: Implementation Checklist

### Phase 1: Enhanced Telemetry

- [ ] Add custom metrics to `shared/logger.py`
- [ ] Instrument MailIngest with business metrics
- [ ] Instrument ExtractEnrich with vendor metrics
- [ ] Instrument PostToAP with transaction metrics
- [ ] Instrument Notify with notification metrics
- [ ] Update all log statements to include transaction_id
- [ ] Test custom metrics in Application Insights
- [ ] Document custom metrics

### Phase 2: Custom Dashboards

- [ ] Create Operations Dashboard JSON
- [ ] Create Business Metrics Dashboard JSON
- [ ] Create SLO Compliance Dashboard JSON
- [ ] Deploy dashboards to Azure Portal
- [ ] Share dashboard links with team
- [ ] Create dashboard access guide
- [ ] Schedule dashboard review meeting

### Phase 3: Advanced Alerting

- [ ] Create End-to-End SLO Violation alert
- [ ] Create Vendor Master Staleness alert
- [ ] Create Dependency Failure alert
- [ ] Test all new alerts
- [ ] Update alert runbook
- [ ] Configure action groups
- [ ] Document escalation procedures

### Phase 4: Synthetic Monitoring

- [ ] Deploy basic availability test
- [ ] Deploy AddVendor API check
- [ ] Configure multi-location monitoring
- [ ] Create availability alert
- [ ] Test synthetic monitoring
- [ ] Document availability tests

### Phase 5: Log Retention & Archival

- [ ] Create archive storage account
- [ ] Configure data export from Log Analytics
- [ ] Set up lifecycle management policy
- [ ] Test log archival
- [ ] Test log restoration
- [ ] Document retention policy
- [ ] Update compliance documentation

---

## Conclusion

This observability proposal provides a comprehensive monitoring solution for the Invoice Agent system, balancing operational excellence with cost-effectiveness. The phased approach allows for incremental implementation over 4-5 weeks, with immediate value from each phase.

**Key Benefits:**
- **Proactive:** Detect issues before users report them
- **Comprehensive:** Full visibility across all system components
- **Cost-effective:** ~$100-167/month for enterprise-grade monitoring
- **Scalable:** Easily accommodates growth from 50 to 500+ invoices/day
- **Actionable:** Clear alerts with documented response procedures

**Next Steps:**
1. Review and approve this proposal
2. Prioritize implementation phases
3. Assign ownership for each phase
4. Begin Phase 1 implementation
5. Schedule weekly check-ins during implementation

---

**Document Version:** 1.0.0
**Last Updated:** 2025-11-19
**Next Review:** 2025-12-19
**Owner:** DevOps Team
**Approvers:** Engineering Lead, Product Manager
