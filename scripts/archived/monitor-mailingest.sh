#!/bin/bash
# Monitor MailIngest function execution

echo "🔍 Monitoring MailIngest Function"
echo "=================================="
echo ""

# Wait until :15, :20, :25, etc (5-minute intervals)
CURRENT_MIN=$(date +%M)
CURRENT_SEC=$(date +%S)
NEXT_RUN=$((((CURRENT_MIN / 5) + 1) * 5))

if [ $NEXT_RUN -ge 60 ]; then
    NEXT_RUN=$((NEXT_RUN - 60))
fi

WAIT_MIN=$((NEXT_RUN - CURRENT_MIN))
if [ $WAIT_MIN -lt 0 ]; then
    WAIT_MIN=$((60 + WAIT_MIN))
fi

WAIT_SEC=$((WAIT_MIN * 60 - CURRENT_SEC + 70))  # Wait until 70 seconds after trigger

printf "⏰ Current time: %s\n" "$(date +%H:%M:%S)"
printf "⏰ Next trigger: :%02d:00\n" "$NEXT_RUN"
printf "⏰ Waiting %d seconds for execution...\n\n" "$WAIT_SEC"

sleep "$WAIT_SEC"

echo "📊 Checking Application Insights logs..."
echo ""

# Check traces
az monitor app-insights query \
  --app ai-invoice-agent-dev \
  --resource-group rg-invoice-agent-dev \
  --analytics-query "traces | where timestamp > ago(5m) | project timestamp, severityLevel, message | order by timestamp desc" \
  --output table

echo ""
echo "🔍 Checking for errors..."
echo ""

# Check exceptions
az monitor app-insights query \
  --app ai-invoice-agent-dev \
  --resource-group rg-invoice-agent-dev \
  --analytics-query "exceptions | where timestamp > ago(5m) | project timestamp, problemId, outerMessage | order by timestamp desc" \
  --output table

echo ""
echo "📧 Checking queue messages..."
echo ""

# Check raw-mail queue depth
STORAGE_CONN=$(az functionapp config appsettings list \
  --name func-invoice-agent-dev \
  --resource-group rg-invoice-agent-dev \
  --query "[?name=='AzureWebJobsStorage'].value" -o tsv)

if [ ! -z "$STORAGE_CONN" ]; then
    az storage message peek \
      --queue-name raw-mail \
      --connection-string "$STORAGE_CONN" \
      --num-messages 5 2>/dev/null || echo "No messages in queue or queue doesn't exist"
fi

echo ""
echo "✅ Monitoring complete"
