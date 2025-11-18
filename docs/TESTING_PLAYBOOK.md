# Email Safety Testing Playbook

## Objective
Verify the invoice agent can safely process emails without:
- ❌ Infinite email loops
- ❌ Duplicate sends to AP mailbox
- ❌ Unauthorized recipients
- ❌ Unprocessed/stuck messages

## Architecture Under Test

```
Test Invoice Email              System Processing                  Verification
(from vendor)                   ↓                                   ↓
    ↓
    ├→ dev-invoices@            MailIngest (5min timer)            Check inbox
    │  chelseapiers.com          ↓ (captures Graph API message ID)
    │                            raw-mail queue
    │                             ↓
    │                        ExtractEnrich (queue trigger)
    │                             ↓ (passes message ID through)
    │                            to-post queue
    │                             ↓
    │                        PostToAP (queue trigger)
    │                             ├→ Dedup check (by Graph API message ID)
    │                             ├→ Recipient validation (only dev-ap)
    │                             └→ Send email + log transaction
    │                                 ↓
    │                        dev-ap@                          Check count = 1
    │                        chelseapiers.com
    │
    └→ InvoiceTransactions table
       ├→ Status: processed
       ├→ OriginalMessageId: <Graph API message ID>
       └→ Count should = 1
```

## Safety Constraints to Verify

| Constraint | How to Check | Expected | Failure = Loop |
|-----------|-------------|----------|---|
| **One email to AP** | Count unread in dev-ap mailbox | Exactly 1 | Multiple = Loop |
| **No duplicate processing** | Count transactions with same message ID | Exactly 1 | Multiple = Duplicate |
| **Deduplication works** | Check OriginalMessageId field in transaction | Present & matches | Missing = Broken |
| **Correct recipient only** | Verify AP email is dev-ap@chelseapiers.com | Correct recipient | Wrong = Bad config |
| **No stuck messages** | Check queue depths | All empty | Non-zero = Stuck |

## Testing Flow

### Phase 1: Preparation

**1. Verify Azure credentials are configured**
```bash
# Check that you can access Azure resources
az account show

# Verify Function App is running
az functionapp show \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query state
```

**2. Set environment variables**
```bash
export GRAPH_TENANT_ID="<your-tenant-id>"
export GRAPH_CLIENT_ID="<your-client-id>"
export GRAPH_CLIENT_SECRET="<your-secret>"
export INVOICE_MAILBOX="dev-invoices@chelseapiers.com"
export AP_EMAIL_ADDRESS="dev-ap@chelseapiers.com"
export STORAGE_ACCOUNT="stinvoiceagentprod"
```

**3. Verify mailboxes are accessible**
```bash
# Quick test of Graph API access
python -c "
from shared.graph_client import GraphAPIClient
import sys
sys.path.insert(0, 'src')
try:
    client = GraphAPIClient()
    print('✅ Graph API credentials valid')
except Exception as e:
    print(f'❌ Error: {e}')
"
```

### Phase 2: Send Test Email

**Option A: Manual Send (Most Reliable)**

1. Open Outlook/Gmail and compose new email
2. Use these details:
   - **To:** `dev-invoices@chelseapiers.com`
   - **From:** Use a vendor address or external email (e.g., `test@adobe.com`)
   - **Subject:** `Test Invoice #<TIMESTAMP>`
   - **Body:** Any text
   - **Attachment:** Any PDF file (can be blank or real invoice)

3. Send the email
4. Note the time (used for monitoring)

**Option B: Script (if you have Graph API send permissions)**

```bash
python scripts/test_email_safety.py contact@adobe.com
```

### Phase 3: Monitor Processing

**Wait 5-10 seconds** (MailIngest runs every 5 minutes, but queues process immediately)

Then run:

```bash
# Monitor test execution
python scripts/analyze_test_results.py
```

**Output includes:**
- ✅/❌ Invoice mailbox status
- ✅/❌ AP mailbox email count (MUST be 1)
- ✅/❌ Transaction created with message ID
- ✅/❌ Queue depths (MUST be 0)

### Phase 4: Detailed Validation

Run detailed analysis:

```bash
python scripts/analyze_test_results.py
```

**Check each section:**

**Section 1: Invoice Mailbox**
```
⚠️  EXPECTED: No unread emails (processed by MailIngest)
✅ PASS: Inbox is empty after processing
```

**Section 2: AP Mailbox**
```
✅ EXPECTED: Exactly ONE unread email from system
   ✅ PASS: Found 1 system email
   ❌ FAIL: Found multiple emails = LOOP
   ⚠️  UNCERTAIN: No emails yet = Still processing
```

