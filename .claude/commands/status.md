# /status - Health Monitor

Check the health and performance of the invoice processing system.

## Actions

1. **Check system health**
   - Function App status
   - Queue depths
   - Storage availability
   - Key Vault access
   - Teams webhook status

2. **Display metrics**
   - Invoices processed today
   - Unknown vendor rate
   - Average processing time
   - Error rate
   - Queue backlogs

3. **Show recent transactions**
   - Last 10 processed invoices
   - Recent errors
   - Unknown vendors
   - Processing times

4. **Check SLOs**
   - Auto-routing rate (target ≥80%)
   - Processing time (target ≤60s)
   - Error rate (target ≤1%)
   - Unknown vendor rate (target ≤10%)

5. **Generate daily summary**
   - Total processed
   - Success rate
   - Common vendors
   - Issues requiring attention

## Status Check Implementation

When user types `/status [environment]`:

```python
#!/usr/bin/env python3
# Check system status

import os
import sys
from datetime import datetime, timedelta
from azure.data.tables import TableServiceClient
from azure.storage.queue import QueueServiceClient
from azure.monitor.query import LogsQueryClient
from azure.identity import DefaultAzureCredential
import requests
import json

def check_status(environment: str = "dev"):
    """Check invoice agent system status."""

    print(f"🔍 Invoice Agent Status - {environment.upper()}")
    print("=" * 50)

    # 1. Function App Health
    print("\n📊 Function App Health:")
    function_app = f"func-invoice-agent-{environment}"
    try:
        url = f"https://{function_app}.azurewebsites.net/api/health"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            print(f"  ✅ Function App: Online")
        else:
            print(f"  ⚠️ Function App: Status {response.status_code}")
    except:
        print(f"  ❌ Function App: Offline")

    # 2. Queue Status
    print("\n📬 Queue Status:")
    conn_str = os.environ.get(f"AZURE_STORAGE_CONNECTION_STRING_{environment.upper()}")
    queue_service = QueueServiceClient.from_connection_string(conn_str)

    queues = ["raw-mail", "to-post", "notify"]
    for queue_name in queues:
        try:
            queue = queue_service.get_queue_client(queue_name)
            properties = queue.get_queue_properties()
            count = properties.approximate_message_count
            status = "✅" if count < 10 else "⚠️" if count < 50 else "❌"
            print(f"  {status} {queue_name}: {count} messages")
        except:
            print(f"  ❌ {queue_name}: Not accessible")

    # 3. Transaction Metrics
    print("\n📈 Today's Metrics:")
    table_service = TableServiceClient.from_connection_string(conn_str)
    transactions = table_service.get_table_client("InvoiceTransactions")

    # Get today's transactions
    today = datetime.utcnow().strftime("%Y%m")
    filter_query = f"PartitionKey eq '{today}'"

    try:
        entities = list(transactions.query_entities(filter_query))
        total = len(entities)
        processed = sum(1 for e in entities if e.get("status") == "processed")
        unknown = sum(1 for e in entities if e.get("status") == "unknown")
        errors = sum(1 for e in entities if e.get("status") == "error")

        print(f"  Total Processed: {total}")
        print(f"  ✅ Successful: {processed} ({processed/total*100:.1f}%)")
        print(f"  ⚠️ Unknown Vendors: {unknown} ({unknown/total*100:.1f}%)")
        print(f"  ❌ Errors: {errors} ({errors/total*100:.1f}%)")

        # Calculate average processing time
        processing_times = []
        for entity in entities[:10]:  # Sample last 10
            if entity.get("created_at") and entity.get("processed_at"):
                created = datetime.fromisoformat(entity["created_at"])
                processed = datetime.fromisoformat(entity["processed_at"])
                delta = (processed - created).total_seconds()
                processing_times.append(delta)

        if processing_times:
            avg_time = sum(processing_times) / len(processing_times)
            print(f"  ⏱️ Avg Processing: {avg_time:.1f}s")

    except Exception as e:
        print(f"  ❌ Could not fetch metrics: {e}")

    # 4. SLO Status
    print("\n🎯 SLO Status:")
    if total > 0:
        auto_route_rate = processed / total * 100
        unknown_rate = unknown / total * 100
        error_rate = errors / total * 100

        print(f"  Auto-routing: {auto_route_rate:.1f}% {'✅' if auto_route_rate >= 80 else '❌'} (target ≥80%)")
        print(f"  Unknown vendors: {unknown_rate:.1f}% {'✅' if unknown_rate <= 10 else '❌'} (target ≤10%)")
        print(f"  Error rate: {error_rate:.1f}% {'✅' if error_rate <= 1 else '❌'} (target ≤1%)")
        if processing_times:
            print(f"  Processing time: {avg_time:.1f}s {'✅' if avg_time <= 60 else '❌'} (target ≤60s)")

    # 5. Recent Transactions
    print("\n📋 Recent Transactions (Last 5):")
    recent = sorted(entities, key=lambda x: x.get("processed_at", ""), reverse=True)[:5]
    for entity in recent:
        vendor = entity.get("vendor_name", "Unknown")
        status = entity.get("status", "unknown")
        gl_code = entity.get("gl_code", "N/A")
        timestamp = entity.get("processed_at", "")[:19]
        icon = "✅" if status == "processed" else "⚠️" if status == "unknown" else "❌"
        print(f"  {icon} {timestamp} - {vendor} (GL: {gl_code})")

    # 6. Teams Webhook Status
    print("\n💬 Teams Notification Status:")
    try:
        webhook_url = os.environ.get("TEAMS_WEBHOOK_URL")
        if webhook_url:
            # Don't actually post, just check if URL is reachable
            response = requests.head(webhook_url, timeout=3)
            print(f"  ✅ Teams webhook: Configured")
        else:
            print(f"  ⚠️ Teams webhook: Not configured")
    except:
        print(f"  ❌ Teams webhook: Unreachable")

    # 7. Alerts
    print("\n⚠️ Alerts:")
    alerts = []

    if queue_service:
        for queue_name in queues:
            try:
                queue = queue_service.get_queue_client(queue_name)
                props = queue.get_queue_properties()
                if props.approximate_message_count > 50:
                    alerts.append(f"High queue depth: {queue_name} ({props.approximate_message_count})")
            except:
                pass

    if unknown_rate > 15:
        alerts.append(f"High unknown vendor rate: {unknown_rate:.1f}%")

    if error_rate > 2:
        alerts.append(f"High error rate: {error_rate:.1f}%")

    if processing_times and avg_time > 90:
        alerts.append(f"Slow processing: {avg_time:.1f}s average")

    if alerts:
        for alert in alerts:
            print(f"  🔴 {alert}")
    else:
        print(f"  ✅ No alerts")

    print("\n" + "=" * 50)
    print("Status check complete")

if __name__ == "__main__":
    environment = sys.argv[1] if len(sys.argv) > 1 else "dev"
    check_status(environment)
```

