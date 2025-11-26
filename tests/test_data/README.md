# Test Invoice Data

This directory contains test invoice templates and utilities for end-to-end testing of the Invoice Agent system.

## Files

- **`invoice_templates.py`** - Invoice content generator for all 25 MVP vendors
- **`../scripts/send_test_emails.py`** - Script to send test invoices via Graph API

## Generated Test Data

The invoice generator creates realistic invoices for 25 vendors across 7 departments:

### IT Department (15 vendors)
1. **Adobe Inc** - Creative Cloud subscriptions (~$2,750/month)
2. **Microsoft Corporation** - Office 365 + Azure (~$6,050/month)
3. **Amazon Web Services** - Cloud infrastructure (~$634/month)
4. **Zoom Video Communications** - Video conferencing (~$1,500/month)
5. **Slack Technologies** - Team collaboration (~$1,500/month)
6. **Google Workspace** - Email and productivity (~$960/month)
7. **Dropbox** - File storage (~$2,400/year)
8. **Verizon** - Telecom services (~$1,050/month)
9. **AT&T** - Fiber + mobile (~$2,450/month)
10. **Oracle** - Database licenses (~$47,500/year)
11. **ServiceNow** - IT service management (~$36,000/year)

### Sales Department (1 vendor)
12. **Salesforce** - CRM platform (~$90,000/year)

### Marketing Department (1 vendor)
13. **HubSpot** - Marketing automation (~$1,090/month)

### Finance Department (1 vendor)
14. **QuickBooks** - Accounting software (~$7,500/year)

### Legal Department (1 vendor)
15. **DocuSign** - Electronic signatures (~$4,800/year)

### HR Department (4 vendors)
16. **Workday** - HR management system (~$48,000/year)
17. **ADP** - Payroll processing (~$1,250/month)
18. **LinkedIn** - Recruiting platform (~$44,995/year)
19. **Indeed** - Job postings (~$2,990/month)

### Operations Department (4 vendors)
20. **FedEx** - Shipping services (~$2,678/month)
21. **UPS** - Shipping services (~$2,625/month)
22. **Staples** - Office supplies (~$2,245/month)
23. **Amazon Business** - Business supplies (~$1,702/month)

### Facilities Department (2 vendors)
24. **Grainger** - Industrial supplies (~$2,816/month)
25. **Home Depot** - Maintenance supplies (~$2,357/month)

## Invoice Content

Each generated invoice includes:

- **Vendor Information**: Name, billing email, address
- **Invoice Details**: Number, date, due date (30 days)
- **Line Items**: Realistic products/services for the vendor
  - Description
  - Quantity
  - Rate
  - Amount
- **Totals**: Subtotal, tax (8%), total due
- **Payment Terms**: Net 30, allocation schedule
- **Department**: Expense department code

## Email Sending Details

Invoices are sent with:
- **From**: Realistic sender addresses (billing@adobe.com, invoices@microsoft.com, etc.)
- **To**: Target mailbox (dev-invoices@chelseapiers.com or custom)
- **Subject**: "Invoice {number} from {vendor}"
- **Body**: Professional email format with invoice details
- **Attachment**: Invoice text included in body (PDF generation for Phase 2)

## Usage Examples

### 1. List All Available Vendors
```bash
python scripts/send_test_emails.py --list
```

### 2. Send All Test Invoices
```bash
# Send all 25 invoices with 5-second delay between each
python scripts/send_test_emails.py --all --delay 5
```

### 3. Send Specific Vendors
```bash
# Send Adobe, Microsoft, and AWS invoices
python scripts/send_test_emails.py --vendors "Adobe" "Microsoft" "AWS"
```

### 4. Send Random Samples
```bash
# Send 5 random invoices
python scripts/send_test_emails.py --count 5 --delay 3

# Send 1 random invoice
python scripts/send_test_emails.py --random
```

### 5. Test Without Sending (Dry Run)
```bash
# Preview what would be sent
python scripts/send_test_emails.py --all --dry-run
```

### 6. Custom Target Mailbox
```bash
# Send to a different mailbox
python scripts/send_test_emails.py --vendors "Adobe" --mailbox "test@example.com"
```

## Testing Scenarios

### Scenario 1: Known Vendor (Happy Path)
```bash
python scripts/send_test_emails.py --vendors "Adobe"
```
**Expected**:
- ✅ Email processed via webhook (<10 seconds)
- ✅ Vendor matched: "Adobe Inc"
- ✅ GL Code applied: 6100
- ✅ Department: IT
- ✅ Sent to AP mailbox
- ✅ Teams notification (green)

