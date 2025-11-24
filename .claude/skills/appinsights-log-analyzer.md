# Application Insights Log Analyzer

Query and analyze Azure Application Insights logs to diagnose function execution failures and trace request flow.

## Objective
Extract and summarize recent Application Insights telemetry to identify errors, exceptions, performance issues, and trace message flow through the email processing pipeline.

## Parameters
- `env` (optional): Environment to check (dev/prod). Defaults to prod.
- `time_range` (optional): Time range to query (1h, 6h, 24h, 7d). Defaults to 1h.
- `function_name` (optional): Specific function to analyze. If not provided, analyzes all functions.
- `severity` (optional): Filter by log level (Error, Warning, Information, Verbose). Defaults to all.

## Instructions

### 1. Get Application Insights Resource

```bash
# Get App Insights resource name
APP_INSIGHTS_NAME=$(az monitor app-insights component list \
  --resource-group rg-invoice-agent-{env} \
  --query '[0].name' -o tsv)

if [ -z "$APP_INSIGHTS_NAME" ]; then
  echo "❌ Application Insights not found in resource group rg-invoice-agent-{env}"
  echo "   Function App may not have monitoring configured."
  exit 1
fi

echo "Application Insights: $APP_INSIGHTS_NAME"

# Get App ID for queries
APP_ID=$(az monitor app-insights component show \
  --app $APP_INSIGHTS_NAME \
  --resource-group rg-invoice-agent-{env} \
  --query appId -o tsv)

echo "App ID: $APP_ID"
```

---

### 2. Query Recent Exceptions

Find all exceptions in the specified time range:

```bash
echo ""
echo "=== RECENT EXCEPTIONS ==="

# Query exceptions from last hour (adjust timespan as needed)
az monitor app-insights query \
  --app $APP_ID \
  --analytics-query "
    exceptions
    | where timestamp > ago({time_range})
    | project timestamp, operation_Name, problemId, outerMessage, innermostMessage, cloud_RoleName
    | order by timestamp desc
    | take 20
  " \
  --output table
```

Expected output:
- **No exceptions**: ✅ Functions executing cleanly
- **Exceptions found**: ❌ Critical issues to investigate

Common exception patterns:
- `KeyVaultError`: Key Vault access issues
- `StorageException`: Queue/blob access issues
- `AuthenticationError`: Graph API auth issues
- `TimeoutError`: Function execution timeout

---

### 3. Query Recent Errors (Log Level)

Find all ERROR-level log entries:

```bash
echo ""
echo "=== ERROR-LEVEL LOGS ==="

az monitor app-insights query \
  --app $APP_ID \
  --analytics-query "
    traces
    | where timestamp > ago({time_range})
    | where severityLevel >= 3  // Error level
    | project timestamp, message, severityLevel, operation_Name, customDimensions
    | order by timestamp desc
    | take 20
  " \
  --output table
```

Parse `customDimensions` for structured fields:
- `transaction_id`: Correlation ID (ULID)
- `email_id`: Email being processed
- `vendor`: Extracted vendor name
- `function_name`: Which function logged the error

---

### 4. Query Function Invocations

Get execution statistics for each function:

```bash
echo ""
echo "=== FUNCTION INVOCATION SUMMARY ==="

az monitor app-insights query \
  --app $APP_ID \
  --analytics-query "
    requests
    | where timestamp > ago({time_range})
    | summarize
        Total = count(),
        Successful = countif(success == true),
        Failed = countif(success == false),
        AvgDuration = avg(duration),
        MaxDuration = max(duration)
      by operation_Name
    | project
        Function = operation_Name,
        Total,
        Successful,
        Failed,
        SuccessRate = round(100.0 * Successful / Total, 2),
        AvgDurationMs = round(AvgDuration, 2),
        MaxDurationMs = round(MaxDuration, 2)
    | order by Failed desc
  " \
  --output table
```

Analyze results:
- ✅ **100% success rate**: Function is healthy
- ⚠️ **<100% success rate**: Some failures occurring
- ❌ **0% success rate**: Function completely broken
- ⚠️ **High AvgDuration**: Performance issue or timeout risk

---

### 5. Trace Specific Transaction

If a transaction_id is known, trace its entire flow through the pipeline:

