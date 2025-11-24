# End-to-End Pipeline Test

Test the complete email processing pipeline from webhook notification through to Teams notification delivery.

## Objective
Inject a synthetic test message into the invoice processing pipeline and track its flow through all stages, measuring latency and verifying successful completion. Validates that all functions, queues, and integrations are working correctly.

## Parameters
- `env` (optional): Environment to test (dev/prod). Defaults to dev (safer for testing).
- `entry_point` (optional): Where to inject test message (webhook-notifications, raw-mail). Defaults to raw-mail.
- `timeout` (optional): Maximum seconds to wait for completion. Defaults to 120.

## Instructions

### 1. Get Required Resources

```bash
# Get storage account
STORAGE_ACCOUNT=$(az storage account list \
  --resource-group rg-invoice-agent-{env} \
  --query '[0].name' -o tsv)

echo "Storage Account: $STORAGE_ACCOUNT"

# Get connection string
STORAGE_CONN_STR=$(az storage account show-connection-string \
  --name $STORAGE_ACCOUNT \
  --resource-group rg-invoice-agent-{env} \
  --query connectionString -o tsv)

# Get Function App
FUNCTION_APP=$(az functionapp list \
  --resource-group rg-invoice-agent-{env} \
  --query '[0].name' -o tsv)

echo "Function App: $FUNCTION_APP"

# Get Application Insights (if configured)
APP_INSIGHTS=$(az monitor app-insights component list \
  --resource-group rg-invoice-agent-{env} \
  --query '[0].name' -o tsv 2>/dev/null)

if [ -n "$APP_INSIGHTS" ]; then
  echo "Application Insights: $APP_INSIGHTS"
  APP_ID=$(az monitor app-insights component show \
    --app $APP_INSIGHTS \
    --resource-group rg-invoice-agent-{env} \
    --query appId -o tsv)
fi
```

---

### 2. Generate Test Transaction ID

Create unique identifier for tracking:

```bash
echo ""
echo "=== GENERATING TEST TRANSACTION ==="

# Generate ULID-like test ID (timestamp-based for sorting)
TEST_ID="TEST-$(date +%s)-$(openssl rand -hex 4 | tr '[:lower:]' '[:upper:]')"
echo "Transaction ID: $TEST_ID"

# Record start time
START_TIME=$(date +%s)
echo "Start Time: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
```

---

### 3. Create Test Message

Build message payload based on entry point:

```bash
echo ""
echo "=== CREATING TEST MESSAGE ==="

# Entry point determines message structure
case "${entry_point:-raw-mail}" in
  webhook-notifications)
    echo "Entry Point: webhook-notifications queue (webhook path)"

    TEST_MESSAGE='{
      "id": "'$TEST_ID'",
      "type": "webhook",
      "subscription_id": "test-subscription",
      "resource": "users/test@example.com/messages/TEST-MSG-'$(date +%s)'",
      "change_type": "created",
      "timestamp": "'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'"
    }'

    ENTRY_QUEUE="webhook-notifications"
    ;;

  raw-mail)
    echo "Entry Point: raw-mail queue (post-webhook path)"

    TEST_MESSAGE='{
      "id": "'$TEST_ID'",
      "sender": "test-vendor@example.com",
      "subject": "Test Invoice - Pipeline Validation",
      "blob_url": "https://'$STORAGE_ACCOUNT'.blob.core.windows.net/invoices/test/placeholder.pdf",
      "received_at": "'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'",
      "original_message_id": "TEST-MSG-'$(date +%s)'",
      "vendor_name": null
    }'

    ENTRY_QUEUE="raw-mail"
    ;;

  *)
    echo "❌ Invalid entry point: ${entry_point}"
    echo "   Valid options: webhook-notifications, raw-mail"
    exit 1
    ;;
esac

echo "Message Structure:"
echo "$TEST_MESSAGE" | jq '.'
```

---

### 4. Inject Test Message into Queue

```bash
echo ""
echo "=== INJECTING TEST MESSAGE ==="

# Encode message for queue (base64)
MESSAGE_ENCODED=$(echo "$TEST_MESSAGE" | base64)

# Send to queue
az storage message put \
  --queue-name "$ENTRY_QUEUE" \
  --content "$MESSAGE_ENCODED" \
  --connection-string "$STORAGE_CONN_STR" \
  --time-to-live 300 \
  --output none

if [ $? -eq 0 ]; then
  echo "✅ Test message injected into $ENTRY_QUEUE queue"
  echo "   Transaction ID: $TEST_ID"
else
  echo "❌ Failed to inject message"
  exit 1
fi

# Record injection time
INJECT_TIME=$(date +%s)
```

