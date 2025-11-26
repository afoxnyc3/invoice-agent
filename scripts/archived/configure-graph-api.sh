#!/bin/bash
# Configure Graph API credentials for Invoice Agent

echo "🔐 Graph API Configuration for Invoice Agent"
echo "==========================================="
echo ""
echo "This will configure the Graph API credentials needed to read/send emails."
echo "You need to have already created an Azure AD App Registration."
echo ""
echo "See GRAPH_API_SETUP.md for detailed instructions."
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

KV_NAME="kv-invoice-agent-prod"

# Get tenant ID
echo "1️⃣ Tenant ID"
echo "Find this in Azure Portal > Azure Active Directory > Overview"
read -p "Enter your Azure AD Tenant ID: " TENANT_ID

if [ -z "$TENANT_ID" ]; then
    echo -e "${RED}❌ Tenant ID is required${NC}"
    exit 1
fi

# Get client ID
echo ""
echo "2️⃣ Client ID (Application ID)"
echo "Find this in your App Registration overview page"
read -p "Enter the Application (client) ID: " CLIENT_ID

if [ -z "$CLIENT_ID" ]; then
    echo -e "${RED}❌ Client ID is required${NC}"
    exit 1
fi

# Get client secret
echo ""
echo "3️⃣ Client Secret"
echo "Created in Certificates & secrets section"
echo "Enter the secret value (input will be hidden):"
read -s CLIENT_SECRET
echo ""

if [ -z "$CLIENT_SECRET" ]; then
    echo -e "${RED}❌ Client Secret is required${NC}"
    exit 1
fi

# Set the secrets
echo ""
echo "Setting Key Vault secrets..."

az keyvault secret set \
  --vault-name "$KV_NAME" \
  --name "graph-tenant-id" \
  --value "$TENANT_ID" \
  --output none

echo "✅ Tenant ID configured"

az keyvault secret set \
  --vault-name "$KV_NAME" \
  --name "graph-client-id" \
  --value "$CLIENT_ID" \
  --output none

echo "✅ Client ID configured"

az keyvault secret set \
  --vault-name "$KV_NAME" \
  --name "graph-client-secret" \
  --value "$CLIENT_SECRET" \
  --output none

echo "✅ Client Secret configured"

# Set Teams webhook if desired
echo ""
echo "4️⃣ Teams Webhook (Optional)"
echo "For notifications in Microsoft Teams"
read -p "Enter Teams webhook URL (or press Enter to skip): " TEAMS_WEBHOOK

if [ ! -z "$TEAMS_WEBHOOK" ]; then
    az keyvault secret set \
      --vault-name "$KV_NAME" \
      --name "teams-webhook-url" \
      --value "$TEAMS_WEBHOOK" \
      --output none
    echo "✅ Teams webhook configured"
fi

# Restart function app
echo ""
echo "Restarting Function App..."
az functionapp restart \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --output none

echo -e "${GREEN}✅ Function App restarted${NC}"

# Verify configuration
echo ""
echo "==========================================="
echo "📊 Configuration Status"
echo "==========================================="

for secret in invoice-mailbox ap-email-address graph-tenant-id graph-client-id graph-client-secret teams-webhook-url; do
  EXISTS=$(az keyvault secret show --vault-name "$KV_NAME" --name "$secret" --query name -o tsv 2>/dev/null)
  if [ ! -z "$EXISTS" ]; then
    echo -e "  ${GREEN}✅ $secret${NC}"
  else
    echo "  ❌ $secret"
  fi
done

# Calculate next run time
CURRENT_MIN=$(date +%M)
NEXT_RUN=$((((CURRENT_MIN / 5) + 1) * 5))
if [ $NEXT_RUN -ge 60 ]; then
    NEXT_RUN=$((NEXT_RUN - 60))
fi

echo ""
echo -e "${GREEN}✅ Graph API Configuration Complete!${NC}"
echo ""
echo "📧 Your test email to dev-invoices@chelseapiers.com"
echo "   will be processed at :$(printf %02d $NEXT_RUN) past the hour"
echo ""
echo "🔍 Monitor with: ./test-live-system.sh"
echo ""
echo "⚠️ If email processing fails, check:"
echo "   1. Admin consent was granted for Mail.Read and Mail.Send"
echo "   2. The app has access to the mailbox"
echo "   3. Credentials are correct"