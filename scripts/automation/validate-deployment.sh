#!/bin/bash
# Deployment Validation Script
# Validates deployment after slot swap or new release
# Usage: ./validate-deployment.sh [--environment prod] [--slot staging]

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Default values
ENVIRONMENT="prod"
SLOT=""
TIMEOUT=300  # 5 minutes
CHECK_INTERVAL=10

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --slot)
            SLOT="$2"
            shift 2
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--environment ENV] [--slot SLOT] [--timeout SECONDS]"
            exit 1
            ;;
    esac
done

# Set resource names
RESOURCE_GROUP="rg-invoice-agent-${ENVIRONMENT}"
FUNCTION_APP="func-invoice-agent-${ENVIRONMENT}"
STORAGE_ACCOUNT="stinvoiceagent${ENVIRONMENT}"
APP_INSIGHTS="ai-invoice-agent-${ENVIRONMENT}"

# Validation counters
CHECKS_PASSED=0
CHECKS_FAILED=0

check_pass() {
    echo -e "  ${GREEN}✅${NC} $1"
    ((CHECKS_PASSED++))
}

check_fail() {
    echo -e "  ${RED}❌${NC} $1"
    ((CHECKS_FAILED++))
}

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║          Invoice Agent Deployment Validation                 ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "Environment: $ENVIRONMENT"
[ -n "$SLOT" ] && echo "Slot: $SLOT" || echo "Slot: production"
echo "Validation started: $(date)"
echo ""

# ============================================================================
# 1. WAIT FOR APP TO BE READY
# ============================================================================
echo "1. Waiting for Function App to be ready..."

ELAPSED=0
APP_READY=false

while [ $ELAPSED -lt $TIMEOUT ]; do
    if [ -n "$SLOT" ]; then
        STATE=$(az functionapp show --name "$FUNCTION_APP" --resource-group "$RESOURCE_GROUP" --slot "$SLOT" --query "state" -o tsv 2>/dev/null || echo "Unknown")
    else
        STATE=$(az functionapp show --name "$FUNCTION_APP" --resource-group "$RESOURCE_GROUP" --query "state" -o tsv 2>/dev/null || echo "Unknown")
    fi

    if [ "$STATE" = "Running" ]; then
        APP_READY=true
        break
    fi

    echo "   State: $STATE, waiting... ($ELAPSED/$TIMEOUT seconds)"
    sleep $CHECK_INTERVAL
    ((ELAPSED += CHECK_INTERVAL))
done

if [ "$APP_READY" = true ]; then
    check_pass "Function App is running"
else
    check_fail "Function App did not reach Running state within $TIMEOUT seconds"
    exit 1
fi

# ============================================================================
# 2. VERIFY FUNCTION COUNT
# ============================================================================
echo ""
echo "2. Verifying deployed functions..."

if [ -n "$SLOT" ]; then
    FUNCTION_COUNT=$(az functionapp function list --name "$FUNCTION_APP" --resource-group "$RESOURCE_GROUP" --slot "$SLOT" --query "length(@)" -o tsv)
else
    FUNCTION_COUNT=$(az functionapp function list --name "$FUNCTION_APP" --resource-group "$RESOURCE_GROUP" --query "length(@)" -o tsv)
fi

if [ "$FUNCTION_COUNT" -eq 5 ]; then
    check_pass "All 5 functions deployed (MailIngest, ExtractEnrich, PostToAP, Notify, AddVendor)"
else
    check_fail "Function count mismatch: found $FUNCTION_COUNT, expected 5"
fi

# ============================================================================
# 3. TEST HTTP ENDPOINT
# ============================================================================
echo ""
echo "3. Testing HTTP endpoint..."

if [ -n "$SLOT" ]; then
    ENDPOINT="https://${FUNCTION_APP}-${SLOT}.azurewebsites.net"
else
    ENDPOINT="https://${FUNCTION_APP}.azurewebsites.net"
fi

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$ENDPOINT" || echo "000")

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "401" ]; then
    check_pass "Endpoint reachable (HTTP $HTTP_CODE)"
