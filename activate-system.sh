#!/bin/bash
# Invoice Agent - System Activation Script
# This script performs the final activation steps

echo "🚀 Invoice Agent System Activation"
echo "=================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Check function status
echo "1️⃣ Checking Azure Functions Status..."
FUNCTIONS=$(az functionapp function list \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "[].name" -o tsv 2>/dev/null | wc -l)

if [ "$FUNCTIONS" -eq "5" ]; then
  echo -e "   ${GREEN}✅ All 5 functions deployed${NC}"
else
  echo -e "   ${RED}❌ Only $FUNCTIONS functions found (expected 5)${NC}"
  exit 1
fi

# Step 2: Seed vendor data
echo ""
echo "2️⃣ Seeding Vendor Master Table..."
echo "   This will populate the vendor lookup table with initial data."
read -p "   Proceed with vendor seeding? (y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
  cd infrastructure/scripts
  python seed_vendors.py --env prod
  if [ $? -eq 0 ]; then
    echo -e "   ${GREEN}✅ Vendor data seeded successfully${NC}"
  else
    echo -e "   ${YELLOW}⚠️ Vendor seeding may have failed - check logs${NC}"
  fi
  cd ../..
else
  echo -e "   ${YELLOW}⚠️ Skipped vendor seeding${NC}"
fi

# Step 3: Verify Key Vault secrets
echo ""
echo "3️⃣ Checking Key Vault Configuration..."
SECRETS_CONFIGURED=true

# Check if secrets exist in Key Vault
for secret in "invoice-mailbox" "ap-email-address" "teams-webhook-url"; do
  SECRET_EXISTS=$(az keyvault secret show \
    --vault-name kv-invoice-agent-prod \
    --name "$secret" \
    --query "name" -o tsv 2>/dev/null)

  if [ -z "$SECRET_EXISTS" ]; then
    echo -e "   ${RED}❌ Missing secret: $secret${NC}"
    SECRETS_CONFIGURED=false
  else
    echo -e "   ${GREEN}✅ Secret configured: $secret${NC}"
  fi
done

if [ "$SECRETS_CONFIGURED" = false ]; then
  echo -e "   ${YELLOW}⚠️ Some secrets are missing. Please configure them in Key Vault.${NC}"
fi

# Step 4: Test HTTP endpoint
echo ""
echo "4️⃣ Testing AddVendor HTTP Endpoint..."
FUNCTION_KEY=$(az functionapp keys list \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "functionKeys.default" -o tsv 2>/dev/null)

if [ ! -z "$FUNCTION_KEY" ]; then
  RESPONSE=$(curl -s -X POST \
    "https://func-invoice-agent-prod.azurewebsites.net/api/AddVendor?code=$FUNCTION_KEY" \
    -H "Content-Type: application/json" \
    -d '{"test": "ping"}' \
    -w "%{http_code}" \
    -o /dev/null)

  if [ "$RESPONSE" = "400" ]; then
    echo -e "   ${GREEN}✅ HTTP endpoint responding (400 = validation working)${NC}"
  else
    echo -e "   ${YELLOW}⚠️ Unexpected response: $RESPONSE${NC}"
  fi
else
  echo -e "   ${YELLOW}⚠️ Could not retrieve function key${NC}"
fi

# Step 5: Check timer trigger
echo ""
echo "5️⃣ Checking MailIngest Timer Trigger..."
SCHEDULE=$(az functionapp function show \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --function-name MailIngest \
  --query "config.bindings[0].schedule" -o tsv 2>/dev/null)

if [ "$SCHEDULE" = "0 */5 * * * *" ]; then
  echo -e "   ${GREEN}✅ Timer configured: runs every 5 minutes${NC}"

  # Calculate next run time
  CURRENT_MIN=$(date +%M)
  NEXT_RUN=$((((CURRENT_MIN / 5) + 1) * 5))
  if [ $NEXT_RUN -ge 60 ]; then
    NEXT_RUN=$((NEXT_RUN - 60))
  fi
  echo -e "   📅 Next run: approximately at :$(printf %02d $NEXT_RUN) past the hour"
else
  echo -e "   ${YELLOW}⚠️ Timer schedule: $SCHEDULE${NC}"
fi

# Final summary
echo ""
echo "=================================="
echo "📊 Activation Summary"
echo "=================================="

if [ "$SECRETS_CONFIGURED" = true ] && [ "$FUNCTIONS" -eq "5" ]; then
  echo -e "${GREEN}✅ System is ACTIVATED and ready to process invoices!${NC}"
  echo ""
  echo "📧 To test the system:"
  echo "   1. Send an invoice email to the configured mailbox"
  echo "   2. Wait up to 5 minutes for processing"
  echo "   3. Check Teams channel for notifications"
  echo "   4. Verify AP received the processed email"
else
  echo -e "${YELLOW}⚠️ System needs additional configuration${NC}"
  echo ""
  echo "📋 Required actions:"
  if [ "$SECRETS_CONFIGURED" = false ]; then
    echo "   - Configure missing Key Vault secrets"
  fi
  echo "   - Run vendor seeding if not completed"
  echo "   - Test with a sample invoice email"
fi

echo ""
echo "📚 Documentation: See ACTIVATION_CHECKLIST.md for details"
echo "🔍 Monitor logs: Application Insights in Azure Portal"