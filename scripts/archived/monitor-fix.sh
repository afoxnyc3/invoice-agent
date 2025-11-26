#!/bin/bash

# Automated Fix Verification Monitor
# Run this script every 5-10 minutes to track invoice processing fix progress
#
# Usage: chmod +x monitor-fix.sh && ./monitor-fix.sh

clear
echo "════════════════════════════════════════════════════════════════"
echo "📊 INVOICE PROCESSING FIX - VERIFICATION MONITOR"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Function to check subscription status
check_subscription() {
  echo "1️⃣  SUBSCRIPTION STATUS"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

  result=$(az storage entity query \
    --table-name GraphSubscriptions \
    --account-name stinvoiceagentprod 2>&1)

  if echo "$result" | grep -q "IsActive\|SubscriptionId"; then
    echo "✅ SUBSCRIPTION FOUND!"
    echo ""
    # Try to extract and display subscription details
    echo "$result" | grep -E "SubscriptionId|IsActive|ExpirationDateTime|CreatedAt" | head -10
    echo ""
    echo "Status: WEBHOOK SUBSCRIPTION ACTIVE ✨"
  else
    echo "⏳ No subscription yet (waiting for SubscriptionManager to execute)"
    echo ""
    echo "Expected: Within 60 minutes of deployment"
    echo "Next check: Run this script again in 5 minutes"
  fi
  echo ""
}

# Function to check transactions
check_transactions() {
  echo "2️⃣  PROCESSED INVOICES"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

  result=$(az storage entity query \
    --table-name InvoiceTransactions \
    --account-name stinvoiceagentprod 2>&1)

  if echo "$result" | grep -q "VendorName\|Status"; then
    count=$(echo "$result" | grep -c "RowKey")
    echo "✅ INVOICES PROCESSED: $count transactions"
    echo ""
    echo "$result" | grep -E "VendorName|Status|GLCode" | head -15
  else
    echo "⏳ No invoices processed yet"
    echo ""
    echo "Next step: Send test invoice to invoices@chelseapiers.com"
  fi
  echo ""
}

# Function to check function execution status
check_function_status() {
  echo "3️⃣  FUNCTION EXECUTION STATUS"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

  status=$(az functionapp show \
    --name func-invoice-agent-prod \
    --resource-group rg-invoice-agent-prod \
    --query "state" \
    --output tsv 2>&1)

  if [ "$status" = "Running" ]; then
    echo "✅ Function App Status: RUNNING"
  else
    echo "❌ Function App Status: $status"
  fi
  echo ""
}

# Function to suggest next actions
suggest_next_steps() {
  echo "4️⃣  NEXT STEPS"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

  result=$(az storage entity query \
    --table-name GraphSubscriptions \
    --account-name stinvoiceagentprod 2>&1)

  if echo "$result" | grep -q "IsActive"; then
    echo "🎯 Subscription is active!"
    echo ""
    echo "ACTION: Send test invoice email"
    echo "  To: invoices@chelseapiers.com"
    echo "  From: (your email)"
    echo "  Subject: Test Invoice - Adobe Inc - November 2024"
    echo "  Attachment: (any PDF)"
    echo ""
    echo "Then check again in 10 seconds for processing..."
  else
    echo "⏳ Waiting for SubscriptionManager to run..."
    echo ""
    echo "Timeline:"
    echo "  • Deployment: ✅ Complete"
    echo "  • SubscriptionManager schedule: Changed to hourly"
    echo "  • Execution: Within ~60 minutes"
    echo "  • Processing ready: Within ~70 minutes"
    echo ""
    echo "Check back in 5 minutes..."
  fi
  echo ""
}

# Run all checks
check_function_status
check_subscription
check_transactions
suggest_next_steps

echo "════════════════════════════════════════════════════════════════"
echo "💡 TIP: Run './monitor-fix.sh' again in 5 minutes to check progress"
echo "════════════════════════════════════════════════════════════════"