else
    check_fail "Endpoint unreachable or error (HTTP $HTTP_CODE)"
fi

# ============================================================================
# 4. VERIFY APPLICATION SETTINGS
# ============================================================================
echo ""
echo "4. Verifying application settings..."

REQUIRED_SETTINGS=(
    "AzureWebJobsStorage"
    "APPLICATIONINSIGHTS_CONNECTION_STRING"
    "INVOICE_MAILBOX"
    "AP_EMAIL_ADDRESS"
    "TEAMS_WEBHOOK_URL"
)

SETTINGS_OK=true

for setting in "${REQUIRED_SETTINGS[@]}"; do
    if [ -n "$SLOT" ]; then
        VALUE=$(az functionapp config appsettings list --name "$FUNCTION_APP" --resource-group "$RESOURCE_GROUP" --slot "$SLOT" --query "[?name=='$setting'].value | [0]" -o tsv 2>/dev/null || echo "")
    else
        VALUE=$(az functionapp config appsettings list --name "$FUNCTION_APP" --resource-group "$RESOURCE_GROUP" --query "[?name=='$setting'].value | [0]" -o tsv 2>/dev/null || echo "")
    fi

    if [ -n "$VALUE" ]; then
        echo "   ✅ $setting"
    else
        echo "   ❌ $setting (MISSING)"
        SETTINGS_OK=false
    fi
done

if [ "$SETTINGS_OK" = true ]; then
    check_pass "All required settings present"
else
    check_fail "Some settings are missing"
fi

# ============================================================================
# 5. TEST FUNCTION EXECUTION
# ============================================================================
echo ""
echo "5. Testing function execution (smoke test)..."

# Test AddVendor endpoint (GET should return 405 Method Not Allowed, which is expected)
if [ -n "$SLOT" ]; then
    FUNCTION_KEY=$(az functionapp function keys list --name "$FUNCTION_APP" --resource-group "$RESOURCE_GROUP" --slot "$SLOT" --function-name AddVendor --query "default" -o tsv 2>/dev/null || echo "")
    TEST_URL="${ENDPOINT}/api/AddVendor?code=${FUNCTION_KEY}"
else
    FUNCTION_KEY=$(az functionapp function keys list --name "$FUNCTION_APP" --resource-group "$RESOURCE_GROUP" --function-name AddVendor --query "default" -o tsv 2>/dev/null || echo "")
    TEST_URL="${ENDPOINT}/api/AddVendor?code=${FUNCTION_KEY}"
fi

if [ -n "$FUNCTION_KEY" ]; then
    FUNC_HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$TEST_URL" || echo "000")

    # 405 Method Not Allowed is expected for GET on POST endpoint
    # 400 Bad Request is also acceptable (means endpoint is working but bad input)
    if [ "$FUNC_HTTP_CODE" = "405" ] || [ "$FUNC_HTTP_CODE" = "400" ]; then
        check_pass "Function endpoint responding (HTTP $FUNC_HTTP_CODE)"
    else
        check_fail "Function endpoint returned unexpected HTTP $FUNC_HTTP_CODE"
    fi
else
    echo "   ⚠️  Could not retrieve function key, skipping function test"
fi

# ============================================================================
# 6. CHECK APPLICATION INSIGHTS CONNECTIVITY
# ============================================================================
echo ""
echo "6. Checking Application Insights connectivity..."

sleep 30  # Wait for initial telemetry

RECENT_TELEMETRY=$(az monitor app-insights query \
  --app "$APP_INSIGHTS" \
  --resource-group "$RESOURCE_GROUP" \
  --analytics-query "requests | where timestamp > ago(5m) | count" \
  --query "tables[0].rows[0][0]" -o tsv 2>/dev/null || echo "0")

if [ "$RECENT_TELEMETRY" -gt 0 ]; then
    check_pass "Application Insights receiving telemetry ($RECENT_TELEMETRY requests in last 5 min)"
else
    echo "   ⚠️  No telemetry yet (this may be normal for new deployment)"
fi

# ============================================================================
# 7. VERIFY STORAGE CONNECTIVITY
# ============================================================================
echo ""
echo "7. Verifying storage connectivity..."

