# Email Loop - Incident Response Guide

## 🚨 YOU DETECTED A LOOP

You're seeing multiple emails in the AP mailbox (2, 3, 4+) or emails re-appearing in the invoice inbox.

**DO NOT PANIC.** Follow this guide step-by-step.

---

## PHASE 1: STOP THE LOOP (Immediate - 2 minutes)

### Step 1: Stop the Function App (Pause All Processing)

**This is the emergency brake.** It stops MailIngest from picking up more emails.

```bash
# STOP the Function App immediately
az functionapp stop \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod

# Verify it's stopped
az functionapp show \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query state
# Output should be: "Stopped"
```

**What this does:**
- ✅ Stops MailIngest from polling inbox
- ✅ Stops processing new queue messages
- ✅ Existing messages in queues stay put (won't be processed)
- ✅ Gives you time to diagnose

**What happens to emails:**
```
BEFORE STOP:
  dev-invoices inbox: 1, 2, 3... emails (growing)
  dev-ap inbox: 1, 2, 3... emails (growing)
  Queue: Messages piling up

AFTER STOP:
  Inbox counts FREEZE
  Queue stops processing
  MailIngest timer paused (won't pick up new emails)
```

---

### Step 2: Clear the Queues (Remove Stuck Messages)

Queue messages are what causes re-processing. Delete them.

```bash
# Delete all messages from processing queues
# (Keep poison queues for later analysis)

az storage queue delete \
  --name raw-mail \
  --account-name stinvoiceagentprod

az storage queue delete \
  --name to-post \
  --account-name stinvoiceagentprod

az storage queue delete \
  --name notify \
  --account-name stinvoiceagentprod

# Verify queues are empty
echo "Verifying queues are cleared..."
CONN_STR=$(az storage account show-connection-string \
  --name stinvoiceagentprod \
  --resource-group rg-invoice-agent-prod \
  --query connectionString -o tsv)

for queue in raw-mail to-post notify; do
  count=$(az storage queue metadata show \
    --name $queue \
    --connection-string "$CONN_STR" 2>/dev/null | \
    grep -o '"approximateMessageCount": [0-9]*' | \
    grep -o '[0-9]*')
  echo "Queue '$queue': $count messages"
done
```

**What this does:**
- ✅ Removes all pending messages from queues
- ✅ Prevents any automatic re-processing
- ✅ Stops exponential growth

**Important:** Poison queues are NOT deleted (for debugging)

---

### Step 3: Verify Emails Stop Re-appearing (5 seconds)

```bash
# Quick check - emails should STOP arriving
python scripts/verify_test_emails.py

# Watch the output:
# - dev-invoices unread count should be STABLE (not growing)
# - dev-ap unread count should be STABLE (not growing)

# If counts are STILL growing, something else is wrong
# → Go to "Phase 2: Diagnose" below
```

---

## PHASE 2: DIAGNOSE THE ROOT CAUSE (5-10 minutes)

### Step 1: Check Configuration (Most Common Cause)

```bash
# Are the mailboxes different?
az functionapp config appsettings list \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "[?name=='INVOICE_MAILBOX' || name=='AP_EMAIL_ADDRESS'].{name:name, value:value}"

# Output should show:
# INVOICE_MAILBOX: dev-invoices@chelseapiers.com
# AP_EMAIL_ADDRESS: dev-ap@chelseapiers.com
#
# If they're the SAME → THIS IS YOUR PROBLEM
```

**If mailboxes are different:** Go to Step 2

**If mailboxes are the SAME or similar:**
```
❌ CONFIGURATION ERROR FOUND

The system is sending email to itself because:
  INVOICE_MAILBOX = AP_EMAIL_ADDRESS (wrong!)

Fix:
1. Update app settings with CORRECT values
2. Both must be DIFFERENT email addresses
3. Redeploy and test

az functionapp config appsettings set \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --settings INVOICE_MAILBOX="dev-invoices@chelseapiers.com" \
              AP_EMAIL_ADDRESS="dev-ap@chelseapiers.com"

# Restart function app
az functionapp restart \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod
```

---

### Step 2: Check Which Loop Prevention Layer Failed

Run this to identify the broken layer:

```bash
python scripts/analyze_test_results.py
```

**Read the output carefully:**

#### Layer 1 Failure (Sender Validation)
```
If email from INVOICE_MAILBOX appears in invoice inbox:
  ❌ Layer 1 FAILED: _should_skip_email() not working
```

#### Layer 2 Failure (Deduplication)
```
If multiple transactions with SAME OriginalMessageId:
  ❌ Layer 2 FAILED: Deduplication not working

Check:
  - Is OriginalMessageId being captured from Graph API?
  - Is OriginalMessageId being passed through pipeline?
  - Is PostToAP querying by OriginalMessageId?
```

#### Layer 3 Failure (Recipient Validation)
```
If email sent to INVOICE_MAILBOX (wrong recipient):
  ❌ Layer 3 FAILED: _validate_recipient() not working
```

#### Layer 4 Failure (Tracking/Audit)
```
If no OriginalMessageId in transaction:
  ⚠️  Layer 4 FAILED: Audit trail incomplete
  (Usually symptom of Layer 2 failure)
```

---

### Step 3: Check Application Insights Logs

```bash
# View function execution errors
az monitor app-insights component show \
  --app ai-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod

# Or via Azure Portal:
# → ai-invoice-agent-prod → Logs
# Run this query:
```

```kusto
traces
| where timestamp > ago(30m)
| where message contains "loop" or message contains "error" or message contains "already processed"
| order by timestamp desc
| project timestamp, message, customDimensions
```

**Look for:**
- `already processed` - Dedup check ran
- `sender is system mailbox` - Layer 1 caught something
- `recipient validation failed` - Layer 3 caught something
- Error messages about Graph API, table storage, etc.

---

## PHASE 3: FIX THE ROOT CAUSE (Varies by cause)

### Cause A: Configuration Error (INVOICE_MAILBOX == AP_EMAIL_ADDRESS)

**Fix:**
```bash
# Update to use DIFFERENT mailboxes
az functionapp config appsettings set \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --settings INVOICE_MAILBOX="dev-invoices@chelseapiers.com" \
              AP_EMAIL_ADDRESS="dev-ap@chelseapiers.com"

# Restart
az functionapp restart \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod

# Wait 30 seconds for restart
sleep 30

# Verify configuration took effect
az functionapp config appsettings list \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "[?name=='INVOICE_MAILBOX' || name=='AP_EMAIL_ADDRESS']"
```

---

### Cause B: Broken Deduplication (OriginalMessageId not captured)

**Symptoms:**
- Multiple transactions with same subject/sender
- OriginalMessageId is NULL or missing
- PostToAP not querying by message ID

**Fix:**
1. Verify MailIngest captures `email["id"]` from Graph API
2. Verify RawMail model includes `original_message_id` field
3. Verify ExtractEnrich passes it through to EnrichedInvoice
4. Verify PostToAP stores it in InvoiceTransaction
5. Verify PostToAP queries by OriginalMessageId

**Code to check:**
```python
# In src/functions/MailIngest/__init__.py
# Should capture Graph API message ID:
email_msg_id = email.get("id")  # ← This must be captured

# In src/functions/PostToAP/__init__.py
# Should query by message ID:
# OriginalMessageId eq '{message_id}' and Status eq 'processed'
```

**If broken, redeploy:**
```bash
# Re-deploy functions from main branch
# (Ensure you're on main with deduplication fix)
git status  # Should show "On branch main"
git log -1  # Should show f63d909 (dedup fix) or later

# Deploy
func azure functionapp publish func-invoice-agent-prod --python

# Restart
az functionapp restart \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod
```

---

### Cause C: Recipient Validation Failed

**Symptoms:**
- Email sent to wrong recipient (invoice mailbox instead of AP)
- PostToAP should have caught this

**Fix:**
```python
# In src/functions/PostToAP/__init__.py
# Verify _validate_recipient() is being called:

def _validate_recipient(recipient: str) -> bool:
    """Ensure recipient is NOT the system mailbox."""
    invoice_mailbox = os.environ.get("INVOICE_MAILBOX")
    if recipient.lower() == invoice_mailbox.lower():
        raise ValueError(f"Cannot send to system mailbox: {recipient}")
    return True
```

---

## PHASE 4: CLEAN UP MAILBOXES (Optional but Recommended)

### Clean Up Duplicate Emails

Once you've fixed the cause, clean up the extra emails:

**In Outlook:**
1. Open dev-ap mailbox
2. Select duplicate emails (keep first one only)
3. Delete
4. Empty trash

**Or via Graph API:**
```python
# WARNING: This deletes emails - be careful!
from shared.graph_client import GraphAPIClient

client = GraphAPIClient()
ap_mailbox = "dev-ap@chelseapiers.com"

# Get all emails with duplicate subject
emails = client.get_unread_emails(ap_mailbox, max_results=50)

# Manually inspect, then delete via Portal
# (Script deletion is risky - do manually)
```

---

## PHASE 5: TEST & RESTART (5 minutes)

### Step 1: Restart Function App

```bash
# Restart (should now be safe)
az functionapp start \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod

# Verify it's running
az functionapp show \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query state
# Output: "Running"
```

### Step 2: Run Safety Test Again

```bash
# Clear any remaining test data
az storage queue delete --name raw-mail --account-name stinvoiceagentprod 2>/dev/null
az storage queue delete --name to-post --account-name stinvoiceagentprod 2>/dev/null
az storage queue delete --name notify --account-name stinvoiceagentprod 2>/dev/null

# Delete duplicate transactions (optional)
# (Manually delete via Azure Portal if needed)

# Send NEW test email
# TO: dev-invoices@chelseapiers.com
# FROM: contact@adobe.com
# SUBJECT: Loop Test #2

# Wait 10 seconds

# Analyze
python scripts/analyze_test_results.py

# Should show:
# ✅ Exactly ONE email in AP mailbox
# ✅ Exactly ONE transaction
# ✅ No LOOP DETECTED
```

---

## Prevention: The 4-Layer Defense

These layers should prevent loops:

### Layer 1: Sender Validation (MailIngest)
```python
if sender == invoice_mailbox.lower():
    return True, f"sender is system mailbox ({sender})"
    # ↑ Skip the email, don't process it
```

### Layer 2: Deduplication (PostToAP)
```python
# Check if this message was already processed
existing = table.query_entities(
    filter=f"OriginalMessageId eq '{message_id}' and Status eq 'processed'"
)
if existing:
    raise AlreadyProcessedError()
    # ↑ Don't process duplicate
```

### Layer 3: Recipient Validation (PostToAP)
```python
if recipient.lower() == invoice_mailbox.lower():
    raise ValueError(f"Cannot send to system mailbox")
    # ↑ Don't send to wrong recipient
```

### Layer 4: Email Tracking (PostToAP)
```python
# Log transaction with message ID for audit trail
transaction = {
    "OriginalMessageId": message_id,  # ← Critical for dedup
    "Status": "processed",
    "CreatedAt": datetime.utcnow()
}
```

**If you hit a loop, one of these layers failed.** The incident response guide above will help you identify which one.

---

## Quick Reference: Loop Incident Response

```
🚨 DETECT LOOP
  ↓
IMMEDIATE ACTION (< 1 min):
  az functionapp stop --name func-invoice-agent-prod --resource-group rg-invoice-agent-prod

CLEAR QUEUES (< 2 min):
  az storage queue delete --name raw-mail --account-name stinvoiceagentprod
  az storage queue delete --name to-post --account-name stinvoiceagentprod
  az storage queue delete --name notify --account-name stinvoiceagentprod

VERIFY STOPPED (< 3 min):
  python scripts/verify_test_emails.py
  # Should show stable counts (not growing)

DIAGNOSE (5-10 min):
  az functionapp config appsettings list ... (check config)
  python scripts/analyze_test_results.py (check which layer failed)

FIX ROOT CAUSE (5-30 min):
  - If config wrong: Update appsettings
  - If dedup broken: Redeploy from main
  - If validation broken: Redeploy from main

RESTART & TEST (5 min):
  az functionapp start --name func-invoice-agent-prod ...
  Send new test email
  python scripts/analyze_test_results.py
  ✅ Verify safety constraints pass
```

---

## Escalation: When to Get Help

**If after Phase 2 you can't identify the cause:**

1. Check Application Insights logs (see Phase 2, Step 3)
2. Review commit f63d909 (deduplication fix)
3. Check if dedup changes were deployed
4. Verify Graph API message ID is flowing through pipeline
5. Check if there's a regression in the code

**If still stuck:**
- Review CLAUDE.md for architecture overview
- Check git log for recent changes
- Review TESTING_PLAYBOOK.md loop detection section
- Escalate to team for code review

---

**Document Version:** 1.0
**Last Updated:** 2024-11-17
**Status:** Ready for incident response
