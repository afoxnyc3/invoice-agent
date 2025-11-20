#!/bin/bash
# Health Check Script for Invoice Agent
# Performs comprehensive health checks across all components
# Usage: ./health-check.sh [--environment prod|dev] [--verbose]

set -euo pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="${1:-prod}"
VERBOSE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

# Set resource names
RESOURCE_GROUP="rg-invoice-agent-${ENVIRONMENT}"
FUNCTION_APP="func-invoice-agent-${ENVIRONMENT}"
STORAGE_ACCOUNT="stinvoiceagent${ENVIRONMENT}"
APP_INSIGHTS="ai-invoice-agent-${ENVIRONMENT}"

# Counters
PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

log_pass() {
    echo -e "${GREEN}✅ PASS${NC}: $1"
    ((PASS_COUNT++))
}

log_fail() {
    echo -e "${RED}❌ FAIL${NC}: $1"
    ((FAIL_COUNT++))
}

log_warn() {
    echo -e "${YELLOW}⚠️  WARN${NC}: $1"
    ((WARN_COUNT++))
}

log_info() {
    if [ "$VERBOSE" = true ]; then
        echo "ℹ️  INFO: $1"
    fi
}

check_section() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo " $1"
    echo "═══════════════════════════════════════════════════════════════"
}

# Start health check
echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║       Invoice Agent Health Check - ${ENVIRONMENT^^} Environment       ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo "Timestamp: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
echo ""

# ============================================================================
# 1. AZURE AUTHENTICATION
# ============================================================================
check_section "1. Azure Authentication"

if az account show &>/dev/null; then
    ACCOUNT_NAME=$(az account show --query "user.name" -o tsv)
    log_pass "Azure CLI authenticated as $ACCOUNT_NAME"
else
    log_fail "Not authenticated to Azure CLI. Run: az login"
    exit 1
fi

# ============================================================================
# 2. RESOURCE GROUP
# ============================================================================
check_section "2. Resource Group"

if az group exists --name "$RESOURCE_GROUP" | grep -q true; then
    log_pass "Resource group exists: $RESOURCE_GROUP"

    # List critical resources
    RESOURCES=$(az resource list --resource-group "$RESOURCE_GROUP" --query "length(@)" -o tsv)
    log_info "Resource count: $RESOURCES"

    if [ "$RESOURCES" -ge 4 ]; then
        log_pass "Expected resources present (minimum 4)"
    else
        log_warn "Resource count low: $RESOURCES (expected at least 4)"
    fi
else
    log_fail "Resource group not found: $RESOURCE_GROUP"
    exit 1
fi

# ============================================================================
# 3. FUNCTION APP
# ============================================================================
check_section "3. Function App"

if az functionapp show --name "$FUNCTION_APP" --resource-group "$RESOURCE_GROUP" &>/dev/null; then
    log_pass "Function App exists: $FUNCTION_APP"

    # Check state
    STATE=$(az functionapp show --name "$FUNCTION_APP" --resource-group "$RESOURCE_GROUP" --query "state" -o tsv)
    if [ "$STATE" = "Running" ]; then
        log_pass "Function App is running"
    else
        log_fail "Function App state: $STATE (expected: Running)"
    fi

    # Check function count
    FUNCTION_COUNT=$(az functionapp function list --name "$FUNCTION_APP" --resource-group "$RESOURCE_GROUP" --query "length(@)" -o tsv)
    if [ "$FUNCTION_COUNT" -eq 5 ]; then
        log_pass "All 5 functions deployed"
    else
        log_warn "Function count: $FUNCTION_COUNT (expected: 5)"
    fi

    # Test endpoint connectivity
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "https://${FUNCTION_APP}.azurewebsites.net" || echo "000")
    if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "401" ]; then
        log_pass "Function App endpoint reachable (HTTP $HTTP_CODE)"
    else
        log_fail "Function App endpoint unreachable (HTTP $HTTP_CODE)"
    fi
else
    log_fail "Function App not found: $FUNCTION_APP"
fi

# ============================================================================
# 4. APP SETTINGS
# ============================================================================
check_section "4. Application Settings"

REQUIRED_SETTINGS=(
    "AzureWebJobsStorage"
    "APPLICATIONINSIGHTS_CONNECTION_STRING"
    "INVOICE_MAILBOX"
    "AP_EMAIL_ADDRESS"
    "TEAMS_WEBHOOK_URL"
)

for setting in "${REQUIRED_SETTINGS[@]}"; do
    VALUE=$(az functionapp config appsettings list \
      --name "$FUNCTION_APP" \
      --resource-group "$RESOURCE_GROUP" \
      --query "[?name=='$setting'].value | [0]" -o tsv 2>/dev/null || echo "")

    if [ -n "$VALUE" ]; then
        log_pass "Setting configured: $setting"
    else
        log_fail "Setting missing: $setting"
    fi