## Status Output Example

```
🔍 Invoice Agent Status - PRODUCTION
==================================================

📊 Function App Health:
  ✅ Function App: Online

📬 Queue Status:
  ✅ raw-mail: 2 messages
  ✅ to-post: 0 messages
  ✅ notify: 1 messages

📈 Today's Metrics:
  Total Processed: 42
  ✅ Successful: 38 (90.5%)
  ⚠️ Unknown Vendors: 3 (7.1%)
  ❌ Errors: 1 (2.4%)
  ⏱️ Avg Processing: 45.3s

🎯 SLO Status:
  Auto-routing: 90.5% ✅ (target ≥80%)
  Unknown vendors: 7.1% ✅ (target ≤10%)
  Error rate: 2.4% ❌ (target ≤1%)
  Processing time: 45.3s ✅ (target ≤60s)

📋 Recent Transactions (Last 5):
  ✅ 2024-11-09 14:30:15 - Adobe Inc (GL: 6100)
  ✅ 2024-11-09 14:25:42 - Microsoft Corp (GL: 6100)
  ⚠️ 2024-11-09 14:20:18 - Unknown (GL: N/A)
  ✅ 2024-11-09 14:15:33 - AWS (GL: 6110)
  ✅ 2024-11-09 14:10:27 - Zoom (GL: 6120)

💬 Teams Notification Status:
  ✅ Teams webhook: Configured

⚠️ Alerts:
  🔴 High error rate: 2.4%

==================================================
Status check complete
```

## Quick Status (Summary Only)

```bash
/status quick

Output:
✅ System: Online
📊 Today: 42 processed (90.5% success)
⚠️ Issues: 1 alert (high error rate)
⏱️ Avg Time: 45.3s
```

## Daily Summary Report

```python
def generate_daily_summary():
    """Generate daily summary for Teams."""

    summary = {
        "@type": "MessageCard",
        "themeColor": "00FF00",
        "text": "📊 Daily Invoice Processing Summary",
        "sections": [{
            "facts": [
                {"name": "Date", "value": datetime.now().strftime("%Y-%m-%d")},
                {"name": "Total Processed", "value": "42"},
                {"name": "Success Rate", "value": "90.5%"},
                {"name": "Unknown Vendors", "value": "3"},
                {"name": "Errors", "value": "1"},
                {"name": "Avg Processing Time", "value": "45.3s"}
            ]
        }]
    }

    # Post to Teams
    requests.post(TEAMS_WEBHOOK_URL, json=summary)
```

## Monitoring Queries

```kusto
// Application Insights queries

// Processing time trend
customMetrics
| where name == "InvoiceProcessingTime"
| where timestamp > ago(24h)
| summarize avg(value), percentile(value, 95) by bin(timestamp, 1h)
| render timechart

// Error rate by function
exceptions
| where timestamp > ago(24h)
| where cloud_RoleName contains "invoice-agent"
| summarize count() by operation_Name
| order by count_ desc

// Queue depth over time
customMetrics
| where name contains "QueueDepth"
| where timestamp > ago(24h)
| summarize avg(value) by name, bin(timestamp, 15m)
| render timechart
```

## Health Endpoints

```python
# Function App health endpoint
@app.route("/api/health")
def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": os.environ.get("BUILD_VERSION", "unknown"),
        "environment": os.environ.get("ENVIRONMENT", "unknown")
    }
```

## Alert Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Queue Depth | >50 | >100 |
| Unknown Vendor Rate | >15% | >25% |
| Error Rate | >2% | >5% |
| Processing Time | >90s | >120s |
| Function App Down | N/A | Immediate |

## Success Criteria
- All components online
- Queue depths normal (<10)
- SLOs being met
- No critical alerts
- Recent transactions successful