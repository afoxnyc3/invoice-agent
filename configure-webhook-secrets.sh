#!/bin/bash
# Configure webhook secrets for Microsoft Graph Change Notifications

set -e

ENV="dev"
RESOURCE_GROUP="rg-invoice-agent-${ENV}"
FUNCTION_APP="func-invoice-agent-${ENV}"
KEY_VAULT="kv-invoice-agent-${ENV}"

echo "🔐 Configuring Webhook Secrets for ${ENV} environment"
echo "========================================================"
echo ""

# Step 1: Generate client state secret
echo "📝 Step 1: Generating client state secret..."
CLIENT_STATE=$(openssl rand -base64 32)
echo "   Generated: ${CLIENT_STATE:0:20}..."
echo ""

# Step 2: Get function key for MailWebhook
echo "📝 Step 2: Getting function key..."
FUNCTION_KEY=$(az functionapp keys list \
  --name "$FUNCTION_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --query "functionKeys.default" -o tsv)

if [ -z "$FUNCTION_KEY" ]; then
  echo "❌ Failed to retrieve function key"
  exit 1
fi
echo "   Retrieved: ${FUNCTION_KEY:0:20}..."
echo ""

# Step 3: Construct webhook URL
echo "📝 Step 3: Constructing webhook URL..."
WEBHOOK_URL="https://${FUNCTION_APP}.azurewebsites.net/api/MailWebhook?code=${FUNCTION_KEY}"
echo "   URL: ${WEBHOOK_URL:0:60}..."
echo ""

# Step 4: Add secrets to Key Vault
echo "📝 Step 4: Adding secrets to Key Vault..."
echo "   Adding graph-client-state..."
az keyvault secret set \
  --vault-name "$KEY_VAULT" \
  --name "graph-client-state" \
  --value "$CLIENT_STATE" \
  --output none

echo "   Adding mail-webhook-url..."
az keyvault secret set \
  --vault-name "$KEY_VAULT" \
  --name "mail-webhook-url" \
  --value "$WEBHOOK_URL" \
  --output none
echo "   ✅ Secrets added to Key Vault"
echo ""

# Step 5: Update Function App settings
echo "📝 Step 5: Updating Function App settings..."
az functionapp config appsettings set \
  --name "$FUNCTION_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --settings \
    "GRAPH_CLIENT_STATE=@Microsoft.KeyVault(SecretUri=https://${KEY_VAULT}.vault.azure.net/secrets/graph-client-state/)" \
    "MAIL_WEBHOOK_URL=@Microsoft.KeyVault(SecretUri=https://${KEY_VAULT}.vault.azure.net/secrets/mail-webhook-url/)" \
  --output none
echo "   ✅ App settings updated"
echo ""

# Step 6: Restart Function App
echo "📝 Step 6: Restarting Function App..."
az functionapp restart \
  --name "$FUNCTION_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --output none
echo "   ✅ Restart initiated"
echo ""

echo "⏳ Waiting 30 seconds for Function App to restart..."
sleep 30
echo ""

echo "✅ Webhook Configuration Complete!"
echo "===================================="
echo ""
echo "Next Steps:"
echo "1. Verify app settings loaded: Check Function App → Configuration in Azure Portal"
echo "2. Initialize subscription: Manually trigger SubscriptionManager function"
echo "3. Test webhook: Send email to dev-invoices@chelseapiers.com"
echo ""
echo "To manually trigger SubscriptionManager:"
echo "  Portal: Function App → SubscriptionManager → Code + Test → Test/Run"
echo ""
