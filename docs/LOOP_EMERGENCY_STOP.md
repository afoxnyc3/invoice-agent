# 🚨 LOOP EMERGENCY STOP - Quick Reference

**If you detect a loop, these are the ONLY commands you need to run:**

---

## THE NUCLEAR OPTION (30 seconds)

```bash
# 1. STOP EVERYTHING IMMEDIATELY (blocking new email pickup)
az functionapp stop \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod

# 2. VERIFY IT'S STOPPED
az functionapp show \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query state
# Expected output: "Stopped"
```

**That's it. The loop stops here.**

The Function App is like a giant OFF switch for all processing:
- ✅ MailIngest timer stops running
- ✅ Queue processing pauses
- ✅ No more emails will be sent
- ✅ Inbox counts will freeze

---

## THEN: Clear the Queues (< 1 minute)

Messages stuck in queues can still cause problems. Delete them:

```bash
# Delete all pending messages
az storage queue delete --name raw-mail --account-name stinvoiceagentprod
az storage queue delete --name to-post --account-name stinvoiceagentprod
az storage queue delete --name notify --account-name stinvoiceagentprod

# Verify they're gone
python scripts/verify_test_emails.py
# Inbox counts should be STABLE now (not changing)
```

---

## THEN: Figure Out WHY (5-10 minutes)

```bash
# Check if mailboxes are different (most common cause)
az functionapp config appsettings list \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "[?name=='INVOICE_MAILBOX' || name=='AP_EMAIL_ADDRESS'].{name:name, value:value}"

# If they're the SAME: FIX IT
az functionapp config appsettings set \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --settings INVOICE_MAILBOX="dev-invoices@chelseapiers.com" \
              AP_EMAIL_ADDRESS="dev-ap@chelseapiers.com"
```

---

## FINALLY: Restart and Verify (5 minutes)

```bash
# Restart the function app
az functionapp start \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod

# Wait 30 seconds for startup
sleep 30

# Verify it's running
az functionapp show \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query state
# Expected output: "Running"

# Send a NEW test email and verify
python scripts/analyze_test_results.py
# Should show:
# ✅ Exactly ONE email (no loop)
# ✅ Exactly ONE transaction
```

---

## Visual: What Happens When You Stop

```
LOOP IN PROGRESS:
  Time  │ Dev-Invoices │ Dev-AP │ Queue Msgs
  ──────┼──────────────┼────────┼──────────
  T+0s  │ 1            │ 0      │ 1
  T+5s  │ 0            │ 1      │ 0
  T+10s │ 1            │ 1      │ 1  ← RE-APPEARS
  T+15s │ 0            │ 2      │ 0  ← DUPLICATED
  T+20s │ 1            │ 2      │ 1  ← KEEPS GROWING

YOU RUN: az functionapp stop

AFTER STOP:
  Time  │ Dev-Invoices │ Dev-AP │ Queue Msgs
  ──────┼──────────────┼────────┼──────────
  T+21s │ 1            │ 2      │ 1  ← FROZEN
  T+22s │ 1            │ 2      │ 1  ← FROZEN
  T+23s │ 1            │ 2      │ 1  ← FROZEN

YOU RUN: az storage queue delete

AFTER QUEUE CLEAR:
  Time  │ Dev-Invoices │ Dev-AP │ Queue Msgs
  ──────┼──────────────┼────────┼──────────
  T+24s │ 1            │ 2      │ 0  ← CLEARED

NOW: Restart and test with fixed configuration
```

---

## Common Causes & Quick Fixes

### Cause 1: Same Mailbox (MOST COMMON)

```bash
# You'll see this:
# INVOICE_MAILBOX: dev-invoices@chelseapiers.com
# AP_EMAIL_ADDRESS: dev-invoices@chelseapiers.com
#                   ↑ SAME ADDRESS = LOOP

# Fix it:
az functionapp config appsettings set \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --settings AP_EMAIL_ADDRESS="dev-ap@chelseapiers.com"
  # Note: Use DIFFERENT email address
```

### Cause 2: Deduplication Not Working

```bash
# You'll see multiple transactions with same subject
# And OriginalMessageId will be NULL or missing

# Check the logs:
az monitor app-insights component show \
  --app ai-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod

# If broken, redeploy from main:
# (Make sure you're on main branch with dedup fix)
git checkout main
func azure functionapp publish func-invoice-agent-prod --python

# Restart:
az functionapp restart \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod
```

### Cause 3: Recipient Validation Failed

```bash
# Email sent to invoice mailbox instead of AP
# (System should have blocked this)

# Redeploy to ensure Layer 3 validation is active:
git checkout main
func azure functionapp publish func-invoice-agent-prod --python

az functionapp restart \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod
```

---

## The 3-Minute Response

If you need to stop a loop in 3 minutes:

```bash
# Minute 1: STOP
az functionapp stop --name func-invoice-agent-prod --resource-group rg-invoice-agent-prod

# Minute 2: CLEAR QUEUES
az storage queue delete --name raw-mail --account-name stinvoiceagentprod
az storage queue delete --name to-post --account-name stinvoiceagentprod
az storage queue delete --name notify --account-name stinvoiceagentprod

# Minute 3: VERIFY STOPPED
python scripts/verify_test_emails.py
# Counts should be stable (frozen)
```

**That's it.** The loop is stopped. Now investigate in Phase 2 of the full guide.

---

## Recovery Checklist

After stopping:

- [ ] Function App is STOPPED
- [ ] Queue messages are DELETED
- [ ] Email counts are STABLE (not growing)
- [ ] You've identified the root cause
- [ ] Configuration is FIXED (or code redeployed)
- [ ] Function App is RESTARTED
- [ ] New test email processed successfully
- [ ] All 5 safety constraints PASS

---

## Safety Assertion

**Before restarting:**

```bash
# Verify mailboxes are different
az functionapp config appsettings list \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod | grep -E "INVOICE_MAILBOX|AP_EMAIL_ADDRESS"

# Output MUST show two DIFFERENT addresses:
# ✅ INVOICE_MAILBOX: dev-invoices@chelseapiers.com
# ✅ AP_EMAIL_ADDRESS: dev-ap@chelseapiers.com  (DIFFERENT)

# If not different, you'll have ANOTHER loop!
```

---

**For detailed incident response, see:** `docs/LOOP_INCIDENT_RESPONSE.md`

**For testing playbook, see:** `docs/TESTING_PLAYBOOK.md`

---

**Remember:** Stop first, diagnose second, restart third.
