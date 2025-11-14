#!/bin/bash

##############################################################################
# Invoice Agent - Monitoring Deployment Script
#
# This script deploys monitoring infrastructure including:
# - Action Groups for alert notifications
# - Metric and Log Analytics alert rules
# - Azure Dashboard
#
# Usage:
#   ./deploy-monitoring.sh --environment prod [options]
#
# Options:
#   --environment ENV        Environment: dev, staging, prod (required)
#   --email EMAIL           Email address for alerts (can specify multiple)
#   --teams-webhook URL     Teams webhook URL for critical alerts
#   --enable-sms            Enable SMS alerts
#   --sms-phone NUMBER      SMS phone number in E.164 format (+1XXXXXXXXXX)
#   --subscription-id ID    Azure subscription ID (optional, uses default)
#   --update-alerts         Update existing alerts (skip if alerts exist)
#   --deploy-dashboard      Deploy dashboard definition
#   --dry-run               Show what would be deployed without deploying
#   --help                  Show this help message
#
# Examples:
#   # Deploy monitoring for production with email alerts
#   ./deploy-monitoring.sh --environment prod --email ops@company.com
#
#   # Deploy with Teams webhook and SMS
#   ./deploy-monitoring.sh --environment prod \
#     --email ops@company.com \
#     --teams-webhook "https://outlook.office.com/webhook/..." \
#     --enable-sms \
#     --sms-phone "+15551234567"
#
#   # Update existing alerts only
#   ./deploy-monitoring.sh --environment prod --update-alerts
#
#   # Dry run to preview changes
#   ./deploy-monitoring.sh --environment prod --dry-run
#
##############################################################################

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT=""
EMAIL_ADDRESSES=()
TEAMS_WEBHOOK=""
ENABLE_SMS=false
SMS_PHONE=""
SUBSCRIPTION_ID=""
UPDATE_ALERTS=false
DEPLOY_DASHBOARD=false
DRY_RUN=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Help function
show_help() {
    grep "^#" "$0" | grep -v "#!/bin/bash" | sed 's/^# //; s/^#//'
    exit 0
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --environment)
                ENVIRONMENT="$2"
                shift 2
                ;;
            --email)
                EMAIL_ADDRESSES+=("$2")
                shift 2
                ;;
            --teams-webhook)
                TEAMS_WEBHOOK="$2"
                shift 2
                ;;
            --enable-sms)
                ENABLE_SMS=true
                shift
                ;;
            --sms-phone)
                SMS_PHONE="$2"
                shift 2
                ;;
            --subscription-id)
                SUBSCRIPTION_ID="$2"
                shift 2
                ;;
            --update-alerts)
                UPDATE_ALERTS=true
                shift
                ;;
            --deploy-dashboard)
                DEPLOY_DASHBOARD=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --help)
                show_help
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                ;;
        esac
    done
}

