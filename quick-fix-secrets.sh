#!/bin/bash
# Quick fix to set minimum required secrets for testing

echo "🚀 Quick Secret Configuration for dev-invoices@chelseapiers.com"
echo "================================================================"
echo ""

KV_NAME="kv-invoice-agent-prod"

# Set the mailbox you mentioned
echo "Setting invoice-mailbox to dev-invoices@chelseapiers.com..."
az keyvault secret set \
    --vault-name "$KV_NAME" \
    --name "invoice-mailbox" \
    --value "dev-invoices@chelseapiers.com" \
    --output none

if [ $? -eq 0 ]; then
    echo "✅ Mailbox configured"
else
    echo "❌ Failed to set mailbox - check Key Vault permissions"
    echo ""
    echo "Try running: az keyvault set-policy --name $KV_NAME --resource-group rg-invoice-agent-prod --secret-permissions get set list --object-id \$(az account show --query user.name -o tsv)"
    exit 1
fi

# Set a test AP email (you can change this)
echo "Setting ap-email-address to ap-test@chelseapiers.com..."
az keyvault secret set \
    --vault-name "$KV_NAME" \
    --name "ap-email-address" \
    --value "ap-test@chelseapiers.com" \
    --output none

echo "✅ AP email configured"

# Dummy Graph API credentials for now (won't work but prevents errors)
echo "Setting Graph API credentials (temporary)..."
az keyvault secret set --vault-name "$KV_NAME" --name "graph-tenant-id" --value "your-tenant-id" --output none
az keyvault secret set --vault-name "$KV_NAME" --name "graph-client-id" --value "your-client-id" --output none
az keyvault secret set --vault-name "$KV_NAME" --name "graph-client-secret" --value "your-secret" --output none

# Restart the function app
echo ""
echo "Restarting function app..."
az functionapp restart \
    --name func-invoice-agent-prod \
    --resource-group rg-invoice-agent-prod \
    --output none

echo "✅ Function app restarted"

echo ""
echo "================================"
echo "✅ Basic configuration complete!"
echo ""
echo "⚠️ IMPORTANT: The Graph API credentials are placeholders."
echo "   You need to set real credentials for email processing to work."
echo ""
echo "📧 Your mailbox (dev-invoices@chelseapiers.com) is now configured."
echo "   But MailIngest won't be able to read emails without valid Graph API credentials."
echo ""
echo "Next steps:"
echo "1. Create an Azure AD app registration with Mail.Read and Mail.Send permissions"
echo "2. Run ./configure-secrets.sh to set the real Graph API credentials"
echo "3. Your email will then be processed at the next 5-minute mark"