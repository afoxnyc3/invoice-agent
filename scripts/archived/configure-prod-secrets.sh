#!/bin/bash
# Configure secrets for PRODUCTION environment
# IMPORTANT: Run this script with an account that has Key Vault Administrator or Contributor role

set -e

echo "🔐 Configuring Production Environment Secrets"
echo "============================================="
echo ""
echo "⚠️  WARNING: This will configure PRODUCTION secrets!"
echo ""

# Production environment values
KV_NAME="kv-invoice-agent-prod"
FUNC_NAME="func-invoice-agent-prod"
RG_NAME="rg-invoice-agent-prod"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check if user has Key Vault access
echo "Checking Key Vault access..."
if ! az keyvault secret list --vault-name "$KV_NAME" &>/dev/null; then
    echo -e "${RED}❌ You don't have permission to manage secrets in $KV_NAME${NC}"
    echo ""
    echo "Please ensure you have one of the following roles:"
    echo "  - Key Vault Administrator"
    echo "  - Key Vault Secrets Officer"
    echo "  - Contributor on the Key Vault"
    echo ""
    echo "To grant access, an admin can run:"
    echo "  az role assignment create --role \"Key Vault Secrets Officer\" --assignee <your-email> --scope /subscriptions/1e86461d-c127-4e54-b041-915d623f9138/resourceGroups/$RG_NAME/providers/Microsoft.KeyVault/vaults/$KV_NAME"
    exit 1
fi

echo -e "${GREEN}✅ Key Vault access confirmed${NC}"
echo ""

# Prompt for required values
echo "📋 Enter the required configuration values:"
echo ""

# Graph API Configuration
read -p "Graph API Tenant ID: " TENANT_ID
if [ -z "$TENANT_ID" ]; then
    echo -e "${RED}❌ Tenant ID is required${NC}"
    exit 1
fi

read -p "Graph API Client ID (Application ID): " CLIENT_ID
if [ -z "$CLIENT_ID" ]; then
    echo -e "${RED}❌ Client ID is required${NC}"
    exit 1
fi

echo "Graph API Client Secret (input will be hidden):"
read -s CLIENT_SECRET
echo ""
if [ -z "$CLIENT_SECRET" ]; then
    echo -e "${RED}❌ Client Secret is required${NC}"
    exit 1
fi

# Email Configuration
read -p "Invoice Mailbox Email [invoices@chelseapiers.com]: " INVOICE_MAILBOX
INVOICE_MAILBOX=${INVOICE_MAILBOX:-invoices@chelseapiers.com}

read -p "AP Department Email [ap@chelseapiers.com]: " AP_EMAIL
AP_EMAIL=${AP_EMAIL:-ap@chelseapiers.com}

# Teams Webhook
echo ""
echo "For Teams Webhook URL:"
echo "1. Go to your Teams channel"
echo "2. Click ⋯ → Connectors → Incoming Webhook"
echo "3. Create/copy the webhook URL"
echo ""
read -p "Teams Webhook URL: " TEAMS_WEBHOOK
if [ -z "$TEAMS_WEBHOOK" ]; then
    echo -e "${YELLOW}⚠️  Teams notifications will not work without webhook URL${NC}"
    TEAMS_WEBHOOK="https://placeholder.webhook.office.com"
fi

echo ""
echo "======================================"
echo "Setting Key Vault secrets..."
echo ""

# Function to set secret and check result
set_secret() {
    local name=$1
    local value=$2
    local display_name=$3

    echo -n "  Setting $display_name... "
    if az keyvault secret set --vault-name "$KV_NAME" --name "$name" --value "$value" --output none 2>/dev/null; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗${NC}"
        return 1
    fi
}

# Set all required secrets
set_secret "graph-tenant-id" "$TENANT_ID" "Graph Tenant ID"
set_secret "graph-client-id" "$CLIENT_ID" "Graph Client ID"
set_secret "graph-client-secret" "$CLIENT_SECRET" "Graph Client Secret"
set_secret "invoice-mailbox" "$INVOICE_MAILBOX" "Invoice Mailbox"
set_secret "ap-email-address" "$AP_EMAIL" "AP Email Address"
set_secret "teams-webhook-url" "$TEAMS_WEBHOOK" "Teams Webhook URL"

# Generate and set client state for webhook security
echo -n "  Generating webhook client state... "
CLIENT_STATE=$(openssl rand -base64 48)
if az keyvault secret set --vault-name "$KV_NAME" --name "graph-client-state" --value "$CLIENT_STATE" --output none 2>/dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

# Set webhook URL (will be updated when function key is available)
echo -n "  Setting webhook URL... "
WEBHOOK_URL="https://${FUNC_NAME}.azurewebsites.net/api/MailWebhook"
if az keyvault secret set --vault-name "$KV_NAME" --name "mail-webhook-url" --value "$WEBHOOK_URL" --output none 2>/dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

echo ""
echo "======================================"
echo -e "${GREEN}✅ Key Vault secrets configured successfully!${NC}"
echo ""

# Restart Function App to pick up new secrets
echo "Restarting Function App to load new secrets..."
az functionapp restart --name "$FUNC_NAME" --resource-group "$RG_NAME"

echo ""
echo "⏳ Waiting 30 seconds for Function App to restart..."
sleep 30

echo ""
echo "======================================"
echo -e "${GREEN}✅ Configuration Complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Verify functions are working:"
echo "   az functionapp function list --name $FUNC_NAME --resource-group $RG_NAME"
echo ""
echo "2. Trigger SubscriptionManager to create webhook subscription:"
echo "   Go to Azure Portal → $FUNC_NAME → Functions → SubscriptionManager → Code + Test → Test/Run"
echo ""
echo "3. Send a test email to: $INVOICE_MAILBOX"
echo ""
echo "4. Monitor Application Insights for activity"
echo ""