# Queue Inspector

Inspect Azure Storage queue message flow, depths, and poison queues for the invoice processing pipeline.

## Objective
Provide real-time visibility into queue message processing to diagnose pipeline bottlenecks, stuck messages, or processing failures.

## Parameters
- `env` (optional): Environment to check (dev/prod). Defaults to prod.
- `queue_name` (optional): Specific queue to inspect. If not provided, checks all pipeline queues.

## Instructions

### 1. Get Storage Account Details

```bash
# Get storage account name
STORAGE_ACCOUNT=$(az storage account list \
  --resource-group rg-invoice-agent-{env} \
  --query '[0].name' -o tsv)

echo "Storage Account: $STORAGE_ACCOUNT"

# Get connection string (for queue operations)
STORAGE_CONN_STR=$(az storage account show-connection-string \
  --name $STORAGE_ACCOUNT \
  --resource-group rg-invoice-agent-{env} \
  --query connectionString -o tsv)
```

---

### 2. List All Queues with Message Counts

```bash
# List all queues
az storage queue list \
  --connection-string "$STORAGE_CONN_STR" \
  --query '[].{Queue:name}' \
  --output table

# Get message count for each queue
echo "=== QUEUE DEPTHS ==="
for queue in $(az storage queue list --connection-string "$STORAGE_CONN_STR" --query '[].name' -o tsv); do
  metadata=$(az storage queue metadata show \
    --name $queue \
    --connection-string "$STORAGE_CONN_STR" 2>/dev/null)

  # Get approximate message count
  count=$(az storage message peek \
    --queue-name $queue \
    --connection-string "$STORAGE_CONN_STR" \
    --num-messages 32 2>/dev/null | jq '. | length // 0')

  echo "$queue: $count messages"
done
```

Expected queues:
- `webhook-notifications` - Graph API webhook notifications
- `raw-mail` - Email metadata + blob URL (fallback path)
- `to-post` - Enriched vendor data ready for AP
- `notify` - Formatted notification messages
- `webhook-notifications-poison` (if exists)
- `raw-mail-poison` (if exists)
- `to-post-poison` (if exists)
- `notify-poison` (if exists)

---

### 3. Peek at Messages (No Dequeue)

For each active queue, peek at messages without removing them:

```bash
# Function to peek and display message summary
inspect_queue() {
  local queue_name=$1
  echo ""
  echo "=== QUEUE: $queue_name ==="

  # Peek at up to 5 messages
  messages=$(az storage message peek \
    --queue-name $queue_name \
    --connection-string "$STORAGE_CONN_STR" \
    --num-messages 5 \
    --output json 2>/dev/null)

  if [ -z "$messages" ] || [ "$messages" == "[]" ]; then
    echo "  📭 Queue is empty"
    return
  fi

  # Parse and display message details
  echo "$messages" | jq -r '.[] | "  Message ID: \(.id)\n  Insertion Time: \(.insertionTime)\n  Dequeue Count: \(.dequeueCount)\n  Content Preview: \(.content | fromjson | tostring | .[0:100])...\n"'
}

# Inspect all main queues
inspect_queue "webhook-notifications"
inspect_queue "raw-mail"
inspect_queue "to-post"
inspect_queue "notify"
```

---

### 4. Check Poison Queues

Poison queues contain messages that failed processing 5+ times:

```bash
echo ""
echo "=== POISON QUEUES ==="

for poison_queue in webhook-notifications-poison raw-mail-poison to-post-poison notify-poison; do
  # Check if poison queue exists
  exists=$(az storage queue exists \
    --name $poison_queue \
    --connection-string "$STORAGE_CONN_STR" \
    --query exists -o tsv 2>/dev/null)

  if [ "$exists" == "true" ]; then
    count=$(az storage message peek \
      --queue-name $poison_queue \
      --connection-string "$STORAGE_CONN_STR" \
      --num-messages 32 2>/dev/null | jq '. | length // 0')

    if [ "$count" -gt 0 ]; then
      echo "⚠️ $poison_queue: $count failed messages"

      # Show first failed message for debugging
      echo "  First failed message:"
      az storage message peek \
        --queue-name $poison_queue \
        --connection-string "$STORAGE_CONN_STR" \
        --num-messages 1 \
        --output json | jq -r '.[0] | "    Dequeue Count: \(.dequeueCount)\n    Content: \(.content | fromjson | tostring)"'
    else
      echo "✅ $poison_queue: empty"
    fi
  else
    echo "✅ $poison_queue: does not exist (good - no failures)"
  fi
done
```

---

### 5. Queue Trigger Binding Validation

Verify that each function has correct queue triggers configured:

```bash
echo ""
echo "=== FUNCTION QUEUE BINDINGS ==="

# Expected bindings (from architecture)
echo "Expected Queue Triggers:"
echo "  MailWebhook (HTTP) → webhook-notifications queue"
echo "  ExtractEnrich ← webhook-notifications + raw-mail queues"
echo "  PostToAP ← to-post queue"
echo "  Notify ← notify queue"
echo "  AddVendor ← (vendor-requests queue if exists)"
echo ""

# List functions and their triggers
az functionapp function list \
  --name func-invoice-agent-{env} \
  --resource-group rg-invoice-agent-{env} \
  --query '[].{Function:name, InvokeUrl:invokeUrlTemplate}' \
  --output table
```