```bash
echo ""
echo "=== TRANSACTION TRACE ==="
read -p "Enter transaction_id (ULID) to trace (or press Enter to skip): " TRANSACTION_ID

if [ -n "$TRANSACTION_ID" ]; then
  az monitor app-insights query \
    --app $APP_ID \
    --analytics-query "
      union traces, requests, exceptions
      | where timestamp > ago(7d)
      | where customDimensions.transaction_id == '$TRANSACTION_ID' or operation_Id == '$TRANSACTION_ID'
      | project timestamp, itemType, message, operation_Name, severityLevel
      | order by timestamp asc
    " \
    --output table

  echo ""
  echo "Transaction Flow:"
  echo "  1. Email received (MailIngest or MailWebhook)"
  echo "  2. Message queued to webhook-notifications or raw-mail"
  echo "  3. ExtractEnrich processes → to-post queue"
  echo "  4. PostToAP processes → notify queue"
  echo "  5. Notify sends to Teams webhook"
  echo ""
  echo "Check above trace for missing steps or errors."
fi
```

---

### 6. Query Custom Dimensions (Structured Logs)

Extract structured log fields used by the application:

```bash
echo ""
echo "=== STRUCTURED LOG ANALYSIS ==="

# Get all unique custom dimensions keys
az monitor app-insights query \
  --app $APP_ID \
  --analytics-query "
    traces
    | where timestamp > ago({time_range})
    | project customDimensions
    | take 1
  " \
  --output json | jq -r '.[0].customDimensions | keys[]' 2>/dev/null

# Query specific custom dimensions
az monitor app-insights query \
  --app $APP_ID \
  --analytics-query "
    traces
    | where timestamp > ago({time_range})
    | where isnotempty(customDimensions.transaction_id)
    | project
        timestamp,
        transaction_id = customDimensions.transaction_id,
        vendor = customDimensions.vendor,
        email_id = customDimensions.email_id,
        function_name = customDimensions.function_name,
        message
    | order by timestamp desc
    | take 20
  " \
  --output table
```

Expected custom dimensions:
- `transaction_id`: ULID correlation ID
- `vendor`: Extracted vendor name
- `email_id`: Graph API email ID
- `function_name`: Function that logged the entry
- `correlation_id`: Alternative correlation field

---

### 7. Performance Analysis

Identify slow functions and potential timeout risks:

```bash
echo ""
echo "=== PERFORMANCE ANALYSIS ==="

az monitor app-insights query \
  --app $APP_ID \
  --analytics-query "
    requests
    | where timestamp > ago({time_range})
    | where duration > 5000  // Longer than 5 seconds
    | project timestamp, operation_Name, duration, success, resultCode
    | order by duration desc
    | take 10
  " \
  --output table

echo ""
echo "⚠️ Azure Functions have a default timeout of 5 minutes (300 seconds)"
echo "   Functions approaching this limit may fail with TimeoutError"
```

---

### 8. Dependency Failures

Check for failures calling external dependencies:

```bash
echo ""
echo "=== DEPENDENCY CALL FAILURES ==="

az monitor app-insights query \
  --app $APP_ID \
  --analytics-query "
    dependencies
    | where timestamp > ago({time_range})
    | where success == false
    | project timestamp, type, target, name, resultCode, duration
    | order by timestamp desc
    | take 20
  " \
  --output table
```

Expected dependencies:
- **Microsoft Graph API**: `https://graph.microsoft.com`
- **Azure Storage**: Queue/blob operations
- **Azure Table Storage**: VendorMaster, TransactionLog lookups
- **Teams Webhook**: `https://outlook.office.com/webhook/...`

Common failure patterns:
- `401/403`: Authentication/permission issues
- `404`: Resource not found (e.g., email deleted, table missing)
- `429`: Rate limiting (Graph API throttling)
- `500/503`: External service errors

---

### 9. Live Metrics Stream (Real-time)

For real-time monitoring (requires separate terminal):

```bash
echo ""
echo "=== LIVE METRICS (Real-time) ==="
echo "To view live telemetry, open Azure Portal:"
echo "https://portal.azure.com/#@/resource/subscriptions/.../resourceGroups/rg-invoice-agent-{env}/providers/microsoft.insights/components/$APP_INSIGHTS_NAME/livestream"
echo ""
echo "Or use Application Insights Live Metrics Stream in VS Code extension"
```

---

### 10. Log Analysis Summary Report

Provide structured summary:

