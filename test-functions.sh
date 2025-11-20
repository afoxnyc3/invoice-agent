#!/bin/bash
# Test if Azure Functions are actually callable

echo "🔍 Testing Azure Functions endpoints..."
echo ""

# Test AddVendor HTTP endpoint
echo "1. Testing AddVendor HTTP endpoint:"
FUNCTION_KEY=$(az functionapp function keys list \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --function-name AddVendor \
  --query "default" -o tsv 2>/dev/null)

if [ -z "$FUNCTION_KEY" ]; then
  echo "   ❌ No function key found - function may not be loaded"

  # Try the function app host key instead
  echo "   Trying with host key..."
  HOST_KEY=$(az functionapp keys list \
    --name func-invoice-agent-prod \
    --resource-group rg-invoice-agent-prod \
    --query "functionKeys.default" -o tsv 2>/dev/null)

  if [ -z "$HOST_KEY" ]; then
    echo "   ❌ No host key found either"
  else
    echo "   Testing with host key..."
    curl -i -X GET \
      "https://func-invoice-agent-prod.azurewebsites.net/api/AddVendor?code=$HOST_KEY" \
      2>/dev/null | head -5
  fi
else
  echo "   ✅ Function key found, testing endpoint..."
  curl -i -X GET \
    "https://func-invoice-agent-prod.azurewebsites.net/api/AddVendor?code=$FUNCTION_KEY" \
    2>/dev/null | head -5
fi

echo ""
echo "2. Checking function runtime status:"
az functionapp show --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "{state:state, status:siteConfig.functionAppScaleLimit, runtime:siteConfig.linuxFxVersion}" \
  -o table

echo ""
echo "3. Recent Application Insights errors (if any):"
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --analytics-query "exceptions | where timestamp > ago(1h) | project timestamp, message=outerMessage, type=outerType | take 5" \
  -o table 2>/dev/null || echo "   (Application Insights query requires additional permissions)"

echo ""
echo "4. Checking deployment package structure:"
echo "   Package URL: https://stinvoiceagentprod.blob.core.windows.net/github-actions-deploy/Functionapp_2025112023827865.zip"
echo "   Note: Can't directly inspect without SAS token"

echo ""
echo "5. Testing Kudu API for function list:"
PUBLISH_PROFILE=$(az functionapp deployment list-publishing-credentials \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "{username:publishingUserName, password:publishingPassword}" \
  -o json 2>/dev/null)

if [ "$PUBLISH_PROFILE" != "null" ]; then
  USERNAME=$(echo $PUBLISH_PROFILE | jq -r '.username')
  PASSWORD=$(echo $PUBLISH_PROFILE | jq -r '.password')

  echo "   Querying Kudu for functions..."
  curl -u "$USERNAME:$PASSWORD" \
    "https://func-invoice-agent-prod.scm.azurewebsites.net/api/functions" \
    2>/dev/null | jq '.[].name' 2>/dev/null || echo "   No functions returned"
else
  echo "   ❌ Could not get publishing credentials"
fi