# Validate required parameters
validate_params() {
    if [[ -z "$ENVIRONMENT" ]]; then
        log_error "Environment is required. Use --environment dev|staging|prod"
        exit 1
    fi

    if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
        log_error "Invalid environment: $ENVIRONMENT. Must be dev, staging, or prod"
        exit 1
    fi

    if [[ ${#EMAIL_ADDRESSES[@]} -eq 0 ]] && [[ -z "$TEAMS_WEBHOOK" ]]; then
        log_warning "No email or Teams webhook specified. Alerts will be created but no notifications will be sent."
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi

    if [[ "$ENABLE_SMS" == true ]] && [[ -z "$SMS_PHONE" ]]; then
        log_error "SMS enabled but no phone number provided. Use --sms-phone +1XXXXXXXXXX"
        exit 1
    fi
}

# Check Azure CLI is logged in
check_azure_login() {
    log_info "Checking Azure CLI authentication..."
    if ! az account show &>/dev/null; then
        log_error "Not logged in to Azure. Run 'az login' first."
        exit 1
    fi

    local account_name=$(az account show --query name -o tsv)
    log_success "Logged in to Azure account: $account_name"

    if [[ -n "$SUBSCRIPTION_ID" ]]; then
        log_info "Setting subscription to: $SUBSCRIPTION_ID"
        az account set --subscription "$SUBSCRIPTION_ID"
    fi
}

# Verify resources exist
verify_resources() {
    local rg_name="rg-invoice-agent-${ENVIRONMENT}"
    local app_insights_name="ai-invoice-agent-${ENVIRONMENT}"
    local function_app_name="func-invoice-agent-${ENVIRONMENT}"
    local storage_account_name="stinvoiceagent${ENVIRONMENT}"

    log_info "Verifying Azure resources exist..."

    # Check resource group
    if ! az group show --name "$rg_name" &>/dev/null; then
        log_error "Resource group $rg_name does not exist. Deploy infrastructure first."
        exit 1
    fi
    log_success "Resource group verified: $rg_name"

    # Check Application Insights
    if ! az monitor app-insights component show --app "$app_insights_name" --resource-group "$rg_name" &>/dev/null; then
        log_error "Application Insights $app_insights_name does not exist."
        exit 1
    fi
    log_success "Application Insights verified: $app_insights_name"

    # Check Function App
    if ! az functionapp show --name "$function_app_name" --resource-group "$rg_name" &>/dev/null; then
        log_error "Function App $function_app_name does not exist."
        exit 1
    fi
    log_success "Function App verified: $function_app_name"

    # Check Storage Account
    if ! az storage account show --name "$storage_account_name" --resource-group "$rg_name" &>/dev/null; then
        log_error "Storage Account $storage_account_name does not exist."
        exit 1
    fi
    log_success "Storage Account verified: $storage_account_name"
}

# Deploy alert rules
deploy_alerts() {
    local rg_name="rg-invoice-agent-${ENVIRONMENT}"
    local deployment_name="monitoring-alerts-$(date +%Y%m%d-%H%M%S)"
    local bicep_file="$SCRIPT_DIR/alerts.bicep"

    log_info "Deploying alert rules to $rg_name..."

    if [[ ! -f "$bicep_file" ]]; then
        log_error "Bicep file not found: $bicep_file"
        exit 1
    fi

    # Build parameters
    local params="environment=$ENVIRONMENT projectPrefix=invoice-agent"

    # Add email addresses
    if [[ ${#EMAIL_ADDRESSES[@]} -gt 0 ]]; then
        local email_array="["
        for email in "${EMAIL_ADDRESSES[@]}"; do
            email_array+="\"$email\","
        done
        email_array="${email_array%,}]"
        params+=" alertEmailAddresses=$email_array"
    else
        params+=" alertEmailAddresses=[]"
    fi

    # Add Teams webhook (secure parameter)
    if [[ -n "$TEAMS_WEBHOOK" ]]; then
        params+=" teamsWebhookUrl=$TEAMS_WEBHOOK"
    else
        params+=" teamsWebhookUrl=''"
    fi

    # Add SMS parameters
    if [[ "$ENABLE_SMS" == true ]]; then
        params+=" enableSmsAlerts=true smsPhoneNumber=$SMS_PHONE"
    else
        params+=" enableSmsAlerts=false smsPhoneNumber=''"
    fi

    if [[ "$DRY_RUN" == true ]]; then
        log_info "DRY RUN: Would deploy with parameters:"
        echo "$params"
        return 0
    fi

    # Deploy Bicep template
    log_info "Starting deployment: $deployment_name"

    if az deployment group create \
        --name "$deployment_name" \
        --resource-group "$rg_name" \
        --template-file "$bicep_file" \
        --parameters $params \
        --output table; then
        log_success "Alert rules deployed successfully"

        # Get deployment outputs
        local action_group_name=$(az deployment group show \
            --name "$deployment_name" \
            --resource-group "$rg_name" \
            --query properties.outputs.actionGroupName.value \
            -o tsv)

        log_success "Action Group created: $action_group_name"

        # List created alerts
        log_info "Alert rules created:"
        az deployment group show \
            --name "$deployment_name" \
            --resource-group "$rg_name" \
            --query properties.outputs.alertsCreated.value \
            -o table
    else
        log_error "Failed to deploy alert rules"
        exit 1
    fi
}

# Deploy dashboard
deploy_dashboard() {
    local rg_name="rg-invoice-agent-${ENVIRONMENT}"
    local dashboard_file="$SCRIPT_DIR/dashboard.json"
    local dashboard_name="dashboard-invoice-agent-${ENVIRONMENT}"

    log_info "Deploying Azure Dashboard..."

    if [[ ! -f "$dashboard_file" ]]; then
        log_error "Dashboard file not found: $dashboard_file"
        exit 1
    fi

    if [[ "$DRY_RUN" == true ]]; then
        log_info "DRY RUN: Would deploy dashboard from $dashboard_file"
        return 0
    fi

    # Get subscription ID for dashboard template
    local subscription_id=$(az account show --query id -o tsv)

    # Replace {subscription-id} placeholder in dashboard JSON
    local temp_dashboard=$(mktemp)
    sed "s/{subscription-id}/$subscription_id/g" "$dashboard_file" > "$temp_dashboard"

    # Deploy dashboard
    if az portal dashboard create \
        --name "$dashboard_name" \
        --resource-group "$rg_name" \
        --input-path "$temp_dashboard" \
        --location eastus; then
        log_success "Dashboard deployed: $dashboard_name"
    else
        log_error "Failed to deploy dashboard"
        rm -f "$temp_dashboard"
        exit 1
    fi

    rm -f "$temp_dashboard"
}

# Verify deployment
verify_deployment() {
    local rg_name="rg-invoice-agent-${ENVIRONMENT}"
    local action_group_name="ag-invoice-agent-${ENVIRONMENT}-ops"

    log_info "Verifying monitoring deployment..."

    # Count alerts
    local alert_count=$(az monitor metrics alert list \
        --resource-group "$rg_name" \
        --query "length([?contains(name, 'invoice-agent-${ENVIRONMENT}')])" \
        -o tsv)

    local log_alert_count=$(az monitor scheduled-query list \
        --resource-group "$rg_name" \
        --query "length([?contains(name, 'invoice-agent-${ENVIRONMENT}')])" \
        -o tsv)

    local total_alerts=$((alert_count + log_alert_count))

    log_info "Deployed alerts: $total_alerts"

    # Check action group
    if az monitor action-group show \
        --name "$action_group_name" \
        --resource-group "$rg_name" &>/dev/null; then
        log_success "Action Group verified: $action_group_name"

        # Show action group details
        log_info "Action Group details:"
        az monitor action-group show \
            --name "$action_group_name" \
            --resource-group "$rg_name" \
            --query "{EmailReceivers: emailReceivers, SMSReceivers: smsReceivers, WebhookReceivers: webhookReceivers}" \
            -o table
    else
        log_warning "Action Group not found: $action_group_name"
    fi

    if [[ "$total_alerts" -eq 0 ]]; then
        log_warning "No alerts found. Deployment may have failed."
        return 1
    fi

    log_success "Monitoring deployment verified successfully"
}

# Print summary
print_summary() {
    local rg_name="rg-invoice-agent-${ENVIRONMENT}"

    cat <<EOF

${GREEN}╔════════════════════════════════════════════════════════════════╗
║                    DEPLOYMENT SUMMARY                          ║
╚════════════════════════════════════════════════════════════════╝${NC}

${BLUE}Environment:${NC}        $ENVIRONMENT
${BLUE}Resource Group:${NC}     $rg_name
${BLUE}Email Alerts:${NC}       ${#EMAIL_ADDRESSES[@]} recipient(s)
${BLUE}Teams Webhook:${NC}      $([ -n "$TEAMS_WEBHOOK" ] && echo "Configured" || echo "Not configured")
${BLUE}SMS Alerts:${NC}         $([ "$ENABLE_SMS" == true ] && echo "Enabled" || echo "Disabled")

${BLUE}Next Steps:${NC}
1. Verify alerts in Azure Portal:
   https://portal.azure.com/#@/resource/subscriptions/$(az account show --query id -o tsv)/resourceGroups/$rg_name/providers/Microsoft.Insights/activityLogAlerts

2. View dashboard:
   https://portal.azure.com/#dashboard

3. Test alert notifications by triggering a test alert

4. Review monitoring guide:
   ${PROJECT_ROOT}/docs/monitoring/MONITORING_GUIDE.md

5. Review log queries:
   ${PROJECT_ROOT}/docs/monitoring/LOG_QUERIES.md

${BLUE}Monitoring Resources:${NC}
- Alert rules Bicep:     ${SCRIPT_DIR}/alerts.bicep
- Dashboard JSON:        ${SCRIPT_DIR}/dashboard.json
- Deployment script:     ${SCRIPT_DIR}/deploy-monitoring.sh

${GREEN}Deployment completed successfully!${NC}

EOF
}

# Main execution
main() {
    log_info "Invoice Agent - Monitoring Deployment"
    log_info "======================================="

    parse_args "$@"
    validate_params
    check_azure_login
    verify_resources

    if [[ "$DRY_RUN" == true ]]; then
        log_warning "DRY RUN MODE - No changes will be made"
    fi

    deploy_alerts

    if [[ "$DEPLOY_DASHBOARD" == true ]]; then
        deploy_dashboard
    fi

    if [[ "$DRY_RUN" == false ]]; then
        verify_deployment
        print_summary
    else
        log_info "DRY RUN completed. No changes were made."
    fi
}

# Run main function
main "$@"
