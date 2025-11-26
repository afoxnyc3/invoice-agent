#!/bin/bash
# Configure the existing invoice-agent-graph-api app registration

echo "🔐 Configuring Your Existing Graph API App Registration"
echo "======================================================"
echo ""
echo "✅ Found: invoice-agent-graph-api"
echo "App ID: ed87010c-9abd-44e8-afe6-3e3572ba4538"
echo "Tenant ID: 7e8833c1-ed8d-41da-b865-8179ee19d439"
echo ""

# Pre-filled values
TENANT_ID="7e8833c1-ed8d-41da-b865-8179ee19d439"
CLIENT_ID="ed87010c-9abd-44e8-afe6-3e3572ba4538"
KV_NAME="kv-invoice-agent-prod"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "📋 Before proceeding, you need to:"
echo "1. Go to Azure Portal > Azure Active Directory > App registrations"
echo "2. Find 'invoice-agent-graph-api' (or search for App ID: $CLIENT_ID)"
echo "3. Go to 'Certificates & secrets' tab"
echo "4. Click 'New client secret'"
echo "5. Add description: 'Invoice Agent Production'"
echo "6. Choose expiry (12 or 24 months recommended)"
echo "7. Copy the secret VALUE (not the ID)"
echo ""

read -p "Press Enter when you have the client secret ready..."

echo ""
echo "Enter the client secret value (input will be hidden):"
read -s CLIENT_SECRET
echo ""

if [ -z "$CLIENT_SECRET" ]; then
    echo -e "${RED}❌ Client secret is required${NC}"
    exit 1
fi

echo "Setting Key Vault secrets..."

# Set tenant ID
az keyvault secret set \
  --vault-name "$KV_NAME" \
  --name "graph-tenant-id" \
  --value "$TENANT_ID" \
  --output none

echo "✅ Tenant ID configured: $TENANT_ID"

# Set client ID
az keyvault secret set \
  --vault-name "$KV_NAME" \
  --name "graph-client-id" \
  --value "$CLIENT_ID" \
  --output none

echo "✅ Client ID configured: $CLIENT_ID"

# Set client secret
az keyvault secret set \
  --vault-name "$KV_NAME" \
  --name "graph-client-secret" \
  --value "$CLIENT_SECRET" \
  --output none

echo "✅ Client Secret configured"

# Optional: Set Teams webhook
echo ""
echo "Would you like to configure Teams notifications? (y/n)"
read -p "> " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Enter Teams webhook URL:"
    read TEAMS_WEBHOOK
    if [ ! -z "$TEAMS_WEBHOOK" ]; then
        az keyvault secret set \
          --vault-name "$KV_NAME" \
          --name "teams-webhook-url" \
          --value "$TEAMS_WEBHOOK" \
          --output none
        echo "✅ Teams webhook configured"
    fi
fi

# Restart function app
echo ""
echo "Restarting Function App to apply changes..."
az functionapp restart \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --output none

echo -e "${GREEN}✅ Function App restarted${NC}"

# Verify configuration
echo ""
echo "======================================================"
echo "📊 Configuration Complete!"
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
    echo "  ❌ $secret"
  fi
done

# Calculate next run
CURRENT_MIN=$(date +%M)
NEXT_RUN=$((((CURRENT_MIN / 5) + 1) * 5))
if [ $NEXT_RUN -ge 60 ]; then
    NEXT_RUN=$((NEXT_RUN - 60))
fi

echo ""
echo -e "${GREEN}🎉 Email Processing is Now Active!${NC}"
echo ""
echo "📧 Your test email to dev-invoices@chelseapiers.com (sent at 10:52 PM)"
echo "   will be processed at :$(printf %02d $NEXT_RUN) past the hour"
echo ""
echo "🔍 Monitor processing:"
echo "   ./test-live-system.sh"
echo ""
echo "📝 The email will be:"
echo "   1. Read from dev-invoices@chelseapiers.com"
echo "   2. Vendor extracted and matched"
echo "   3. Enriched with GL codes"
echo "   4. Sent to ap@chelseapiers.com"
echo "   5. Marked as read in the inbox"