**Section 3: Transactions**
```
✅ EXPECTED: Exactly ONE transaction with Test Invoice subject
   ✅ PASS: Found 1 transaction, Status=processed
   ❌ FAIL: Found multiple = DUPLICATE PROCESSING
   ✅ PASS: OriginalMessageId captured = DEDUP WORKS
   ❌ FAIL: No OriginalMessageId = DEDUP BROKEN
```

**Section 4: Queues**
```
✅ EXPECTED: All queues empty
   ✅ PASS: All show 0 messages
   ⚠️  WARNING: Non-zero = Message stuck in processing
```

## Success Criteria

**✅ ALL TESTS PASS if:**

1. **Email received** ✅ One email in dev-ap mailbox from system
2. **Processed once** ✅ Exactly one transaction created
3. **Deduplication active** ✅ OriginalMessageId captured
4. **No loops** ✅ Only one email sent (no multiple sends)
5. **No stuck messages** ✅ All queues empty
6. **Teams notification** ✅ (optional) Check Teams channel for notification

## Troubleshooting

### "No email in AP mailbox"

**Likely cause:** Processing still in progress or email stuck in queue

**Check:**
```bash
# Check if email arrived in invoice inbox yet
python scripts/verify_test_emails.py

# Check transaction table (may not be processed yet)
python scripts/check_transactions.py 2

# Check if message is stuck in queue
az storage queue metadata show --name raw-mail --account-name stinvoiceagentprod
```

**Fix:** Wait 30 seconds, re-run analysis

### "Multiple emails in AP mailbox" ⚠️ LOOP DETECTED

**This is a critical failure!**

**Immediate action:**
1. Stop any further test emails
2. Check the logs in Application Insights
3. Review deduplication logic in PostToAP
4. Check if sender/recipient addresses are different

**Possible causes:**
- Deduplication broken (message ID not captured)
- Recipient validation failed (sending back to invoice mailbox)
- Queue retry loop (message retried multiple times)

### "Multiple transactions created"

**This indicates duplicate processing!**

**Check:**
```bash
# See all transactions from past 2 hours
python scripts/analyze_test_results.py | grep "Transaction"

# Check if they have same OriginalMessageId
```

**Possible causes:**
- Graph API message ID not being passed through pipeline
- Queue message being reprocessed
- Idempotency not working

### "No OriginalMessageId in transaction"

**Deduplication is broken!**

**Check:**
1. MailIngest is capturing `email["id"]` from Graph API
2. message ID is being passed through RawMail model
3. message ID is being passed through ExtractEnrich to EnrichedInvoice
4. PostToAP is storing it in InvoiceTransaction

**Fix:** Review commit f63d909 (deduplication fix)

## Monitoring Commands

**Quick health check:**
```bash
# All in one
python scripts/analyze_test_results.py
```

**Detailed troubleshooting:**
```bash
# Check mailboxes
python scripts/verify_test_emails.py

# Check transactions
python scripts/check_transactions.py 2

# Check queues (requires Azure CLI)
az storage queue metadata show --name raw-mail --account-name stinvoiceagentprod
```

**Application Insights (via Azure Portal):**
1. Go to `ai-invoice-agent-prod` in Azure Portal
2. View → Logs → Run query:
```kusto
requests
| where timestamp > ago(30m)
| where name in ("MailIngest", "ExtractEnrich", "PostToAP", "Notify")
| order by timestamp desc
```

## Safety Assertion Summary

If all these checks pass, the system is safe:

- [ ] ✅ Only ONE email in AP mailbox
- [ ] ✅ Only ONE transaction created
- [ ] ✅ OriginalMessageId captured and matches
- [ ] ✅ All queues empty
- [ ] ✅ No error logs in Application Insights
- [ ] ✅ Sender is correct vendor address
- [ ] ✅ Recipient is ONLY dev-ap@chelseapiers.com

**Then you can:** Proceed to production with confidence! 🚀

## Next Steps After Validation

1. **Send multiple test emails** from different vendors
   - Adobe, Microsoft, AWS, Salesforce, etc.
   - Verify each processes independently

2. **Test error cases:**
   - Unknown vendor (should log, not fail)
   - Malformed attachment (should handle gracefully)
   - Network timeout (retry logic should catch)

3. **Production metrics:**
   - Average processing time
   - Vendor match rate
   - Auto-routing percentage
   - Error rate

4. **Monitor for 24 hours:**
   - Watch for unexpected loop patterns
   - Check queue depths periodically
   - Review error logs
   - Validate transaction counts

---

**Document Version:** 1.0
**Last Updated:** 2024-11-17
**Status:** Ready for testing