```
=== APPLICATION INSIGHTS LOG ANALYSIS ===
Environment: {env}
App Insights: {app_name}
Time Range: Last {time_range}
Timestamp: {current_time}

EXCEPTION SUMMARY:
  Total Exceptions: {count}
  Unique Problems: {unique_count}
  Most Common: {most_common_exception_type}

ERROR LOGS:
  Total Error-level logs: {count}
  Functions with errors:
    - {function_name}: {count} errors
    - {function_name}: {count} errors

FUNCTION HEALTH:
  MailIngest:        ✅ {success_rate}% success ({total} invocations)
  MailWebhook:       ✅ {success_rate}% success ({total} invocations)
  ExtractEnrich:     ✅ {success_rate}% success ({total} invocations)
  PostToAP:          ✅ {success_rate}% success ({total} invocations)
  Notify:            ✅ {success_rate}% success ({total} invocations)
  AddVendor:         ✅ {success_rate}% success ({total} invocations)
  SubscriptionMgr:   ✅ {success_rate}% success ({total} invocations)

PERFORMANCE:
  Slowest function: {function_name} ({duration}ms avg)
  Functions >5s: {count} invocations (timeout risk)

DEPENDENCY FAILURES:
  Graph API: {count} failures
  Storage: {count} failures
  Teams Webhook: {count} failures

TOP 3 ISSUES:
  1. {Most critical issue based on frequency/severity}
  2. {Second issue}
  3. {Third issue}

RECOMMENDED ACTIONS:
  1. {Fix for top issue}
  2. {Fix for second issue}
  3. {Monitoring suggestion}
```

---

## Advanced Queries

### Query by Correlation ID
```bash
# Trace all logs for a specific operation
az monitor app-insights query \
  --app $APP_ID \
  --analytics-query "
    union traces, requests, exceptions, dependencies
    | where operation_Id == '{operation_id}'
    | project timestamp, itemType, message, operation_Name
    | order by timestamp asc
  "
```

### Count Logs by Severity
```bash
az monitor app-insights query \
  --app $APP_ID \
  --analytics-query "
    traces
    | where timestamp > ago(1h)
    | summarize count() by severityLevel
    | project Severity = case(
        severityLevel == 0, 'Verbose',
        severityLevel == 1, 'Information',
        severityLevel == 2, 'Warning',
        severityLevel == 3, 'Error',
        severityLevel == 4, 'Critical',
        'Unknown'),
      Count = count_
  "
```

### Find Missing Transactions
```bash
# Detect emails that started processing but never completed
az monitor app-insights query \
  --app $APP_ID \
  --analytics-query "
    let started = traces
      | where operation_Name == 'MailIngest' or operation_Name == 'MailWebhook'
      | where message contains 'Processing email'
      | distinct customDimensions.transaction_id;
    let completed = traces
      | where operation_Name == 'Notify'
      | where message contains 'Notification sent'
      | distinct customDimensions.transaction_id;
    started
    | join kind=leftanti completed on \$left.transaction_id == \$right.transaction_id
  "
```

---

## Diagnostic Questions to Answer

This skill should help answer:

✅ **Are functions executing at all?**
   - Check request counts

✅ **What errors are occurring?**
   - Review exceptions and error logs

✅ **Why is a specific transaction failing?**
   - Trace by transaction_id

✅ **Which function is the bottleneck?**
   - Compare success rates and durations

✅ **Are external services failing?**
   - Check dependency failures

✅ **Is the pipeline complete?**
   - Trace message flow from MailIngest → Notify

---

## Output Format

Provide:
1. **Health Score**: Overall system health (0-100%)
2. **Critical Errors**: Top 3 most frequent errors with counts
3. **Function Status**: Each function's success rate and invocation count
4. **Sample Error Logs**: 2-3 representative error messages
5. **Remediation Steps**: Specific actions to fix identified issues

## Success Criteria

Analysis is complete when you've determined:
- [ ] Which functions are executing successfully
- [ ] What errors/exceptions are occurring
- [ ] Whether the entire pipeline is processing messages
- [ ] If any external dependencies are failing
- [ ] What the root cause of failures is (auth, config, code bug, etc.)

## Notes

- Application Insights has a ~2 minute ingestion delay for logs
- Use Live Metrics for real-time debugging
- Queries use KQL (Kusto Query Language) syntax
- Time ranges: `ago(1h)`, `ago(6h)`, `ago(1d)`, `ago(7d)`
- Severity levels: 0=Verbose, 1=Info, 2=Warning, 3=Error, 4=Critical