---

### 5. Monitor Queue Flow

Track message through all queues:

```bash
echo ""
echo "=== MONITORING PIPELINE FLOW ==="
echo "Expected Flow:"

if [ "$ENTRY_QUEUE" == "webhook-notifications" ]; then
  echo "  webhook-notifications → MailWebhookProcessor → raw-mail"
  EXPECTED_QUEUES=("webhook-notifications" "raw-mail" "to-post" "notify")
else
  echo "  raw-mail → ExtractEnrich → to-post → PostToAP → notify → Notify"
  EXPECTED_QUEUES=("raw-mail" "to-post" "notify")
fi

echo ""
echo "Polling queues (timeout: ${timeout:-120} seconds)..."

# Function to check if message is in queue
check_queue_for_message() {
  local queue_name=$1
  local search_id=$2

  # Peek at messages (up to 32)
  messages=$(az storage message peek \
    --queue-name "$queue_name" \
    --connection-string "$STORAGE_CONN_STR" \
    --num-messages 32 \
    --output json 2>/dev/null)

  # Search for our transaction ID in messages
  echo "$messages" | jq -r '.[].content' | while read -r msg; do
    # Decode base64
    decoded=$(echo "$msg" | base64 -d 2>/dev/null)
    if echo "$decoded" | grep -q "$search_id"; then
      return 0
    fi
  done

  return 1
}

# Poll for message flow
TIMEOUT=${timeout:-120}
elapsed=0
current_stage=0

declare -A stage_times

while [ $elapsed -lt $TIMEOUT ]; do
  sleep 2
  elapsed=$((elapsed + 2))

  # Check if message moved to next queue
  if [ $current_stage -lt ${#EXPECTED_QUEUES[@]} ]; then
    next_queue="${EXPECTED_QUEUES[$current_stage]}"

    # Get queue depth
    depth=$(az storage queue metadata show \
      --name "$next_queue" \
      --connection-string "$STORAGE_CONN_STR" \
      --query 'approximateMessageCount' -o tsv 2>/dev/null)

    # If message left current queue, it's progressing
    if [ "$current_stage" -gt 0 ]; then
      prev_queue="${EXPECTED_QUEUES[$((current_stage - 1))]}"
      prev_depth=$(az storage queue metadata show \
        --name "$prev_queue" \
        --connection-string "$STORAGE_CONN_STR" \
        --query 'approximateMessageCount' -o tsv 2>/dev/null)

      # Message moved if previous queue decreased
      # (Simplified - actual check would peek messages)
    fi

    printf "\r[%3ds] %s: %s messages" "$elapsed" "$next_queue" "${depth:-0}"
  fi

  # Check if completely processed (no messages in any queue)
  all_empty=true
  for queue in "${EXPECTED_QUEUES[@]}"; do
    depth=$(az storage queue metadata show \
      --name "$queue" \
      --connection-string "$STORAGE_CONN_STR" \
      --query 'approximateMessageCount' -o tsv 2>/dev/null)

    if [ "${depth:-0}" -gt 0 ]; then
      all_empty=false
      break
    fi
  done

  if [ "$all_empty" == "true" ]; then
    echo ""
    echo "✅ All queues empty - message processed"
    break
  fi
done

echo ""
TOTAL_TIME=$(($(date +%s) - $START_TIME))
echo "Total elapsed time: ${TOTAL_TIME}s"
```

---

### 6. Verify Transaction Record

Check if transaction was recorded in InvoiceTransactions table:

```bash
echo ""
echo "=== VERIFYING TRANSACTION RECORD ==="

# Get current month partition key
PARTITION_KEY=$(date +%Y%m)

# Query InvoiceTransactions table
az storage entity query \
  --table-name InvoiceTransactions \
  --connection-string "$STORAGE_CONN_STR" \
  --filter "PartitionKey eq '$PARTITION_KEY' and RowKey eq '$TEST_ID'" \
  --output json > /tmp/transaction.json

record_count=$(cat /tmp/transaction.json | jq '. | length')

if [ "$record_count" -eq 1 ]; then
  echo "✅ Transaction record found in InvoiceTransactions table"

  # Extract key fields
  status=$(cat /tmp/transaction.json | jq -r '.[0].Status')
  vendor=$(cat /tmp/transaction.json | jq -r '.[0].VendorName')
  gl_code=$(cat /tmp/transaction.json | jq -r '.[0].GLCode')
  processed_at=$(cat /tmp/transaction.json | jq -r '.[0].ProcessedAt')

  echo "   Status: $status"
  echo "   Vendor: $vendor"
  echo "   GL Code: $gl_code"
  echo "   Processed At: $processed_at"

  if [ "$status" == "processed" ]; then
    echo "   ✅ Status: Processed successfully"
  elif [ "$status" == "unknown" ]; then
    echo "   ⚠️ Status: Unknown vendor (expected for test message)"
  else
    echo "   ❌ Status: Error or unexpected value"
  fi
else
  echo "❌ Transaction record NOT found"
  echo "   Message may still be processing or failed"
fi
```