done

# ============================================================================
# 5. STORAGE ACCOUNT
# ============================================================================
check_section "5. Storage Account"

if az storage account show --name "$STORAGE_ACCOUNT" --resource-group "$RESOURCE_GROUP" &>/dev/null; then
    log_pass "Storage account exists: $STORAGE_ACCOUNT"

    # Check provisioning state
    PROV_STATE=$(az storage account show --name "$STORAGE_ACCOUNT" --resource-group "$RESOURCE_GROUP" --query "provisioningState" -o tsv)
    if [ "$PROV_STATE" = "Succeeded" ]; then
        log_pass "Storage account provisioned successfully"
    else
        log_warn "Storage provisioning state: $PROV_STATE"
    fi

    # Check tables
    TABLES=$(az storage table list --account-name "$STORAGE_ACCOUNT" --query "length(@)" -o tsv 2>/dev/null || echo "0")
    if [ "$TABLES" -ge 2 ]; then
        log_pass "Tables exist: $TABLES found (expected: VendorMaster, InvoiceTransactions)"
    else
        log_fail "Missing tables (found: $TABLES, expected: 2)"
    fi

    # Check queues
    QUEUES=$(az storage queue list --account-name "$STORAGE_ACCOUNT" --query "length(@)" -o tsv 2>/dev/null || echo "0")
    if [ "$QUEUES" -ge 6 ]; then
        log_pass "Queues exist: $QUEUES found (expected: 6)"
    else
        log_warn "Queue count: $QUEUES (expected: 6)"
    fi

    # Check blob container
    if az storage container exists --name invoices --account-name "$STORAGE_ACCOUNT" --query "exists" -o tsv 2>/dev/null | grep -q true; then
        log_pass "Blob container 'invoices' exists"
    else
        log_fail "Blob container 'invoices' not found"
    fi
else
    log_fail "Storage account not found: $STORAGE_ACCOUNT"
fi

# ============================================================================
# 6. QUEUE DEPTHS
# ============================================================================
check_section "6. Queue Depths"

for queue in raw-mail to-post notify; do
    DEPTH=$(az storage queue metadata show \
      --name "$queue" \
      --account-name "$STORAGE_ACCOUNT" \
      --query "approximateMessagesCount" -o tsv 2>/dev/null || echo "ERR")

    if [ "$DEPTH" = "ERR" ]; then
        log_fail "Cannot read queue: $queue"
    elif [ "$DEPTH" -eq 0 ]; then
        log_pass "Queue $queue is empty (healthy)"
    elif [ "$DEPTH" -le 10 ]; then
        log_pass "Queue $queue has $DEPTH messages (normal)"
    elif [ "$DEPTH" -le 100 ]; then
        log_warn "Queue $queue has $DEPTH messages (elevated)"
    else
        log_fail "Queue $queue has $DEPTH messages (critical backlog)"
    fi
done

# Check poison queues
for poison_queue in raw-mail-poison to-post-poison notify-poison; do
    POISON_DEPTH=$(az storage queue metadata show \
      --name "$poison_queue" \
      --account-name "$STORAGE_ACCOUNT" \
      --query "approximateMessagesCount" -o tsv 2>/dev/null || echo "0")

    if [ "$POISON_DEPTH" -eq 0 ]; then
        log_pass "Poison queue $poison_queue is empty (healthy)"
    else
        log_fail "Poison queue $poison_queue has $POISON_DEPTH messages (requires investigation)"
    fi
done

# ============================================================================
# 7. VENDOR MASTER TABLE
# ============================================================================
check_section "7. VendorMaster Table"

VENDOR_COUNT=$(az storage entity query \
  --table-name VendorMaster \
  --account-name "$STORAGE_ACCOUNT" \
  --filter "PartitionKey eq 'Vendor' and Active eq true" \
  --select "RowKey" \
  --query "length(items)" -o tsv 2>/dev/null || echo "0")

if [ "$VENDOR_COUNT" -ge 9 ]; then
    log_pass "VendorMaster has $VENDOR_COUNT active vendors (expected: at least 9)"
elif [ "$VENDOR_COUNT" -gt 0 ]; then
    log_warn "VendorMaster has only $VENDOR_COUNT vendors (expected: at least 9)"
else
    log_fail "VendorMaster table is empty or inaccessible"
fi

# ============================================================================
# 8. APPLICATION INSIGHTS
# ============================================================================
check_section "8. Application Insights"

