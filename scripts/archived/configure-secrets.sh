#!/bin/bash
# Configure Key Vault secrets for Invoice Agent

echo "🔐 Invoice Agent - Key Vault Configuration"
echo "=========================================="
echo ""
echo "This script will help you configure the required secrets in Key Vault."
echo "You'll need the following information ready:"
echo "  1. Mailbox email address to monitor (e.g., dev-invoices@chelseapiers.com)"
echo "  2. AP email address for sending processed invoices"
echo "  3. Teams webhook URL (optional)"
echo "  4. Azure AD app registration details for Graph API"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Key Vault name
KV_NAME="kv-invoice-agent-prod"
RG_NAME="rg-invoice-agent-prod"

echo "Using Key Vault: $KV_NAME"
echo ""

# Function to set a secret
set_secret() {
    local secret_name=$1
    local secret_value=$2

    echo "Setting secret: $secret_name"
    az keyvault secret set \
        --vault-name "$KV_NAME" \
        --name "$secret_name" \
        --value "$secret_value" \
        --output none 2>/dev/null

    if [ $? -eq 0 ]; then
        echo -e "  ${GREEN}✅ Secret '$secret_name' set successfully${NC}"
    else
        echo -e "  ${YELLOW}⚠️ Failed to set '$secret_name' - check Key Vault permissions${NC}"
        return 1
    fi
}

# 1. Configure mailbox to monitor
echo "1️⃣ Configure Mailbox to Monitor"
echo "--------------------------------"
read -p "Enter the mailbox email address (e.g., dev-invoices@chelseapiers.com): " MAILBOX_EMAIL
if [ ! -z "$MAILBOX_EMAIL" ]; then
    set_secret "invoice-mailbox" "$MAILBOX_EMAIL"
else
    echo -e "  ${YELLOW}⚠️ Skipped - mailbox is required${NC}"
fi
echo ""

# 2. Configure AP email
echo "2️⃣ Configure AP Email Address"
echo "-----------------------------"
read -p "Enter the AP email address for processed invoices: " AP_EMAIL
if [ ! -z "$AP_EMAIL" ]; then
    set_secret "ap-email-address" "$AP_EMAIL"
else
    echo -e "  ${YELLOW}⚠️ Skipped - AP email is required${NC}"
fi
echo ""

# 3. Configure Teams webhook (optional)
echo "3️⃣ Configure Teams Webhook (Optional)"
echo "-------------------------------------"
echo "To get a webhook URL: In Teams, right-click a channel > Connectors > Incoming Webhook"
read -p "Enter Teams webhook URL (or press Enter to skip): " TEAMS_WEBHOOK
if [ ! -z "$TEAMS_WEBHOOK" ]; then
    set_secret "teams-webhook-url" "$TEAMS_WEBHOOK"
else
    echo "  ℹ️ Skipped - Teams notifications disabled"
fi
echo ""

# 4. Configure Graph API credentials
echo "4️⃣ Configure Graph API Authentication"
echo "-------------------------------------"
echo "You need an Azure AD app registration with Mail.Read and Mail.Send permissions."
echo "If you don't have one, create it in Azure Portal > Azure Active Directory > App registrations"
echo ""

read -p "Enter Graph API Tenant ID (your Azure AD tenant ID): " TENANT_ID
if [ ! -z "$TENANT_ID" ]; then
    set_secret "graph-tenant-id" "$TENANT_ID"
fi

read -p "Enter Graph API Client ID (app registration ID): " CLIENT_ID
if [ ! -z "$CLIENT_ID" ]; then
    set_secret "graph-client-id" "$CLIENT_ID"
fi

echo "Enter Graph API Client Secret (will be hidden): "
read -s CLIENT_SECRET
echo ""
if [ ! -z "$CLIENT_SECRET" ]; then
    set_secret "graph-client-secret" "$CLIENT_SECRET"
fi
echo ""

# 5. Restart function app to pick up new secrets
echo "5️⃣ Restarting Function App"
echo "-------------------------"
az functionapp restart \
    --name func-invoice-agent-prod \
    --resource-group "$RG_NAME" \
    --output none

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Function app restarted${NC}"
else
    echo -e "${YELLOW}⚠️ Could not restart function app${NC}"
fi

echo ""
echo "=========================================="
echo "📊 Configuration Summary"
echo "=========================================="

# Verify what was set
echo ""
echo "Checking configured secrets:"
for secret in invoice-mailbox ap-email-address teams-webhook-url graph-client-id graph-client-secret graph-tenant-id; do
  EXISTS=$(az keyvault secret show --vault-name "$KV_NAME" --name "$secret" --query name -o tsv 2>/dev/null)
  if [ ! -z "$EXISTS" ]; then
    echo -e "  ${GREEN}✅ $secret${NC}"
  else
    echo -e "  ❌ $secret (missing)"
  fi
done

echo ""
echo "🔄 Next Steps:"
echo "  1. Wait 2-3 minutes for function app to restart"
echo "  2. The MailIngest timer will run at the next 5-minute mark"
echo "  3. Monitor processing with: ./test-live-system.sh"
echo ""
echo "📧 Your test email to $MAILBOX_EMAIL will be processed soon!"