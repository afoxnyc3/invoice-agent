#!/bin/bash
# Production Diagnostics Script

set -e

RG="rg-invoice-agent-prod"
FUNC_NAME="func-invoice-agent-prod"

echo "========================================="
echo "Azure Functions Production Diagnostics"
echo "========================================="
echo ""

echo "1. Function App Basic Status"
echo "-----------------------------"
az functionapp show --name $FUNC_NAME --resource-group $RG \
  --query "{State:state, PythonVersion:siteConfig.pythonVersion, LinuxFxVersion:siteConfig.linuxFxVersion, RunFromPackage:siteConfig.appSettings[?name=='WEBSITE_RUN_FROM_PACKAGE'].value|[0]}" \
  --output table

echo ""
echo "2. Checking Loaded Functions"
echo "-----------------------------"
FUNCTIONS=$(az functionapp function list --name $FUNC_NAME --resource-group $RG --output json 2>/dev/null)
if [ "$FUNCTIONS" == "[]" ] || [ -z "$FUNCTIONS" ]; then
    echo "❌ No functions loaded"
else
    echo "✅ Functions loaded:"
    echo "$FUNCTIONS" | jq -r '.[].name'
fi

echo ""
echo "3. Checking Key App Settings"
echo "-----------------------------"
az functionapp config appsettings list --name $FUNC_NAME --resource-group $RG \
  --query "[?name=='FUNCTIONS_WORKER_RUNTIME' || name=='FUNCTIONS_EXTENSION_VERSION' || name=='PYDANTIC_PURE_PYTHON'].{Name:name, Value:value}" \
  --output table

echo ""
echo "4. Recent Deployment Info"
echo "-------------------------"
echo "Checking last GitHub deployment..."
gh run list --workflow=ci-cd.yml --limit 1 --json conclusion,updatedAt,headBranch | jq -r '.[0] | "Branch: \(.headBranch)\nStatus: \(.conclusion)\nTime: \(.updatedAt)"'

echo ""
echo "5. Testing HTTP Endpoint"
echo "------------------------"
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "https://$FUNC_NAME.azurewebsites.net/api/AddVendor")
if [ "$HTTP_STATUS" == "404" ]; then
    echo "❌ AddVendor endpoint returns 404 (function not loaded)"
elif [ "$HTTP_STATUS" == "401" ] || [ "$HTTP_STATUS" == "403" ]; then
    echo "✅ AddVendor endpoint exists (returns $HTTP_STATUS - auth required)"
else
    echo "⚠️  AddVendor endpoint returns: $HTTP_STATUS"
fi

echo ""
echo "6. Function App Health Check"
echo "----------------------------"
HEALTH=$(curl -s "https://$FUNC_NAME.azurewebsites.net/" -w "\nStatus: %{http_code}" 2>/dev/null | tail -1)
echo "Root endpoint: $HEALTH"

echo ""
echo "========================================="
echo "Diagnostic Summary"
echo "========================================="

if [ "$FUNCTIONS" == "[]" ] || [ -z "$FUNCTIONS" ]; then
    echo "⚠️  ISSUE DETECTED: Functions are not loading"
    echo ""
    echo "Possible causes:"
    echo "1. Deployment package issue (missing files)"
    echo "2. Python import errors during startup"
    echo "3. Missing environment variables"
    echo "4. Function trigger configuration issues"
    echo ""
    echo "Recommended actions:"
    echo "1. Check SCM site for deployment files"
    echo "2. Review Application Insights for import errors"
    echo "3. Restart the Function App"
    echo "4. Re-deploy if necessary"
else
    echo "✅ Functions are loaded and ready"
fi