if az monitor app-insights component show --app "$APP_INSIGHTS" --resource-group "$RESOURCE_GROUP" &>/dev/null; then
    log_pass "Application Insights exists: $APP_INSIGHTS"

    # Check recent telemetry
    RECENT_REQUESTS=$(az monitor app-insights query \
      --app "$APP_INSIGHTS" \
      --resource-group "$RESOURCE_GROUP" \
      --analytics-query "requests | where timestamp > ago(1h) | count" \
      --query "tables[0].rows[0][0]" -o tsv 2>/dev/null || echo "0")

    if [ "$RECENT_REQUESTS" -gt 0 ]; then
        log_pass "Application Insights receiving data ($RECENT_REQUESTS requests in last hour)"
    else
        log_warn "No requests logged in last hour (may be idle)"
    fi

    # Check error rate
    RECENT_ERRORS=$(az monitor app-insights query \
      --app "$APP_INSIGHTS" \
      --resource-group "$RESOURCE_GROUP" \
      --analytics-query "requests | where timestamp > ago(1h) and success == false | count" \
      --query "tables[0].rows[0][0]" -o tsv 2>/dev/null || echo "0")

    if [ "$RECENT_REQUESTS" -gt 0 ]; then
        ERROR_RATE=$(awk "BEGIN {printf \"%.2f\", ($RECENT_ERRORS / $RECENT_REQUESTS) * 100}")
        if (( $(echo "$ERROR_RATE < 1" | bc -l) )); then
            log_pass "Error rate: ${ERROR_RATE}% (healthy, <1%)"
        elif (( $(echo "$ERROR_RATE < 5" | bc -l) )); then
            log_warn "Error rate: ${ERROR_RATE}% (elevated, 1-5%)"
        else
            log_fail "Error rate: ${ERROR_RATE}% (critical, >5%)"
        fi
    fi
else
    log_fail "Application Insights not found: $APP_INSIGHTS"
fi

# ============================================================================
# 9. RECENT FUNCTION EXECUTIONS
# ============================================================================
check_section "9. Recent Function Executions (Last Hour)"

for func in MailIngest ExtractEnrich PostToAP Notify; do
    EXEC_COUNT=$(az monitor app-insights query \
      --app "$APP_INSIGHTS" \
      --resource-group "$RESOURCE_GROUP" \
      --analytics-query "requests | where timestamp > ago(1h) and operation_Name == '$func' | count" \
      --query "tables[0].rows[0][0]" -o tsv 2>/dev/null || echo "0")

    if [ "$func" = "MailIngest" ]; then
        # MailIngest runs every 5 minutes, expect at least 10 executions in last hour
        if [ "$EXEC_COUNT" -ge 10 ]; then
            log_pass "$func: $EXEC_COUNT executions (expected: ~12)"
        elif [ "$EXEC_COUNT" -gt 0 ]; then
            log_warn "$func: $EXEC_COUNT executions (expected: ~12, may be recent deployment)"
        else
            log_fail "$func: No executions in last hour"
        fi
    else
        # Other functions triggered by queues
        if [ "$EXEC_COUNT" -gt 0 ]; then
            log_pass "$func: $EXEC_COUNT executions"
        else
            log_info "$func: No executions (normal if no emails processed)"
        fi
    fi
done

# ============================================================================
# SUMMARY
# ============================================================================
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo " Health Check Summary"
echo "═══════════════════════════════════════════════════════════════"
echo ""
printf "  ${GREEN}✅ Passed:${NC}  %2d\n" "$PASS_COUNT"
printf "  ${YELLOW}⚠️  Warnings:${NC} %2d\n" "$WARN_COUNT"
printf "  ${RED}❌ Failed:${NC}  %2d\n" "$FAIL_COUNT"
echo ""

# Overall status
if [ "$FAIL_COUNT" -eq 0 ] && [ "$WARN_COUNT" -eq 0 ]; then
    echo -e "${GREEN}Overall Status: HEALTHY${NC}"
    EXIT_CODE=0
elif [ "$FAIL_COUNT" -eq 0 ]; then
    echo -e "${YELLOW}Overall Status: DEGRADED (warnings present)${NC}"
    EXIT_CODE=1
else
    echo -e "${RED}Overall Status: UNHEALTHY (failures present)${NC}"
    EXIT_CODE=2
fi

echo ""
echo "Health check completed at: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
echo ""

# Generate report file
REPORT_FILE="/tmp/invoice-agent-health-${ENVIRONMENT}-$(date +%Y%m%d-%H%M%S).txt"
{
    echo "Invoice Agent Health Check Report"
    echo "Environment: $ENVIRONMENT"
    echo "Timestamp: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
    echo ""
    echo "Summary:"
    echo "  Passed: $PASS_COUNT"
    echo "  Warnings: $WARN_COUNT"
    echo "  Failed: $FAIL_COUNT"
    echo ""
    echo "Overall Status: $([ $EXIT_CODE -eq 0 ] && echo 'HEALTHY' || [ $EXIT_CODE -eq 1 ] && echo 'DEGRADED' || echo 'UNHEALTHY')"
} > "$REPORT_FILE"

if [ "$VERBOSE" = true ]; then
    echo "Report saved to: $REPORT_FILE"
fi

exit $EXIT_CODE
