# Email Ingestion Troubleshooting Session Summary

> **RESOLUTION (2024-11-20):** Timer trigger reliability issue resolved by migrating to Graph API webhooks. Webhook system now deployed and active in dev environment. See [WEBHOOK_SETUP_GUIDE.md](WEBHOOK_SETUP_GUIDE.md) and [ADR-021](docs/DECISIONS.md#adr-021-event-driven-webhooks-over-timer-polling) for implementation details.
>
> **This document archived for historical reference.**

---

**Date:** 2025-11-20
**Environment:** dev
**Original Status:** ✅ Configuration Fixed | ⚠️ Timer Trigger Issue Identified
**Final Resolution:** ✅ Migrated to Webhook Architecture

---

## Issues Resolved ✅

### 1. Missing Key Vault Secrets
**Problem:** Function couldn't access mailbox or Graph API  
**Solution:** Configured all 5 required secrets:
- `graph-tenant-id`
- `graph-client-id`
- `graph-client-secret`
- `invoice-mailbox`: dev-invoices@chelseapiers.com
- `ap-email-address`: dev-ap@chelseapiers.com

### 2. User Permissions
**Problem:** User couldn't set Key Vault secrets  
**Solution:** Granted `set`, `get`, `list`, `delete` permissions

### 3. Missing Extension Bundle  
**Problem:** "The binding type(s) 'queue' are not registered"  
**Solution:** Added extensionBundle to `src/host.json`:
```json
{
  "extensionBundle": {
    "id": "Microsoft.Azure.Functions.ExtensionBundle",
    "version": "[4.*, 5.0.0)"
  }
}
```

### 4. Deployment Configuration
**Problem:** CI/CD didn't deploy to dev environment  
**Solution:** Commit messages must include `[deploy-dev]` flag

---

## Remaining Issue ⚠️

### Timer Triggers on Consumption Plan

**Problem:** Timer triggers don't fire reliably on Consumption tier when app is idle  
**Root Cause:** `AlwaysOn: false` (not available on Consumption plan)  
**Impact:** MailIngest timer (every 5 minutes) won't execute when Function App sleeps

**Evidence:**
- Function App state: Running
- Last logs: 22:35 UTC (stopped logging after deployment)
- Manual GraphAPI test: ✅ Works (4 emails ready to process)
- Configuration: ✅ All correct
- Code: ✅ Deployed successfully

**Solutions:**

#### Option 1: Upgrade to Premium Plan (**Recommended**)
```bash
az functionapp plan update \
  --name asp-invoice-agent-dev \
  --resource-group rg-invoice-agent-dev \
  --sku P1V2
```
**Pros:**  
- Reliable timer triggers with AlwaysOn
- Better performance, VNet integration, always-warm instances

**Cons:**  
- Cost: ~$150-300/month (vs $0-20 on Consumption)

#### Option 2: HTTP Trigger + External Scheduler
Convert MailIngest to HTTP trigger and use:
- **Azure Logic App** (every 5 min HTTP call)
- **GitHub Actions** (cron workflow)
- **Azure Automation** (runbook schedule)

**Pros:**  
- Stays on Consumption plan (cheaper)
- Reliable scheduling from external service

**Cons:**  
- Requires code changes
- Additional service to manage

#### Option 3: Manual/On-Demand Only  
Keep as-is, trigger manually or via HTTP when needed.

---

## Verification Steps

All configuration is correct and ready. To verify end-to-end:

### Test Manually (Proves Everything Works)
```bash
# Option A: Via Azure Portal
# 1. Go to Function App → MailIngest → "Code + Test"
# 2. Click "Test/Run"
# 3. Check if 4 emails are processed

# Option B: Via Python test script
python3 check-mailbox.py  # Shows 4 unread emails waiting
```

### Monitor After Timer Solution Implemented
```bash
# Check emails processed
python3 check-mailbox.py

# Check logs
az monitor app-insights query \
  --app ai-invoice-agent-dev \
  --resource-group rg-invoice-agent-dev \
  --analytics-query "traces | where timestamp > ago(10m) and message contains 'MailIngest' | order by timestamp desc"
```

---

## Files Created This Session

1. `configure-dev-secrets.sh` - Secret configuration script
2. `check-mailbox.py` - Manual mailbox verification
3. `monitor-mailingest.sh` - Log monitoring script
4. `wait-for-deployment.sh` - Deployment monitoring
5. `SESSION_SUMMARY.md` - This file

---

## Next Steps

**Immediate:**
1. Decide on timer solution (Premium plan vs HTTP trigger)
2. If Premium: Update infrastructure
3. If HTTP: Modify MailIngest + create scheduler
4. Test end-to-end with chosen solution

**For Production:**
- Apply same fixes to production environment
- Consider Premium plan for reliability
- Document timer trigger limitation in ops guide

---

## Lessons Learned

1. **Consumption plans have timer trigger limitations** - Not suitable for reliable scheduled tasks
2. **CI/CD requires environment-specific flags** - `[deploy-dev]` vs automatic prod deployment
3. **Extension bundles are critical** - Python Functions need explicit bundle configuration
4. **Configuration gaps hard to diagnose** - Missing secrets show as generic errors
5. **Always test Graph API separately** - Validates credentials before debugging functions

---

**Status:** Ready for timer solution decision and final testing
