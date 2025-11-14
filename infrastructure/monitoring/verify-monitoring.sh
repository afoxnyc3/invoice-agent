#!/bin/bash

##############################################################################
# Invoice Agent - Monitoring Verification Script
#
# This script verifies that monitoring infrastructure is properly configured
# and functioning correctly.
#
# Usage:
#   ./verify-monitoring.sh --environment prod
#
##############################################################################

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ENVIRONMENT=""
VERBOSE=false

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[!]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        *)
            echo "Usage: $0 --environment <env> [--verbose]"
            exit 1
            ;;
    esac
done

if [[ -z "$ENVIRONMENT" ]]; then
    log_error "Environment is required. Use --environment dev|staging|prod"
    exit 1
fi

RG_NAME="rg-invoice-agent-${ENVIRONMENT}"
APP_INSIGHTS_NAME="ai-invoice-agent-${ENVIRONMENT}"
ACTION_GROUP_NAME="ag-invoice-agent-${ENVIRONMENT}-ops"

echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║     Invoice Agent Monitoring Verification             ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# Check Azure login
log_info "Verifying Azure CLI authentication..."
if ! az account show &>/dev/null; then
    log_error "Not logged in to Azure. Run 'az login' first."
    exit 1
fi
log_success "Authenticated to Azure"

# Check resource group exists
log_info "Checking resource group: $RG_NAME"
if ! az group show --name "$RG_NAME" &>/dev/null; then
    log_error "Resource group not found: $RG_NAME"
    exit 1
fi
log_success "Resource group exists"

# Check Application Insights
log_info "Checking Application Insights: $APP_INSIGHTS_NAME"
if ! az monitor app-insights component show --app "$APP_INSIGHTS_NAME" --resource-group "$RG_NAME" &>/dev/null; then
    log_error "Application Insights not found"
    exit 1
fi
log_success "Application Insights exists"

# Check if data is flowing
log_info "Verifying telemetry data..."
data_count=$(az monitor app-insights query \
    --app "$APP_INSIGHTS_NAME" \
    --analytics-query "requests | where timestamp > ago(1h) | count" \
    --query "tables[0].rows[0][0]" -o tsv 2>/dev/null || echo "0")

if [[ "$data_count" -gt 0 ]]; then
    log_success "Receiving telemetry data ($data_count requests in last hour)"
else
    log_warning "No telemetry data in last hour (system may be idle)"
fi

# Check action group
log_info "Checking action group: $ACTION_GROUP_NAME"
if az monitor action-group show --name "$ACTION_GROUP_NAME" --resource-group "$RG_NAME" &>/dev/null; then
    log_success "Action group exists"

    # Get action group details
    email_count=$(az monitor action-group show \
        --name "$ACTION_GROUP_NAME" \
        --resource-group "$RG_NAME" \
        --query "length(emailReceivers)" -o tsv)

    webhook_count=$(az monitor action-group show \
        --name "$ACTION_GROUP_NAME" \
        --resource-group "$RG_NAME" \
        --query "length(webhookReceivers)" -o tsv)

    log_info "  - Email receivers: $email_count"
    log_info "  - Webhook receivers: $webhook_count"

    if [[ "$email_count" -eq 0 ]] && [[ "$webhook_count" -eq 0 ]]; then
        log_warning "No notification receivers configured"
    fi
else
    log_error "Action group not found"
fi

# Check metric alerts
log_info "Checking metric alerts..."
metric_alerts=$(az monitor metrics alert list \
    --resource-group "$RG_NAME" \
    --query "[?contains(name, 'invoice-agent-${ENVIRONMENT}')]" \
    -o tsv 2>/dev/null | wc -l | xargs)

if [[ "$metric_alerts" -gt 0 ]]; then
    log_success "Found $metric_alerts metric alert(s)"
else
    log_warning "No metric alerts found"
fi

# Check log analytics alerts
log_info "Checking log analytics alerts..."
log_alerts=$(az monitor scheduled-query list \
    --resource-group "$RG_NAME" \
    --query "[?contains(name, 'invoice-agent-${ENVIRONMENT}')]" \
    -o tsv 2>/dev/null | wc -l | xargs)

if [[ "$log_alerts" -gt 0 ]]; then
    log_success "Found $log_alerts log alert(s)"
else
    log_warning "No log analytics alerts found"
fi

total_alerts=$((metric_alerts + log_alerts))
expected_alerts=8

echo ""
log_info "Total alerts configured: $total_alerts (expected: $expected_alerts)"

if [[ "$total_alerts" -eq "$expected_alerts" ]]; then
    log_success "All expected alerts are configured"
elif [[ "$total_alerts" -gt 0 ]]; then
    log_warning "Alert count mismatch (found: $total_alerts, expected: $expected_alerts)"
else
    log_error "No alerts configured. Run deploy-monitoring.sh"
fi

# List all alerts if verbose
if [[ "$VERBOSE" == true ]] && [[ "$total_alerts" -gt 0 ]]; then
    echo ""
    log_info "Alert Details:"
    echo ""

    az monitor metrics alert list \
        --resource-group "$RG_NAME" \
        --query "[?contains(name, 'invoice-agent-${ENVIRONMENT}')].{Name:name, Enabled:enabled, Severity:severity}" \
        -o table 2>/dev/null

    az monitor scheduled-query list \
        --resource-group "$RG_NAME" \
        --query "[?contains(name, 'invoice-agent-${ENVIRONMENT}')].{Name:name, Enabled:enabled, Severity:severity}" \
        -o table 2>/dev/null
fi

# Check dashboard
log_info "Checking dashboard..."
dashboard_count=$(az portal dashboard list \
    --resource-group "$RG_NAME" \
    --query "[?contains(name, 'invoice-agent-${ENVIRONMENT}')] | length(@)" \
    -o tsv 2>/dev/null || echo "0")

if [[ "$dashboard_count" -gt 0 ]]; then
    log_success "Dashboard exists"
else
    log_warning "Dashboard not found (deploy with --deploy-dashboard)"
fi

# Summary
echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║                     SUMMARY                            ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

checks_passed=0
total_checks=6

[[ -n "$(az group show --name "$RG_NAME" 2>/dev/null)" ]] && ((checks_passed++))
[[ -n "$(az monitor app-insights component show --app "$APP_INSIGHTS_NAME" --resource-group "$RG_NAME" 2>/dev/null)" ]] && ((checks_passed++))
[[ -n "$(az monitor action-group show --name "$ACTION_GROUP_NAME" --resource-group "$RG_NAME" 2>/dev/null)" ]] && ((checks_passed++))
[[ "$metric_alerts" -gt 0 ]] && ((checks_passed++))
[[ "$log_alerts" -gt 0 ]] && ((checks_passed++))
[[ "$data_count" -gt 0 ]] && ((checks_passed++))

echo "Checks passed: $checks_passed / $total_checks"
echo ""

if [[ "$checks_passed" -eq "$total_checks" ]]; then
    log_success "All monitoring checks passed!"
    exit 0
elif [[ "$checks_passed" -ge 4 ]]; then
    log_warning "Monitoring is partially configured ($checks_passed/$total_checks checks passed)"
    exit 0
else
    log_error "Monitoring configuration incomplete ($checks_passed/$total_checks checks passed)"
    exit 1
fi
