#!/bin/bash
# Deploy Invoice Agent Operations Workbook to Azure Monitor
#
# Usage:
#   ./deploy_workbook.sh [--env prod|dev] [--subscription-id <id>]
#
# Prerequisites:
#   - Azure CLI installed and logged in
#   - Contributor access to the resource group

set -e

# Defaults
ENV="${ENV:-prod}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKBOOK_FILE="$SCRIPT_DIR/../monitoring/invoice-agent-workbook.json"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --env)
            ENV="$2"
            shift 2
            ;;
        --subscription-id)
            SUBSCRIPTION_ID="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Set resource names based on environment
RESOURCE_GROUP="rg-invoice-agent-$ENV"
APP_INSIGHTS="ai-invoice-agent-$ENV"
WORKBOOK_NAME="Invoice Agent Operations"

# Get subscription ID if not provided
if [ -z "$SUBSCRIPTION_ID" ]; then
    SUBSCRIPTION_ID=$(az account show --query id -o tsv)
fi

echo "Deploying workbook to:"
echo "  Subscription: $SUBSCRIPTION_ID"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  App Insights: $APP_INSIGHTS"
echo ""

# Check if App Insights exists
echo "Checking App Insights resource..."
AI_RESOURCE_ID=$(az monitor app-insights component show \
    --app "$APP_INSIGHTS" \
    --resource-group "$RESOURCE_GROUP" \
    --query id -o tsv 2>/dev/null || echo "")

if [ -z "$AI_RESOURCE_ID" ]; then
    echo "Error: App Insights resource '$APP_INSIGHTS' not found in resource group '$RESOURCE_GROUP'"
    exit 1
fi

echo "Found App Insights: $AI_RESOURCE_ID"

# Read workbook template and substitute placeholders
echo "Preparing workbook template..."
WORKBOOK_CONTENT=$(cat "$WORKBOOK_FILE" | sed "s|{subscription-id}|$SUBSCRIPTION_ID|g")

# Generate a unique workbook ID (GUID)
WORKBOOK_ID=$(uuidgen | tr '[:upper:]' '[:lower:]')

# Check if workbook already exists
EXISTING_WORKBOOK=$(az monitor app-insights workbook list \
    --resource-group "$RESOURCE_GROUP" \
    --query "[?displayName=='$WORKBOOK_NAME'].id" -o tsv 2>/dev/null || echo "")

if [ -n "$EXISTING_WORKBOOK" ]; then
    echo "Updating existing workbook..."
    WORKBOOK_RESOURCE_ID="$EXISTING_WORKBOOK"

    az monitor app-insights workbook update \
        --resource-group "$RESOURCE_GROUP" \
        --name "$(basename $EXISTING_WORKBOOK)" \
        --serialized-data "$WORKBOOK_CONTENT" \
        --output none
else
    echo "Creating new workbook..."
    WORKBOOK_RESOURCE_ID="/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Insights/workbooks/$WORKBOOK_ID"

    az monitor app-insights workbook create \
        --resource-group "$RESOURCE_GROUP" \
        --name "$WORKBOOK_ID" \
        --display-name "$WORKBOOK_NAME" \
        --category "workbook" \
        --kind "shared" \
        --source-id "$AI_RESOURCE_ID" \
        --serialized-data "$WORKBOOK_CONTENT" \
        --output none
fi

echo ""
echo "Workbook deployed successfully!"
echo ""
echo "To view the workbook:"
echo "  1. Go to Azure Portal: https://portal.azure.com"
echo "  2. Navigate to: Application Insights > $APP_INSIGHTS > Workbooks"
echo "  3. Open: '$WORKBOOK_NAME'"
echo ""
echo "Direct link:"
echo "  https://portal.azure.com/#@/resource$AI_RESOURCE_ID/workbooks"
