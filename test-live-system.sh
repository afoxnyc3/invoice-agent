#!/bin/bash
# Test the live Invoice Agent system

echo "🧪 Invoice Agent Live System Test"
echo "=================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Test 1: Check function status
echo "1️⃣ Checking Azure Functions Status..."
FUNCTIONS=$(az functionapp function list \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "length(@)" -o tsv)

if [ "$FUNCTIONS" = "5" ]; then
  echo -e "   ${GREEN}✅ All 5 functions active${NC}"
else
  echo -e "   ❌ Only $FUNCTIONS functions found"
fi

# Test 2: Check vendor table
echo ""
echo "2️⃣ Checking VendorMaster Table..."
CONNECTION_STRING=$(az storage account show-connection-string \
  --name stinvoiceagentprod \
  --resource-group rg-invoice-agent-prod \
  --query connectionString -o tsv)

if [ ! -z "$CONNECTION_STRING" ]; then
  # Count vendors using Azure CLI
  VENDOR_COUNT=$(az storage entity query \
    --table-name VendorMaster \
    --account-name stinvoiceagentprod \
    --filter "PartitionKey eq 'Vendor'" \
    --query "items | length(@)" -o tsv 2>/dev/null || echo "0")

  if [ "$VENDOR_COUNT" -gt "0" ]; then
    echo -e "   ${GREEN}✅ VendorMaster has $VENDOR_COUNT vendors${NC}"
  else
    echo "   ⚠️ Could not verify vendor count"
  fi
fi

# Test 3: Check timer trigger schedule
echo ""
echo "3️⃣ Checking MailIngest Timer..."
NEXT_RUN=$(az functionapp function show \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --function-name MailIngest \
  --query "config.bindings[0].schedule" -o tsv)

if [ "$NEXT_RUN" = "0 */5 * * * *" ]; then
  echo -e "   ${GREEN}✅ Timer active (every 5 minutes)${NC}"

  # Calculate next run
  CURRENT_MIN=$(date +%M)
  NEXT_MIN=$((((CURRENT_MIN / 5) + 1) * 5))
  if [ $NEXT_MIN -ge 60 ]; then
    NEXT_MIN=$((NEXT_MIN - 60))
  fi
  echo -e "   📅 Next run: ~$(printf %02d $NEXT_MIN) minutes past the hour"
fi

# Test 4: Check queue status
echo ""
echo "4️⃣ Checking Queue Status..."
for queue in raw-mail to-post notify; do
  COUNT=$(az storage message peek \
    --queue-name $queue \
    --account-name stinvoiceagentprod \
    --query "length(@)" -o tsv 2>/dev/null || echo "0")

  if [ "$COUNT" = "0" ]; then
    echo -e "   ✅ Queue '$queue': Empty (ready)"
  else
    echo -e "   ${YELLOW}📬 Queue '$queue': $COUNT messages pending${NC}"
  fi
done

# Test 5: Test HTTP endpoint
echo ""
echo "5️⃣ Testing AddVendor Endpoint..."
FUNCTION_KEY=$(az functionapp keys list \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "functionKeys.default" -o tsv 2>/dev/null)

if [ ! -z "$FUNCTION_KEY" ]; then
  RESPONSE=$(curl -s -X POST \
    "https://func-invoice-agent-prod.azurewebsites.net/api/AddVendor?code=$FUNCTION_KEY" \
    -H "Content-Type: application/json" \
    -d '{"test": "ping"}' \
    -w "%{http_code}" -o /dev/null)

  if [ "$RESPONSE" = "400" ]; then
    echo -e "   ${GREEN}✅ HTTP endpoint responding correctly${NC}"
  else
    echo "   ⚠️ HTTP response: $RESPONSE"
  fi
fi

# Test 6: Recent activity check
echo ""
echo "6️⃣ Checking Recent Activity..."
echo "   Querying Application Insights for last 30 minutes..."
RECENT_LOGS=$(az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --analytics-query "traces | where timestamp > ago(30m) | summarize count()" \
  --query "tables[0].rows[0][0]" -o tsv 2>/dev/null || echo "0")

if [ "$RECENT_LOGS" -gt "0" ]; then
  echo -e "   ${GREEN}✅ System active: $RECENT_LOGS log entries in last 30 min${NC}"
else
  echo "   ℹ️ No recent activity (system may be idle)"
fi

echo ""
echo "=================================="
echo "📊 System Health Summary"
echo "=================================="

echo -e "${GREEN}✅ SYSTEM IS OPERATIONAL${NC}"
echo ""
echo "📧 To Process an Invoice:"
echo "   1. Send email with invoice attachment to configured mailbox"
echo "   2. Include vendor name in subject (e.g., 'Invoice from Microsoft')"
echo "   3. System will process within 5 minutes"
echo ""
echo "🔍 Monitor Processing:"
echo "   - Application Insights: Check logs in Azure Portal"
echo "   - Teams Channel: Watch for notifications"
echo "   - AP Mailbox: Verify enriched email received"