**Note:** To see actual binding configuration, you'd need to inspect function.json files in deployment. Check locally if available:
- `src/functions/*/function.json`

---

### 6. Message Flow Metrics

Calculate message processing metrics:

```bash
echo ""
echo "=== PIPELINE FLOW ANALYSIS ==="

# Get counts
webhook_count=$(az storage message peek --queue-name webhook-notifications --connection-string "$STORAGE_CONN_STR" --num-messages 32 2>/dev/null | jq '. | length // 0')
raw_count=$(az storage message peek --queue-name raw-mail --connection-string "$STORAGE_CONN_STR" --num-messages 32 2>/dev/null | jq '. | length // 0')
topost_count=$(az storage message peek --queue-name to-post --connection-string "$STORAGE_CONN_STR" --num-messages 32 2>/dev/null | jq '. | length // 0')
notify_count=$(az storage message peek --queue-name notify --connection-string "$STORAGE_CONN_STR" --num-messages 32 2>/dev/null | jq '. | length // 0')

echo "Message Flow:"
echo "  webhook-notifications: $webhook_count"
echo "  raw-mail: $raw_count"
echo "  ↓ ExtractEnrich processes"
echo "  to-post: $topost_count"
echo "  ↓ PostToAP processes"
echo "  notify: $notify_count"
echo "  ↓ Notify processes"
echo "  → Teams webhook"
echo ""

# Diagnose bottlenecks
if [ "$webhook_count" -gt 0 ] && [ "$topost_count" -eq 0 ]; then
  echo "⚠️ BOTTLENECK: Messages stuck in webhook-notifications"
  echo "   → ExtractEnrich function may not be running or failing"
elif [ "$topost_count" -gt 0 ] && [ "$notify_count" -eq 0 ]; then
  echo "⚠️ BOTTLENECK: Messages stuck in to-post"
  echo "   → PostToAP function may not be running or failing"
elif [ "$notify_count" -gt 0 ]; then
  echo "⚠️ BOTTLENECK: Messages stuck in notify"
  echo "   → Notify function may not be running or failing"
elif [ "$webhook_count" -eq 0 ] && [ "$raw_count" -eq 0 ] && [ "$topost_count" -eq 0 ] && [ "$notify_count" -eq 0 ]; then
  echo "✅ All queues empty - pipeline is flowing normally"
fi
```

---

### 7. Test Message Injection (Optional)

If user requests, create a test message to validate queue processing:

```bash
# Create test message for webhook-notifications queue
test_message='{
  "transaction_id": "TEST-'$(date +%s)'",
  "email_id": "test@example.com",
  "subject": "Test Invoice",
  "timestamp": "'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'"
}'

echo "Injecting test message into webhook-notifications queue..."
az storage message put \
  --queue-name webhook-notifications \
  --content "$test_message" \
  --connection-string "$STORAGE_CONN_STR"

echo "✅ Test message injected. Monitor queue depth to see if it's processed."
echo "   Run this skill again in 10 seconds to check if message was consumed."
```

---

### 8. Queue Inspector Summary Report

Provide structured output:

```
=== QUEUE INSPECTOR REPORT ===
Environment: {env}
Storage Account: {account_name}
Timestamp: {current_time}

QUEUE DEPTHS:
  webhook-notifications: {count} messages
  raw-mail: {count} messages
  to-post: {count} messages
  notify: {count} messages

POISON QUEUES:
  ✅/⚠️ webhook-notifications-poison: {count} failed messages
  ✅/⚠️ raw-mail-poison: {count} failed messages
  ✅/⚠️ to-post-poison: {count} failed messages
  ✅/⚠️ notify-poison: {count} failed messages

PIPELINE HEALTH:
  ✅ Messages flowing normally
  OR
  ⚠️ Bottleneck detected at: {queue_name}
  ❌ Pipeline stalled: No messages moving

OLDEST MESSAGE:
  Queue: {queue_name}
  Age: {duration} minutes/hours
  Dequeue Count: {count}
  Preview: {first 100 chars}

IMMEDIATE ACTIONS:
  1. {Fix for poison messages}
  2. {Fix for bottleneck}
  3. {Command to clear stuck messages if needed}
```

---

## Diagnostic Questions to Answer

This skill should help answer:

✅ **Are messages being created?**
   - Check webhook-notifications and raw-mail queues

✅ **Are messages being processed?**
   - Compare queue depths over time
   - Check if message counts decrease

✅ **Are messages failing repeatedly?**
   - Inspect poison queues
   - Look at dequeue counts

✅ **Where is the bottleneck?**
   - Identify which queue has growing backlog

✅ **What does a failed message look like?**
   - Peek at poison queue contents for error patterns

---

## Output Format

Provide:
1. **Queue Depth Table**: All queues with message counts
2. **Poison Queue Alerts**: Any failed messages
3. **Bottleneck Analysis**: Where messages are stuck
4. **Sample Messages**: Content preview for debugging
5. **Remediation Steps**: Commands to clear poison queues or restart functions

## Success Criteria

Inspection is complete when you've determined:
- [ ] Current message count in each queue
- [ ] Whether messages are flowing or stuck
- [ ] If any messages are in poison queues
- [ ] What the oldest unprocessed message contains
- [ ] Which function (if any) is not processing messages
