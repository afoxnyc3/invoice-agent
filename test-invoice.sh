#!/bin/bash
# Test invoice processing pipeline

echo "📧 Testing Invoice Processing Pipeline"
echo "======================================"
echo ""

# Trigger MailIngest
echo "1. Triggering MailIngest function..."
az functionapp function invoke \
  --name func-invoice-agent-prod \
  --function-name MailIngest \
  --resource-group rg-invoice-agent-prod \
  2>/dev/null || echo "   (Manual trigger via Portal if this fails)"

echo ""
echo "2. Waiting 10 seconds for processing..."
sleep 10

# Check Application Insights logs
echo ""
echo "3. Checking Application Insights for activity..."
az monitor app-insights query \
  --app appi-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --analytics-query "traces | where timestamp > ago(5m) | where message contains 'MailIngest' or message contains 'invoice' or message contains 'dev-invoices' | project timestamp, message, severityLevel | order by timestamp desc | take 10" \
  --output table

echo ""
echo "4. Checking queue depths..."
az storage queue show \
  --name raw-mail \
  --account-name stinvoiceagentprod \
  --query approximateMessageCount \
  --output tsv 2>/dev/null | xargs -I {} echo "   raw-mail queue: {} messages"

az storage queue show \
  --name to-post \
  --account-name stinvoiceagentprod \
  --query approximateMessageCount \
  --output tsv 2>/dev/null | xargs -I {} echo "   to-post queue: {} messages"

echo ""
echo "5. Checking for blob uploads..."
az storage blob list \
  --container-name invoices \
  --account-name stinvoiceagentprod \
  --query "[?properties.lastModified > '$(date -u -d '5 minutes ago' '+%Y-%m-%dT%H:%M:%SZ')'].{Name:name, Modified:properties.lastModified}" \
  --output table 2>/dev/null || echo "   (Check Azure Portal for recent uploads)"

echo ""
echo "======================================"
echo "✅ Test complete!"
echo ""
echo "If invoice was processed:"
echo "- Check Teams channel for notification"
echo "- Email will remain 'unread' (security trade-off)"
echo "- Blob storage will have attachment"
echo ""
echo "If not processed:"
echo "- Verify email has attachments"
echo "- Check Graph API permissions (Mail.Read)"
echo "- Review Application Insights for errors"