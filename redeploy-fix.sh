#!/bin/bash
# Quick redeploy script to fix function loading issue

echo "🔧 Redeploying Azure Functions with fixed permissions..."

# Ensure we're in the right directory
cd "$(dirname "$0")"

# Commit the permission fixes
echo "📝 Committing permission fixes..."
git add src/functions/*/function.json
git commit -m "fix: correct function.json file permissions for Azure runtime

All function.json files now have 644 permissions instead of 600,
allowing Azure Functions runtime to read and discover the functions.

This should resolve the issue where functions deploy but aren't recognized."

# Push to trigger CI/CD
echo "🚀 Pushing to main to trigger deployment..."
git push origin main

echo "✅ Deployment triggered!"
echo ""
echo "Monitor deployment:"
echo "  - GitHub Actions: https://github.com/yourusername/invoice-agent/actions"
echo "  - Azure Portal: https://portal.azure.com"
echo ""
echo "After deployment completes (~3-5 min), verify functions are loaded:"
echo "  az functionapp function list --name func-invoice-agent-prod --resource-group rg-invoice-agent-prod"