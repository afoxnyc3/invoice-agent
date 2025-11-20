# Incident Response Guide

This document provides procedures for responding to incidents in the Invoice Agent system.

> **For deployment troubleshooting, see [TROUBLESHOOTING_GUIDE.md](TROUBLESHOOTING_GUIDE.md)**
> **For disaster recovery, see [DISASTER_RECOVERY.md](DISASTER_RECOVERY.md)**

---

## Table of Contents

1. [Incident Classification](#incident-classification)
2. [General Response Procedures](#general-response-procedures)
3. [Specific Incident Types](#specific-incident-types)
4. [Historical Incidents](#historical-incidents)
5. [Post-Incident Review](#post-incident-review)

---

## Incident Classification

### Severity Levels

| Severity | Impact | Response Time | Examples |
|----------|--------|---------------|----------|
| **P0 - Critical** | System down, data loss | Immediate (5 min) | Email loops, data corruption, total failure |
| **P1 - High** | Major functionality impaired | <30 minutes | Graph API failures, storage down, high error rate |
| **P2 - Medium** | Partial functionality impaired | <2 hours | Unknown vendor rate spike, Teams webhook down |
| **P3 - Low** | Minor issues, workarounds exist | <1 day | Performance degradation, monitoring gaps |

### Escalation Matrix

| Role | Contact | Escalate If |
|------|---------|-------------|
| On-Call Engineer | Primary responder | P0-P1 incidents |
| Engineering Lead | Secondary | Cannot resolve in 30 min |
| IT Operations | Support | Azure infrastructure issues |
| Management | Notification only | P0 incidents |

---

## General Response Procedures

### Phase 1: Detect & Assess (5 minutes)

**Immediate Actions**:
1. **Confirm incident is real** (not false alert)
2. **Classify severity** (P0-P3)
3. **Identify affected components**
4. **Estimate blast radius**

**Key Questions**:
- Is the system processing invoices?
- Are any queues backing up?
- Are error rates elevated?
- Is data being lost or corrupted?

**Tools**:
```bash
# Check function app status
az functionapp show \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query state

# Check queue depths
az storage queue list \
  --account-name stinvoiceagentprod \
  --query "[].{name:name, approxCount:approximateMessagesCount}"

# Check error rates (Application Insights)
# Portal: ai-invoice-agent-prod → Failures
```

### Phase 2: Contain (2-10 minutes)

**Goal**: Stop the bleeding, prevent further damage

**Actions by Severity**:

**P0 (Critical) - Immediate Stop**:
```bash
# STOP the Function App to prevent further damage
az functionapp stop \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod

# Verify stopped
az functionapp show \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query state
# Expected: "Stopped"
```

**P1 (High) - Isolate Component**:
- Identify failing function
- Clear affected queue if needed
- Monitor for cascading failures

**P2-P3 (Medium/Low) - Monitor**:
- Increase monitoring frequency
- Prepare fix, deploy during maintenance window

### Phase 3: Diagnose (5-30 minutes)

**Diagnostic Steps**:

1. **Check Recent Changes**:
```bash
# Recent deployments
az functionapp deployment list \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "[0:3].{time:end_time, status:status, id:id}"

# Recent commits
git log -5 --oneline
```

2. **Check Application Insights**:
```bash
# Portal query:
# ai-invoice-agent-prod → Logs → Run KQL query
```

```kusto
traces
| where timestamp > ago(1h)
| where severityLevel >= 3  // Warning or higher
| order by timestamp desc
| project timestamp, message, severityLevel, customDimensions
| take 100
```

3. **Check Configuration**:
```bash
# App settings
az functionapp config appsettings list \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "[].{name:name, value:value}" -o table

# Check for misconfigurations
```

4. **Check Azure Service Health**:
```bash
# Check for Azure outages
az rest --method get \
  --uri "https://management.azure.com/subscriptions/{subscription-id}/providers/Microsoft.ResourceHealth/availabilityStatuses?api-version=2018-07-01"

# Or via Portal: Service Health → Resource health
```

### Phase 4: Fix (Varies by cause)

**Common Fixes**:

**Configuration Error**:
```bash
# Update app settings
az functionapp config appsettings set \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --settings KEY="VALUE"

# Restart to apply
az functionapp restart \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod
```

**Code Bug** (requires deployment):
```bash
# Deploy fix from main
git checkout main
git pull
func azure functionapp publish func-invoice-agent-prod --python

# Restart
az functionapp restart \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod
```

**Queue Backup** (clear and reprocess):
```bash
# Option 1: Let it drain naturally (if system is healthy)
# Monitor queue depth until clear

# Option 2: Clear queue (if messages are corrupted)
az storage queue clear \
  --name QUEUE_NAME \
  --account-name stinvoiceagentprod

# Check poison queue for failed messages
az storage queue list \
  --account-name stinvoiceagentprod \
  --query "[?contains(name, 'poison')]"
```

**External Service Failure** (Graph API, Storage):
```bash
# Wait for service recovery
# Monitor Azure status dashboard
# Implement retry logic if not present
```

### Phase 5: Verify (5-10 minutes)

**Verification Steps**:

1. **Restart System**:
```bash
az functionapp start \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod

# Wait 30 seconds for startup
sleep 30
```

2. **Test with Known-Good Invoice**:
```bash
# Send test email to invoice mailbox
# FROM: known-vendor@example.com
# TO: INVOICE_MAILBOX
# SUBJECT: Test Invoice - Incident Recovery

# Monitor processing
# Expected timeline: <60 seconds end-to-end
```

3. **Check All Metrics**:
```bash
# Queue depths should be draining
az storage queue list --account-name stinvoiceagentprod

# Error rates should be normal
# Portal: ai-invoice-agent-prod → Metrics → Failures

# Functions should be executing
# Portal: func-invoice-agent-prod → Functions → Monitor
```

4. **Verify End-to-End**:
```bash
# Check that test invoice reached AP mailbox
# Check transaction logged in InvoiceTransactions table
# Check Teams notification sent

# All should complete within 60 seconds
```

### Phase 6: Document (15-30 minutes)

**Create Incident Report**:
```markdown
# Incident Report: [Title]

**Date**: YYYY-MM-DD HH:MM UTC
**Severity**: P0/P1/P2/P3
**Duration**: X minutes
**Affected Users**: Finance team / AP team
**Data Loss**: None / Describe

## Timeline

- **HH:MM** - Incident detected (how/who)
- **HH:MM** - Containment actions taken
- **HH:MM** - Root cause identified
- **HH:MM** - Fix deployed
- **HH:MM** - System verified recovered
- **HH:MM** - Incident closed

## Root Cause

[Describe what caused the incident]

## Impact

- Invoices affected: X
- Processing delay: X minutes
- Emails sent/lost: X
- Data corruption: None/Describe

## Resolution

[Describe how incident was resolved]

## Prevention

[What can we do to prevent this in the future?]

## Action Items

- [ ] Deploy monitoring improvement (Owner, Due date)
- [ ] Update runbook (Owner, Due date)
- [ ] Add tests for this scenario (Owner, Due date)
```

---

## Specific Incident Types

### 1. Email Loop Incident

**Symptoms**:
- Multiple emails appearing in AP mailbox
- Emails re-appearing in invoice mailbox
- Exponential queue growth
- Transaction duplicates

**Emergency Response** (< 3 minutes):
```bash
# 1. STOP IMMEDIATELY
az functionapp stop \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod

# 2. CLEAR QUEUES
az storage queue delete --name raw-mail --account-name stinvoiceagentprod
az storage queue delete --name to-post --account-name stinvoiceagentprod
az storage queue delete --name notify --account-name stinvoiceagentprod

# 3. VERIFY COUNTS STABILIZE
# Email counts should freeze (not growing)
```

**Root Cause Investigation**:
```bash
# Check if mailboxes are misconfigured (most common)
az functionapp config appsettings list \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "[?name=='INVOICE_MAILBOX' || name=='AP_EMAIL_ADDRESS']"

# MUST show two DIFFERENT addresses:
# ✅ INVOICE_MAILBOX: invoices@example.com
# ✅ AP_EMAIL_ADDRESS: ap@example.com (DIFFERENT)
```

**Fix**:
```bash
# If mailboxes are same, update configuration
az functionapp config appsettings set \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --settings INVOICE_MAILBOX="invoices@example.com" \
              AP_EMAIL_ADDRESS="ap@example.com"

# Restart and verify
az functionapp restart \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod
```

**Prevention Layers**:
1. **Sender Validation** (MailIngest): Skip emails from system
2. **Deduplication** (PostToAP): Check OriginalMessageId
3. **Recipient Validation** (PostToAP): Block sending to invoice mailbox
4. **Transaction Tracking**: Log OriginalMessageId for audit

See [Historical Incidents - Email Loop](#email-loop-nov-2024) for detailed case study.

### 2. Graph API Failures

**Symptoms**:
- MailIngest or PostToAP failing
- 401/403/429/500 errors in logs
- Emails not being read or sent

**Diagnosis**:
```bash
# Check recent Graph API errors
# Portal: ai-invoice-agent-prod → Logs
```

```kusto
traces
| where timestamp > ago(30m)
| where message contains "Graph" or message contains "MSAL"
| where severityLevel >= 3
| order by timestamp desc
```

**Common Causes**:

**401 Unauthorized** - Token expired:
```bash
# Verify service principal exists
az ad sp show --id {CLIENT_ID}

# Verify Key Vault secret
az keyvault secret show \
  --vault-name kv-invoice-agent-prod \
  --name graph-client-secret \
  --query value -o tsv
```

**403 Forbidden** - Permissions issue:
```bash
# Check Graph API permissions
# Portal: Azure AD → App registrations → invoice-agent
# → API permissions

# Required:
# - Mail.Read (Application)
# - Mail.Send (Application)
# - Admin consent granted
```

**429 Too Many Requests** - Throttling:
```bash
# Verify retry logic honors Retry-After headers
# Check logs for backoff behavior

# If excessive, reduce polling frequency:
# Update MailIngest timer from 5min to 10min (temporary)
```

**500 Server Error** - Microsoft service issue:
```bash
# Check Microsoft 365 service health
# https://status.office365.com/

# Wait for recovery, retry logic should handle
```

### 3. Storage Failures

**Symptoms**:
- Table Storage queries failing
- Blob uploads/downloads failing
- Queue operations failing

**Diagnosis**:
```bash
# Check storage account health
az storage account show \
  --name stinvoiceagentprod \
  --resource-group rg-invoice-agent-prod \
  --query "{status:statusOfPrimary, location:location}"

# Check storage metrics
# Portal: stinvoiceagentprod → Insights → Failures
```

**Common Causes**:

**Connection Failures**:
```bash
# Verify Managed Identity has permissions
az role assignment list \
  --assignee {FUNCTION_APP_PRINCIPAL_ID} \
  --scope /subscriptions/{SUB}/resourceGroups/{RG}/providers/Microsoft.Storage/storageAccounts/{STORAGE}
```

**Quota/Throttling**:
```bash
# Check storage account limits
# Portal: stinvoiceagentprod → Metrics → Transactions

# If throttled:
# - Reduce batch sizes
# - Add exponential backoff
# - Consider upgrading SKU (LRS → GRS)
```

### 4. High Error Rate

**Symptoms**:
- >5% function failures
- Alert triggered
- Unknown vendor rate spike

**Diagnosis**:
```bash
# Get error breakdown
# Portal: ai-invoice-agent-prod → Failures → Top 10 exceptions

# Common errors:
# - UnknownVendorError (business error - acceptable)
# - ValidationError (data quality issue)
# - TimeoutError (performance issue)
```

**Response by Error Type**:

**UnknownVendorError** (>10% of invoices):
```bash
# Expected in normal operation
# If spike: Check for new vendor campaign
# Action: Add vendors to VendorMaster table

# Portal: Add vendor via AddVendor HTTP function
# Or: Update vendors.csv and re-seed
```

**ValidationError** (Pydantic errors):
```bash
# Data quality issue
# Check if email format changed
# Update data models if needed
# May require code fix
```

**TimeoutError** (>5 minute execution):
```bash
# Performance issue
# Check queue depths
# Check storage latency
# May need to optimize queries or add batching
```

### 5. Queue Backup

**Symptoms**:
- Queue depth >50 messages
- Processing lag >15 minutes
- Alert triggered

**Diagnosis**:
```bash
# Check all queue depths
az storage queue list \
  --account-name stinvoiceagentprod \
  --query "[].{name:name, count:approximateMessagesCount}" -o table

# Check function scaling
az monitor metrics list \
  --resource func-invoice-agent-prod \
  --metric FunctionExecutionCount \
  --interval PT1M
```

**Causes & Fixes**:

**Too Many Invoices** (legitimate load):
```bash
# System is auto-scaling
# Monitor: Should drain within 15-30 minutes
# No action needed unless sustained
```

**Function Failures** (processing errors):
```bash
# Check poison queues
az storage queue list \
  --account-name stinvoiceagentprod \
  --query "[?contains(name, 'poison')]"

# Inspect poison messages
# Fix underlying error
# Re-submit good messages
```

**External Dependency Slow** (Graph API, Storage):
```bash
# Check dependency health
# Add circuit breaker if needed
# Temporarily increase timeout if transient
```

---

## Historical Incidents

### Email Loop (Nov 2024)

**Date**: 2024-11-16
**Severity**: P0 (Critical - Discovered before production impact)
**Status**: Resolved

**Background**:
During pre-production testing, analysis revealed critical email loop vulnerabilities with no safeguards. The system was configured to send emails TO the same mailbox it reads FROM, creating potential for infinite loops.

**Root Cause**:
Infrastructure misconfiguration where both `INVOICE_MAILBOX` and `AP_EMAIL_ADDRESS` pointed to the same Key Vault secret, causing the system to send processed invoices back to the same mailbox it monitors.

**Resolution**:
1. Four-layer defense implemented:
   - Layer 1: Sender validation in MailIngest
   - Layer 2: Deduplication by OriginalMessageId in PostToAP
   - Layer 3: Recipient validation in PostToAP
   - Layer 4: Transaction tracking for audit trail

2. Configuration corrected to use separate mailboxes

3. Comprehensive testing playbook created

**Prevention**:
- Separate mailboxes for ingestion vs. routing
- Multi-layer validation prevents single point of failure
- Deduplication using Graph API message IDs
- Emergency stop procedure documented

**Artifacts**:
- Prevention analysis: Previously at `docs/EMAIL_LOOP_PREVENTION.md` (consolidated here)
- Incident response: Previously at `docs/LOOP_INCIDENT_RESPONSE.md` (consolidated here)
- Emergency stop: Previously at `docs/LOOP_EMERGENCY_STOP.md` (consolidated here)
- Code fix: Commit f63d909

**Key Learnings**:
1. Infrastructure as Code should validate mailboxes are different
2. Defense in depth prevents catastrophic failure
3. Testing should include negative scenarios (loop detection)
4. Emergency stop procedures are critical for P0 incidents

---

## Post-Incident Review

### Review Meeting (Within 48 hours)

**Attendees**:
- Incident responders
- Engineering team
- Stakeholders (if P0/P1)

**Agenda**:
1. **Timeline Review** (10 min)
   - What happened and when?
   - How was it detected?
   - How long to contain/resolve?

2. **Root Cause Analysis** (20 min)
   - What was the underlying cause?
   - Why did it happen?
   - What was missed in testing/review?

3. **Response Effectiveness** (10 min)
   - What went well?
   - What could be improved?
   - Were runbooks helpful?

4. **Prevention** (20 min)
   - How can we prevent this?
   - What monitoring/alerts needed?
   - What code/process changes?

5. **Action Items** (10 min)
   - Assign owners and due dates
   - Prioritize by impact
   - Track to completion

### Incident Report Template

Create report in `docs/incidents/YYYY-MM-DD-incident-name.md`:

```markdown
# Incident Report: [Title]

**Date**: YYYY-MM-DD
**Severity**: P0/P1/P2/P3
**Duration**: X hours
**Responders**: Names
**Status**: Resolved/In Progress

## Summary

Brief description of what happened.

## Impact

- **Users Affected**: X users
- **Invoices Affected**: X invoices
- **Duration**: X minutes of downtime
- **Data Loss**: None/Describe
- **Financial Impact**: $X estimated

## Timeline

| Time (UTC) | Event | Action Taken |
|------------|-------|--------------|
| 14:00 | Alert triggered | Engineer notified |
| 14:05 | Incident confirmed | Function app stopped |
| 14:10 | Root cause identified | Configuration fix deployed |
| 14:20 | Fix verified | System restarted |
| 14:30 | Incident closed | Monitoring continued |

## Root Cause

### What Happened

Detailed explanation of the root cause.

### Why It Happened

Contributing factors:
1. Factor 1
2. Factor 2

### Why It Wasn't Caught Earlier

Testing gaps, monitoring gaps, etc.

## Resolution

### Immediate Fix

What was done to resolve immediately.

### Permanent Fix

What was done to prevent recurrence.

## Lessons Learned

### What Went Well

- Good detection
- Fast response
- Effective communication

### What Could Be Improved

- Better monitoring
- More comprehensive testing
- Clearer runbooks

## Action Items

| Action | Owner | Due Date | Status |
|--------|-------|----------|--------|
| Add monitoring for X | Engineer | YYYY-MM-DD | Open |
| Update runbook | Engineer | YYYY-MM-DD | Open |
| Add integration test | Engineer | YYYY-MM-DD | Open |

## Related Documents

- [Runbook](OPERATIONS_PLAYBOOK.md)
- [Architecture](../ARCHITECTURE.md)
```

---

## Quick Reference: Emergency Commands

```bash
# STOP EVERYTHING (P0 incidents)
az functionapp stop --name func-invoice-agent-prod --resource-group rg-invoice-agent-prod

# CHECK STATUS
az functionapp show --name func-invoice-agent-prod --resource-group rg-invoice-agent-prod --query state

# CLEAR QUEUES (after stop)
az storage queue delete --name raw-mail --account-name stinvoiceagentprod
az storage queue delete --name to-post --account-name stinvoiceagentprod
az storage queue delete --name notify --account-name stinvoiceagentprod

# CHECK CONFIGURATION
az functionapp config appsettings list --name func-invoice-agent-prod --resource-group rg-invoice-agent-prod

# UPDATE CONFIGURATION
az functionapp config appsettings set --name func-invoice-agent-prod --resource-group rg-invoice-agent-prod --settings KEY="VALUE"

# RESTART
az functionapp restart --name func-invoice-agent-prod --resource-group rg-invoice-agent-prod

# CHECK LOGS
# Portal: ai-invoice-agent-prod → Logs → Run KQL query

# CHECK RECENT DEPLOYMENTS
az functionapp deployment list --name func-invoice-agent-prod --resource-group rg-invoice-agent-prod --query "[0:3]"
```

---

## Contacts & Escalation

### On-Call Rotation

| Week | Primary | Secondary |
|------|---------|-----------|
| Current | TBD | TBD |

### Escalation Path

1. **On-Call Engineer** (Primary responder)
2. **Engineering Lead** (If unresolved in 30 min)
3. **IT Operations** (Azure infrastructure issues)
4. **Management** (P0 incidents, communication)

### Key Resources

- **Azure Portal**: https://portal.azure.com
- **Application Insights**: ai-invoice-agent-prod
- **Function App**: func-invoice-agent-prod
- **Storage Account**: stinvoiceagentprod
- **Teams Channel**: #invoice-automation

---

**Version:** 1.0 (Consolidated from multiple incident docs)
**Last Updated:** 2025-11-20
**Maintained By:** Engineering Team
**Related Documents**:
- [Operations Playbook](OPERATIONS_PLAYBOOK.md)
- [Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md)
- [Disaster Recovery](DISASTER_RECOVERY.md)
- [Architecture](../ARCHITECTURE.md)
