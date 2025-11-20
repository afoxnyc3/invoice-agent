#!/bin/bash
# Quick script to set Graph API credentials

echo "🔐 Setting Graph API Credentials"
echo "================================"

TENANT_ID="7e8833c1-ed8d-41da-b865-8179ee19d439"
CLIENT_ID="ed87010c-9abd-44e8-afe6-3e3572ba4538"
KV_NAME="kv-invoice-agent-prod"

# Colors
GREEN='\033[0;32m'
NC='\033[0m'

echo "Enter your client secret value (paste and press Enter):"
read -s CLIENT_SECRET
echo ""

if [ -z "$CLIENT_SECRET" ]; then
    echo "❌ Secret is required"
    exit 1
fi

echo "Setting Key Vault secrets..."

# Set all three values
az keyvault secret set --vault-name "$KV_NAME" --name "graph-tenant-id" --value "$TENANT_ID" --output none
echo "✅ Tenant ID configured"

az keyvault secret set --vault-name "$KV_NAME" --name "graph-client-id" --value "$CLIENT_ID" --output none
echo "✅ Client ID configured"

az keyvault secret set --vault-name "$KV_NAME" --name "graph-client-secret" --value "$CLIENT_SECRET" --output none
echo "✅ Client Secret configured"

echo ""
echo "Restarting Function App..."
az functionapp restart --name func-invoice-agent-prod --resource-group rg-invoice-agent-prod --output none
echo -e "${GREEN}✅ Function App restarted${NC}"

# Calculate next run
CURRENT_MIN=$(date +%M)
NEXT_RUN=$((((CURRENT_MIN / 5) + 1) * 5))
if [ $NEXT_RUN -ge 60 ]; then
    NEXT_RUN=$((NEXT_RUN - 60))
fi

echo ""
echo -e "${GREEN}🎉 SUCCESS! Email processing is now ACTIVE!${NC}"
echo ""
echo "Your test email will be processed at :$(printf %02d $NEXT_RUN) past the hour"
echo "Monitor with: ./test-live-system.sh"