---

### 7. Check Poison Queues

Verify test message didn't fail:

```bash
echo ""
echo "=== CHECKING POISON QUEUES ==="

poison_queues=(
  "webhook-notifications-poison"
  "raw-mail-poison"
  "to-post-poison"
  "notify-poison"
)

found_in_poison=false

for poison_queue in "${poison_queues[@]}"; do
  # Check if poison queue exists
  exists=$(az storage queue exists \
    --name "$poison_queue" \
    --connection-string "$STORAGE_CONN_STR" \
    --query exists -o tsv 2>/dev/null)

  if [ "$exists" == "true" ]; then
    # Check for messages
    messages=$(az storage message peek \
      --queue-name "$poison_queue" \
      --connection-string "$STORAGE_CONN_STR" \
      --num-messages 10 \
      --output json 2>/dev/null)

    # Search for our test ID
    if echo "$messages" | jq -r '.[].content' | base64 -d 2>/dev/null | grep -q "$TEST_ID"; then
      echo "❌ Test message found in $poison_queue"
      found_in_poison=true
    fi
  fi
done

if [ "$found_in_poison" == "false" ]; then
  echo "✅ No test messages in poison queues"
fi
```

---

### 8. Query Application Insights Logs

If Application Insights available, query for test transaction logs:

```bash
if [ -n "$APP_ID" ]; then
  echo ""
  echo "=== APPLICATION INSIGHTS LOGS ==="

  # Query traces for our transaction ID
  az monitor app-insights query \
    --app "$APP_ID" \
    --analytics-query "
      traces
      | where timestamp > ago(5m)
      | where message contains '$TEST_ID' or customDimensions.transaction_id == '$TEST_ID'
      | project timestamp, message, severityLevel, operation_Name
      | order by timestamp asc
    " \
    --output table 2>/dev/null

  # Query for any errors
  echo ""
  echo "Checking for errors..."

  errors=$(az monitor app-insights query \
    --app "$APP_ID" \
    --analytics-query "
      exceptions
      | where timestamp > ago(5m)
      | where message contains '$TEST_ID'
      | project timestamp, operation_Name, problemId, outerMessage
    " \
    --output table 2>/dev/null)

  if [ -n "$errors" ]; then
    echo "⚠️ Errors found:"
    echo "$errors"
  else
    echo "✅ No errors found for test transaction"
  fi
else
  echo ""
  echo "ℹ️  Application Insights not configured - skipping log analysis"
fi
```

---

### 9. Measure Stage Latencies

Calculate time spent in each stage:

```bash
echo ""
echo "=== LATENCY ANALYSIS ==="

if [ "$record_count" -eq 1 ]; then
  processed_at=$(cat /tmp/transaction.json | jq -r '.[0].ProcessedAt')
  processed_epoch=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$processed_at" "+%s" 2>/dev/null || echo "0")

  if [ "$processed_epoch" -gt 0 ]; then
    total_latency=$((processed_epoch - START_TIME))

    echo "Pipeline Timing:"
    echo "  Start:    $(date -r $START_TIME -u +"%Y-%m-%dT%H:%M:%SZ")"
    echo "  Complete: $(date -r $processed_epoch -u +"%Y-%m-%dT%H:%M:%SZ")"
    echo "  Duration: ${total_latency}s"
    echo ""

    # Compare to SLA
    if [ "$total_latency" -lt 60 ]; then
      echo "✅ Within SLA (<60 seconds)"
    else
      echo "⚠️ Exceeded SLA target (${total_latency}s > 60s)"
    fi

    # Categorize performance
    if [ "$total_latency" -lt 10 ]; then
      echo "   Performance: Excellent (<10s)"
    elif [ "$total_latency" -lt 30 ]; then
      echo "   Performance: Good (<30s)"
    elif [ "$total_latency" -lt 60 ]; then
      echo "   Performance: Acceptable (<60s)"
    else
      echo "   Performance: Slow (>60s)"
    fi
  fi
else
  echo "⚠️ Cannot calculate latency - no transaction record"
fi
```

