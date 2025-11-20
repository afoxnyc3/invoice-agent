# Invoice Agent - Activation Checklist

## ✅ Infrastructure Status (COMPLETE)
- [x] Azure Functions deployed and discoverable
- [x] All 5 functions active and responding
- [x] Timer trigger configured (every 5 minutes)
- [x] Storage accounts configured
- [x] Key Vault accessible
- [x] Application Insights connected

## 🔄 Required Configuration (PENDING)

### 1. Seed Vendor Master Table
**Priority: CRITICAL** - System cannot match vendors without this data

```bash
# Run the vendor seeding script
cd infrastructure/scripts
python seed_vendors.py --env prod
```

This will populate the VendorMaster table with initial vendor data from `src/data/vendors.csv`

### 2. Configure Email Settings
**Priority: HIGH** - Required for email processing

Verify these environment variables are set in Azure:
- `INVOICE_MAILBOX`: The shared mailbox to monitor
- `AP_EMAIL`: The accounts payable email address
- `TEAMS_WEBHOOK_URL`: Teams channel webhook URL

Check current settings:
```bash
az functionapp config appsettings list \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "[?name=='INVOICE_MAILBOX' || name=='AP_EMAIL' || name=='TEAMS_WEBHOOK_URL'].{name:name, value:value}" \
  -o table
```

### 3. Grant Graph API Permissions
**Priority: HIGH** - Required for email access

The service principal needs:
- Mail.Read: To read from shared mailbox
- Mail.Send: To send to AP

Verify permissions are granted in Azure AD.

## 🧪 Testing the System

### Step 1: Test Vendor Addition (Manual)
```bash
curl -X POST "https://func-invoice-agent-prod.azurewebsites.net/api/AddVendor?code=YOUR_FUNCTION_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "RowKey": "microsoft",
    "CompanyName": "Microsoft Corporation",
    "ExpenseDept": "IT",
    "AllocationSchedule": "Monthly",
    "GLCode": "6200-IT-SOFTWARE",
    "ProductCategory": "Software Licenses",
    "BillingParty": "IT Department"
  }'
```

### Step 2: Send Test Invoice Email
1. Send an email with PDF attachment to the configured mailbox
2. Subject should contain vendor name (e.g., "Invoice from Microsoft")
3. Wait up to 5 minutes for processing

### Step 3: Monitor Processing
```bash
# Check Application Insights for activity
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --analytics-query "traces | where timestamp > ago(10m) | project timestamp, message, severityLevel | take 20" \
  -o table

# Check queue depths
az storage queue list \
  --account-name stinvoiceagentprod \
  --query "[].{name:name, messageCount:metadata.approximateMessageCount}" \
  -o table
```

## 📊 Success Metrics

Your system is working when:
1. ✅ Emails are marked as read after processing
2. ✅ Attachments appear in blob storage
3. ✅ AP receives formatted emails with vendor data
4. ✅ Teams notifications appear for each invoice
5. ✅ InvoiceTransactions table contains audit records

## 🚨 Troubleshooting

### If emails aren't being processed:
1. Check MailIngest logs in Application Insights
2. Verify Graph API authentication
3. Confirm mailbox permissions

### If vendor lookup fails:
1. Verify VendorMaster table has data
2. Check vendor name normalization (lowercase, no spaces)
3. Review ExtractEnrich function logs

### If AP emails aren't sent:
1. Check PostToAP function logs
2. Verify AP_EMAIL is configured
3. Check Graph API Mail.Send permission

## 📞 Support

- **GitHub Issues**: https://github.com/afoxnyc3/invoice-agent/issues
- **Application Insights**: Monitor real-time logs
- **Azure Portal**: Function app metrics and health

---

**System Status**: 🟢 READY FOR ACTIVATION
**Last Updated**: $(date)