### Scenario 2: Unknown Vendor
```bash
# Create a test email from an unknown domain (manual process)
# Or modify invoice_templates.py to add a fake vendor
```
**Expected**:
- ✅ Email processed
- ⚠️ Vendor not found
- ✅ Registration email sent to original sender
- ⚠️ Teams notification (orange warning)
- ✅ GL Code: 0000 (unknown)

### Scenario 3: High Volume Test
```bash
python scripts/send_test_emails.py --all --delay 2
```
**Expected**:
- ✅ All 25 invoices processed
- ✅ No errors or missed emails
- ✅ Webhook latency <10 seconds each
- ✅ Queue processing smooth
- ✅ All Teams notifications sent

### Scenario 4: Different Departments
```bash
# Test IT vendors
python scripts/send_test_emails.py --vendors "Adobe" "Microsoft" "AWS"

# Test HR vendors
python scripts/send_test_emails.py --vendors "Workday" "ADP" "LinkedIn"

# Test Operations vendors
python scripts/send_test_emails.py --vendors "FedEx" "UPS" "Staples"
```
**Expected**:
- ✅ Correct department codes applied
- ✅ Different GL codes per department
- ✅ Proper allocation schedules

### Scenario 5: Reseller Vendor (Special Case)
If Myriad360 is added to vendor list with `ProductCategory="Reseller"`:
**Expected**:
- ✅ Email processed
- ⚠️ Flagged for manual review
- ✅ Teams notification (orange)
- ✅ GL Code: 0000 (requires product extraction)

## Monitoring Test Results

### Application Insights Queries

**Watch webhook processing:**
```kql
traces
| where timestamp > ago(5m)
| where message contains "MailWebhook" or message contains "MailWebhookProcessor"
| order by timestamp desc
```

**Check vendor matching:**
```kql
traces
| where timestamp > ago(5m)
| where message contains "ExtractEnrich"
| where message contains "matched" or message contains "not found"
| order by timestamp desc
```

**Monitor end-to-end flow:**
```kql
traces
| where timestamp > ago(5m)
| where customDimensions.TransactionId != ""
| order by timestamp desc
| project timestamp, message, customDimensions.TransactionId
```

### Azure CLI Commands

**Check queue depths:**
```bash
az storage queue list \
  --connection-string "$(az storage account show-connection-string \
    --name stinvoiceagentdev \
    --resource-group rg-invoice-agent-dev \
    --query connectionString -o tsv)" \
  --query "[].{name:name, messages:metadata.approximateMessageCount}"
```

**Check transaction log:**
```bash
az storage entity query \
  --table-name InvoiceTransactions \
  --connection-string "..." \
  --filter "Timestamp gt datetime'$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)'"
```

## Expected Performance

Based on MVP targets:

- **Webhook Latency**: <10 seconds (email arrival → MailWebhook triggered)
- **End-to-End Processing**: <60 seconds (email arrival → Teams notification)
- **Vendor Match Rate**: >80% (20/25 = 80% minimum)
- **Error Rate**: <1% (0 errors expected with valid test data)

## Troubleshooting

### Issue: Emails not received
**Check:**
1. INVOICE_MAILBOX configured correctly
2. Graph API permissions (Mail.Read)
3. Webhook subscription active

### Issue: Vendor not matched
**Check:**
1. VendorMaster table populated
2. Email domain extraction working
3. Case-insensitive matching logic

### Issue: Slow processing
**Check:**
1. Queue depths (backlog?)
2. Application Insights traces
3. Function app scaling

### Issue: Teams notifications not sent
**Check:**
1. TEAMS_WEBHOOK_URL configured
2. Webhook URL valid
3. Notify function logs

## Phase 2 Enhancements

When PDF extraction is implemented:
- [ ] Generate actual PDF files (not just text)
- [ ] Include invoice images/logos
- [ ] Test OCR accuracy
- [ ] Test AI vendor extraction with variations
- [ ] Add intentional typos/formatting issues

## Contributing

To add new test vendors:

1. Add vendor to `infrastructure/data/vendors.csv`
2. Update `_generate_line_items()` in `invoice_templates.py`
3. Add realistic line items for the vendor
4. Test with `--vendors "NewVendor"`

## Cost Considerations

- **Email sending**: Free (Graph API included in M365)
- **Function executions**: ~$0.60/month (25 invoices × 6 functions)
- **Storage**: Negligible (<$0.01/month)
- **Application Insights**: Included in free tier

**Total cost for testing**: <$1/month