# Try to list queues
QUEUE_COUNT=$(az storage queue list --account-name "$STORAGE_ACCOUNT" --query "length(@)" -o tsv 2>/dev/null || echo "0")

if [ "$QUEUE_COUNT" -ge 6 ]; then
    check_pass "Storage account accessible ($QUEUE_COUNT queues found)"
else
    check_fail "Storage account connectivity issue or missing queues (found: $QUEUE_COUNT, expected: 6)"
fi

# ============================================================================
# 8. CHECK FOR IMMEDIATE ERRORS
# ============================================================================
echo ""
echo "8. Checking for immediate errors..."

sleep 10  # Wait a bit more

ERROR_COUNT=$(az monitor app-insights query \
  --app "$APP_INSIGHTS" \
  --resource-group "$RESOURCE_GROUP" \
  --analytics-query "exceptions | where timestamp > ago(2m) | count" \
  --query "tables[0].rows[0][0]" -o tsv 2>/dev/null || echo "0")

if [ "$ERROR_COUNT" -eq 0 ]; then
    check_pass "No exceptions in last 2 minutes"
else
    check_fail "$ERROR_COUNT exceptions detected in last 2 minutes"
fi

# ============================================================================
# 9. VERIFY TIMER TRIGGER (MailIngest)
# ============================================================================
echo ""
echo "9. Verifying timer trigger configuration..."

# Check if MailIngest function is enabled
if [ -n "$SLOT" ]; then
    MAIL_INGEST_STATUS=$(az functionapp function show --name "$FUNCTION_APP" --resource-group "$RESOURCE_GROUP" --slot "$SLOT" --function-name MailIngest --query "config.disabled" -o tsv 2>/dev/null || echo "true")
else
    MAIL_INGEST_STATUS=$(az functionapp function show --name "$FUNCTION_APP" --resource-group "$RESOURCE_GROUP" --function-name MailIngest --query "config.disabled" -o tsv 2>/dev/null || echo "true")
fi

if [ "$MAIL_INGEST_STATUS" = "false" ]; then
    check_pass "MailIngest timer trigger is enabled"
else
    check_fail "MailIngest timer trigger is disabled"
fi

# ============================================================================
# 10. DEPLOYMENT SUMMARY
# ============================================================================
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo " Deployment Validation Summary"
echo "═══════════════════════════════════════════════════════════════"
echo ""
printf "  ${GREEN}✅ Checks Passed:${NC}  %2d\n" "$CHECKS_PASSED"
printf "  ${RED}❌ Checks Failed:${NC}  %2d\n" "$CHECKS_FAILED"
echo ""

if [ "$CHECKS_FAILED" -eq 0 ]; then
    echo -e "${GREEN}✅ DEPLOYMENT VALIDATION PASSED${NC}"
    echo ""
    echo "The deployment is healthy and ready for traffic."
    EXIT_CODE=0
else
    echo -e "${RED}❌ DEPLOYMENT VALIDATION FAILED${NC}"
    echo ""
    echo "Issues detected. Review failures above before proceeding."
    echo ""
    echo "Recommended actions:"
    echo "  1. Check Application Insights for errors"
    echo "  2. Verify application settings"
    echo "  3. Review deployment logs"
    echo "  4. Consider rolling back deployment"
    EXIT_CODE=1
fi

echo ""
echo "Validation completed: $(date)"
echo ""

# If this is a staging slot, provide swap command
if [ -n "$SLOT" ] && [ "$EXIT_CODE" -eq 0 ]; then
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║                 Ready to Swap to Production                  ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo ""
    echo "To swap staging to production, run:"
    echo ""
    echo "  az functionapp deployment slot swap \\"
    echo "    --name $FUNCTION_APP \\"
    echo "    --resource-group $RESOURCE_GROUP \\"
    echo "    --slot $SLOT \\"
    echo "    --target-slot production"
    echo ""
    echo "After swap, run this script again to validate production:"
    echo "  ./validate-deployment.sh --environment $ENVIRONMENT"
    echo ""
fi

exit $EXIT_CODE
