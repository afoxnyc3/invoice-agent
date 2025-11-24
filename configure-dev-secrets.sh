#!/bin/bash
# Configure secrets for dev environment

echo "🔐 Configuring Dev Environment Secrets"
echo "======================================"
echo ""

# Dev environment values
KV_NAME="kv-invoice-agent-dev"
FUNC_NAME="func-invoice-agent-dev"
RG_NAME="rg-invoice-agent-dev"
INVOICE_MAILBOX="dev-invoices@chelseapiers.com"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Prompt for Graph API credentials
echo "📋 Enter your Graph API credentials:"
echo ""

read -p "Tenant ID: " TENANT_ID
if [ -z "$TENANT_ID" ]; then
    echo -e "${RED}❌ Tenant ID is required${NC}"
    exit 1
fi

read -p "Client ID (Application ID): " CLIENT_ID
if [ -z "$CLIENT_ID" ]; then
    echo -e "${RED}❌ Client ID is required${NC}"
    exit 1
fi

echo "Client Secret (input will be hidden):"
read -s CLIENT_SECRET
echo ""
if [ -z "$CLIENT_SECRET" ]; then
    echo -e "${RED}❌ Client Secret is required${NC}"
    exit 1
fi

read -p "AP Email Address [ap@chelseapiers.com]: " AP_EMAIL
AP_EMAIL=${AP_EMAIL:-ap@chelseapiers.com}

echo ""
echo "Setting Key Vault secrets..."

# Set Graph API credentials
az keyvault secret set \
  --vault-name "$KV_NAME" \
  --name "graph-tenant-id" \
  --value "$TENANT_ID" \
  --output none && echo "✅ Tenant ID configured"

az keyvault secret set \
  --vault-name "$KV_NAME" \
  --name "graph-client-id" \
  --value "$CLIENT_ID" \
  --output none && echo "✅ Client ID configured"

az keyvault secret set \
  --vault-name "$KV_NAME" \
  --name "graph-client-secret" \
  --value "$CLIENT_SECRET" \
  --output none && echo "✅ Client Secret configured"

# Set invoice mailbox
az keyvault secret set \
  --vault-name "$KV_NAME" \
  --name "invoice-mailbox" \
  --value "$INVOICE_MAILBOX" \
  --output none && echo "✅ Invoice mailbox configured: $INVOICE_MAILBOX"

# Set AP email
az keyvault secret set \
  --vault-name "$KV_NAME" \
  --name "ap-email-address" \
  --value "$AP_EMAIL" \
  --output none && echo "✅ AP email configured: $AP_EMAIL"

# Restart function app
echo ""
echo "Restarting Function App to apply changes..."
az functionapp restart \
  --name "$FUNC_NAME" \
  --resource-group "$RG_NAME" \
  --output none

echo -e "${GREEN}✅ Function App restarted${NC}"

# Verify configuration
echo ""
echo "======================================================"
echo "📊 Configuration Summary"
echo "======================================================"

for secret in invoice-mailbox ap-email-address graph-tenant-id graph-client-id graph-client-secret; do
  EXISTS=$(az keyvault secret show --vault-name "$KV_NAME" --name "$secret" --query name -o tsv 2>/dev/null)
  if [ ! -z "$EXISTS" ]; then
    if [ "$secret" == "graph-client-secret" ]; then
      echo -e "  ${GREEN}✅ $secret [configured]${NC}"
    else
      VALUE=$(az keyvault secret show --vault-name "$KV_NAME" --name "$secret" --query value -o tsv 2>/dev/null)
      if [ "$secret" == "invoice-mailbox" ] || [ "$secret" == "ap-email-address" ]; then
        echo -e "  ${GREEN}✅ $secret: $VALUE${NC}"
      else
        echo -e "  ${GREEN}✅ $secret${NC}"
      fi
    fi
  else
    echo -e "  ${RED}❌ $secret [missing]${NC}"
  fi
done

# Calculate next timer run
CURRENT_MIN=$(date +%M)
NEXT_RUN=$((((CURRENT_MIN / 5) + 1) * 5))
if [ $NEXT_RUN -ge 60 ]; then
    NEXT_RUN=$((NEXT_RUN - 60))
    echo ""
    echo -e "${GREEN}🎉 Configuration Complete!${NC}"
    echo ""
    echo "⏰ Next email poll: :00 (top of next hour)"
else
    echo ""
    echo -e "${GREEN}🎉 Configuration Complete!${NC}"
    echo ""
    echo "⏰ Next email poll: :$(printf %02d $NEXT_RUN)"
fi

echo ""
echo "📧 Test by sending an email with attachment to: $INVOICE_MAILBOX"
echo "🔍 Monitor logs with: az monitor app-insights query --app $FUNC_NAME --analytics-query \"traces | where timestamp > ago(1h) | order by timestamp desc | take 50\""
echo ""