---

### 10. Cleanup Test Data

Offer to clean up test transaction:

```bash
echo ""
echo "=== CLEANUP ==="

read -p "Delete test transaction record? (y/N): " cleanup_response

if [ "$cleanup_response" == "y" ] || [ "$cleanup_response" == "Y" ]; then
  az storage entity delete \
    --table-name InvoiceTransactions \
    --partition-key "$PARTITION_KEY" \
    --row-key "$TEST_ID" \
    --connection-string "$STORAGE_CONN_STR" \
    --if-match "*" \
    --output none 2>/dev/null

  if [ $? -eq 0 ]; then
    echo "✅ Test transaction record deleted"
  else
    echo "ℹ️  No transaction record to delete (may have already been removed)"
  fi
else
  echo "ℹ️  Test transaction record retained for inspection"
  echo "   PartitionKey: $PARTITION_KEY"
  echo "   RowKey: $TEST_ID"
fi
```

---

### 11. Pipeline Test Summary Report

Provide comprehensive test results:

```
=== END-TO-END PIPELINE TEST REPORT ===
Environment: {env}
Transaction ID: {test_id}
Entry Point: {entry_queue}
Start Time: {start_time}

TEST EXECUTION:
  ✅ Test message created
  ✅ Injected into {entry_queue} queue
  ✅ Monitoring started

QUEUE FLOW:
  {entry_queue}: ✅ Message processed
  raw-mail: ✅ Message processed
  to-post: ✅ Message processed
  notify: ✅ Message processed

TRANSACTION RECORD:
  ✅/❌ Record created: {yes/no}
  ✅/⚠️/❌ Status: {processed/unknown/error}
  Vendor: {vendor_name}
  GL Code: {gl_code}

POISON QUEUES:
  ✅ No failed messages

APPLICATION INSIGHTS:
  ✅ Logs found for transaction
  ✅/❌ No errors / {error_count} errors

PERFORMANCE:
  Total Duration: {total_latency}s
  SLA Target: <60s
  Status: ✅ Within SLA / ⚠️ Exceeded SLA
  Rating: Excellent/Good/Acceptable/Slow

OVERALL RESULT: ✅ PASS / ⚠️ PARTIAL / ❌ FAIL

PASS CRITERIA:
  [✅/❌] Message processed through all queues
  [✅/❌] Transaction record created
  [✅/❌] No poison queue messages
  [✅/❌] Completed within 60 seconds
  [✅/❌] No exceptions in logs

ISSUES FOUND:
  1. {Issue description if any}
  2. {Issue description if any}

RECOMMENDATIONS:
  - {Recommendation 1}
  - {Recommendation 2}

NEXT STEPS:
  - Use appinsights-log-analyzer to investigate errors
  - Use queue-inspector to check for backlog
  - Use azure-health-check to verify configuration
```

---

## Diagnostic Questions to Answer

This skill should help answer:

✅ **Is the complete pipeline working?**
   - Track test message from entry to completion

✅ **What is the end-to-end latency?**
   - Measure time from injection to completion

✅ **Where is the bottleneck?**
   - Identify which queue has delays

✅ **Are all functions processing correctly?**
   - Verify each stage completes

✅ **Is the system meeting SLA?**
   - Compare against <60 second target

---

## Output Format

Provide:
1. **Test Status**: Pass/Partial/Fail with explanation
2. **Queue Flow Diagram**: Visual representation of message flow
3. **Latency Breakdown**: Time spent in each stage
4. **Transaction Verification**: Database record details
5. **Recommendations**: Actions to improve performance or fix issues

## Success Criteria

Pipeline test is successful when:
- [ ] Test message successfully injected
- [ ] Message processed through all queues
- [ ] Transaction record created in InvoiceTransactions
- [ ] No messages in poison queues
- [ ] Total latency <60 seconds
- [ ] No exceptions in Application Insights

## Notes

- Use `dev` environment for testing (safer)
- Test message will appear as "unknown" vendor (expected)
- Clean up test data after validation
- Run during off-peak hours to avoid interfering with production
- Entry point `raw-mail` is simpler (skips Graph API calls)
- Entry point `webhook-notifications` tests full webhook path
- Timeout default 120s allows for retries and backlog
