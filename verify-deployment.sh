#!/bin/bash
# Verify Azure Functions are now working after structure fix

echo "🔍 Verifying Azure Functions Deployment..."
echo "========================================="
echo ""

# Wait a moment for deployment to propagate
echo "⏳ Waiting 30s for deployment to fully propagate..."
sleep 30

# 1. Check if functions are listed
echo "1️⃣ Checking if functions are discoverable:"
FUNCTIONS=$(az functionapp function list \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "[].name" -o tsv)

if [ -z "$FUNCTIONS" ]; then
  echo "   ❌ No functions found - deployment may still be in progress"
  echo "   Please wait and try again in 2-3 minutes"
else
  echo "   ✅ Functions discovered:"
  echo "$FUNCTIONS" | sed 's/^/      - /'
fi

echo ""

# 2. Test HTTP endpoint
echo "2️⃣ Testing AddVendor HTTP endpoint:"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
  "https://func-invoice-agent-prod.azurewebsites.net/api/AddVendor")

if [ "$RESPONSE" = "401" ] || [ "$RESPONSE" = "403" ]; then
  echo "   ✅ HTTP endpoint responding (401/403 = auth required, function exists!)"
elif [ "$RESPONSE" = "404" ]; then
  echo "   ❌ HTTP endpoint returning 404 - function not found"
else
  echo "   🔄 HTTP response code: $RESPONSE"
fi

echo ""

# 3. Check app status
echo "3️⃣ Function App Status:"
az functionapp show \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "{State:state, HostStatus:siteConfig.functionsRuntimeScaleMonitoringEnabled}" \
  -o table

echo ""
echo "========================================="
echo "📊 Deployment Verification Complete"
echo ""
echo "If functions are not yet visible:"
echo "  1. Wait 2-3 more minutes for deployment"
echo "  2. Run this script again: ./verify-deployment.sh"
echo "  3. Check GitHub Actions for deployment status"
echo ""
echo "Once functions are visible, the system is OPERATIONAL! 🎉"