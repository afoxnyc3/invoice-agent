# Diagnostic Skills - Quick Reference for LLMs

**Purpose:** This document provides a concise overview of the 5 diagnostic skills available for troubleshooting the invoice-agent Azure Functions application. Use this as a quick reference when diagnosing issues.

**Last Updated:** 2025-11-23

---

## 📚 Overview of Diagnostic Skills

The invoice-agent project includes 5 specialized diagnostic skills that automate Azure Functions troubleshooting workflows:

| Skill | Purpose | Time Saved | Use When |
|-------|---------|------------|----------|
| azure-health-check | Function App infrastructure validation | 10-15 min | Config/permission issues |
| queue-inspector | Queue message flow analysis | 5-10 min | Pipeline bottlenecks |
| appinsights-log-analyzer | Error log analysis | 15-20 min | Function failures |
| webhook-validator | Graph API webhook validation | 10-15 min | Webhook not triggering |
| pipeline-test | End-to-end flow testing | 20-30 min | System validation |

---

## 🔧 Skill #1: Azure Health Check

**File:** `.claude/skills/azure-health-check.md`

**What it checks:**
- Function App runtime status (running/stopped)
- All 7 functions deployed (MailWebhook, MailIngest, ExtractEnrich, PostToAP, Notify, AddVendor, SubscriptionManager)
- Application settings and Key Vault references
- Managed Identity RBAC permissions (Storage, Key Vault)
- Key Vault access policies
- Application Insights configuration

**When to use:**
- Function App accepting requests but not executing
- After infrastructure or code deployments
- "Undefined" errors in logs
- Permission denied errors
- Regular health monitoring

**How to invoke:**
```
Use the azure-health-check skill
```

**Common fixes it identifies:**
- Malformed Key Vault references: `@Microsoft.KeyVault(SecretUri=...)` syntax errors
- Missing Managed Identity role assignments: Storage Blob/Queue/Table Data Contributor
- Missing functions in deployment
- Function App stopped or misconfigured

**Expected output:**
```
=== AZURE FUNCTIONS HEALTH CHECK REPORT ===

RUNTIME STATUS: ✅/❌
CONFIGURATION: ✅/❌ (Key Vault refs, app settings)
PERMISSIONS: ✅/❌ (Managed Identity roles)
DEPLOYMENT: ✅/❌ (All functions present)
MONITORING: ✅/❌ (App Insights configured)

IMMEDIATE ACTIONS REQUIRED:
1. {Specific fix commands}
```

---

## 📊 Skill #2: Queue Inspector

**File:** `.claude/skills/queue-inspector.md`

**What it analyzes:**
- Message counts in all pipeline queues
- Poison queue contents (failed messages)
- Bottleneck detection (where messages are stuck)
- Message flow through: webhook-notifications → raw-mail → to-post → notify

**When to use:**
- Messages not flowing through pipeline
- Functions healthy but no processing
- Investigating delays
- Checking for failures (poison queues)

**How to invoke:**
```
Use the queue-inspector skill
```

**Queue flow (expected):**
```
Email → MailWebhook → webhook-notifications queue (webhook path)
             OR
Email → MailIngest → raw-mail queue (fallback hourly path)
             ↓
ExtractEnrich ← webhook-notifications + raw-mail
             ↓
to-post queue → PostToAP
             ↓
notify queue → Notify → Teams
```

**Common issues it detects:**
- Messages stuck in specific queue (bottleneck)
- High poison queue counts (repeated failures)
- All queues empty but emails not processed (upstream issue)
- Messages with high dequeue counts (retry loop)

**Expected output:**
```
=== QUEUE INSPECTOR REPORT ===

QUEUE DEPTHS:
  webhook-notifications: X messages
  raw-mail: X messages
  to-post: X messages
  notify: X messages

POISON QUEUES:
  ✅ All empty / ⚠️ X failed messages

PIPELINE HEALTH:
  ✅ Flowing / ⚠️ Bottleneck at {queue_name}

IMMEDIATE ACTIONS:
1. {Fix for bottleneck}
```

---

## 🔍 Skill #3: Application Insights Log Analyzer

**File:** `.claude/skills/appinsights-log-analyzer.md`

**What it analyzes:**
- Exceptions and error-level logs (last 1h default)
- Function invocation statistics (success rates)
- Transaction traces by correlation ID (ULID)
- Performance metrics (timeout risks)
- External dependency failures (Graph API, Storage, Teams)

**When to use:**
- Functions failing but errors unclear
- Tracing specific transaction flow
- Performance analysis (slow functions)
- Dependency failure investigation
- Understanding error patterns

**How to invoke:**
```
Use the appinsights-log-analyzer skill

# Can specify:
# - Time range: 1h, 6h, 24h, 7d
# - Function name filter
# - Transaction ID to trace
```

**Key queries it runs:**
- `exceptions | where timestamp > ago(1h)` - Recent exceptions
- `traces | where severityLevel >= 3` - Error-level logs
- `requests | summarize by operation_Name` - Function success rates
- `dependencies | where success == false` - External call failures

**Common issues it detects:**
- Key Vault access denied (Managed Identity permission)
- Storage account access failures (RBAC)
- Table Storage EntityNotFound (VendorMaster not seeded)
- Graph API authentication failures
- Function timeout approaching (>5s duration)

**Expected output:**
```
=== APPLICATION INSIGHTS LOG ANALYSIS ===

EXCEPTION SUMMARY:
  Total: X exceptions
  Most Common: {error_type}

FUNCTION HEALTH:
  MailIngest:      ✅ XX% success (Y invocations)
  ExtractEnrich:   ⚠️ XX% success (Y invocations)
  ...

DEPENDENCY FAILURES:
  Graph API: X failures
  Storage: X failures

TOP ISSUES:
  1. {Most frequent error with count}
  2. {Second error}

RECOMMENDED ACTIONS:
  1. {Fix command}
```

---

## 🌐 Skill #4: Graph API Webhook Validator

**File:** `.claude/skills/webhook-validator.md`

**What it validates:**
- Active subscription in GraphSubscriptions table
- Subscription expiration (warns if <48 hours)
- Environment variables (GRAPH_TENANT_ID, GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET, MAIL_WEBHOOK_URL, GRAPH_CLIENT_STATE, INVOICE_MAILBOX)
- Webhook endpoint accessibility (validation handshake + POST test)
- Client state secret (≥32 chars, matches subscription)
- Graph API authentication (token acquisition test)
- SubscriptionManager function deployment

**When to use:**
- Webhooks not triggering for new emails
- After webhook configuration changes
- Subscription expired or about to expire
- Authentication/permission issues
- Regular webhook health monitoring

**How to invoke:**
```
Use the webhook-validator skill
```

**Webhook validation flow:**
1. Check GraphSubscriptions table for active subscription
2. Validate environment variables format
3. Test webhook endpoint:
   - GET with `?validationToken=test` (must echo token)
   - POST with simulated notification (must return 202)
4. Test Graph API authentication (acquire token)
5. Check client state secret length and storage

**Common issues it detects:**
- Subscription expired or missing
- Webhook URL malformed (missing HTTPS or function key)
- Client state mismatch or too short (<32 chars)
- Graph API authentication failures
- SubscriptionManager not deployed (no auto-renewal)

**Expected output:**
```
=== GRAPH API WEBHOOK VALIDATOR REPORT ===

SUBSCRIPTION STATUS:
  ✅/❌ Active subscription: X found
  ✅/⚠️ Expiration: X hours remaining

WEBHOOK ENDPOINT:
  ✅/❌ HTTPS protocol
  ✅/❌ Validation handshake
  ✅/❌ Notification POST (202)

GRAPH API AUTHENTICATION:
  ✅/❌ Token acquisition
  ✅/❌ Mailbox accessible

OVERALL STATUS: ✅ HEALTHY / ❌ CRITICAL

IMMEDIATE ACTIONS:
1. {Fix command to renew subscription}
```

---

## 🧪 Skill #5: End-to-End Pipeline Test

**File:** `.claude/skills/pipeline-test.md`

**What it tests:**
- Injects synthetic test message
- Tracks flow through all queues (webhook-notifications/raw-mail → to-post → notify)
- Verifies transaction record created in InvoiceTransactions table
- Checks blob uploaded to storage
- Measures end-to-end latency (<60s SLA target)
- Validates no poison queue failures

**When to use:**
- After deploying code or infrastructure changes
- Validating complete system health
- Performance regression testing
- Verifying SLA compliance (<60s)
- Troubleshooting end-to-end flow issues

**How to invoke:**
```
Use the pipeline-test skill

# Recommended settings:
# - env: dev (safer for testing)
# - entry_point: raw-mail (simpler, skips Graph API)
# - timeout: 120 (allows retries)
```

**Test flow:**
1. Generate unique test transaction ID (TEST-{timestamp}-{random})
2. Create test message payload
3. Inject into entry queue (webhook-notifications or raw-mail)
4. Poll queues for 120 seconds to track flow
5. Verify transaction record in InvoiceTransactions table
6. Check for poison queue failures
7. Query Application Insights for logs
8. Calculate total latency
9. Offer cleanup of test data

**Success criteria:**
- Message processed through all queues
- Transaction record created (Status: "unknown" expected)
- No poison queue messages
- Total latency <60 seconds
- No exceptions in logs

**Expected output:**
```
=== END-TO-END PIPELINE TEST REPORT ===
Transaction ID: TEST-1732394821-A3F2

QUEUE FLOW:
  raw-mail: ✅ Processed (Xs)
  to-post: ✅ Processed (Xs)
  notify: ✅ Processed (Xs)

TRANSACTION RECORD:
  ✅ Created (Status: unknown)

PERFORMANCE:
  Total Duration: Xs
  SLA Target: <60s
  Status: ✅ Within SLA

OVERALL RESULT: ✅ PASS / ❌ FAIL

ISSUES FOUND: {list if any}
```

---

## 🎯 Recommended Diagnostic Workflow

When troubleshooting Function App issues, use skills in this order:

### **Step 1: Health Check**
```
Use azure-health-check skill
```
**Purpose:** Validate infrastructure, configuration, permissions.

**Decision:**
- ✅ All healthy → Proceed to Step 2
- ❌ Critical issues → Fix before proceeding (stopped app, missing permissions, malformed config)

---

### **Step 2: Queue Inspector**
```
Use queue-inspector skill
```
**Purpose:** Determine if messages are flowing or stuck.

**Decision:**
- 📭 All queues empty → Check if messages being created (Step 4: webhook-validator)
- ⚠️ Bottleneck detected → Proceed to Step 3 for error logs
- ✅ Flowing normally → Proceed to Step 5 for end-to-end test

---

### **Step 3: Log Analysis**
```
Use appinsights-log-analyzer skill
```
**Purpose:** Get detailed error messages and root cause.

**Decision:** Use logs to:
- Fix code bugs
- Adjust configuration
- Seed missing data (VendorMaster)
- Update permissions

---

### **Step 4: Webhook Validator** (if emails not arriving)
```
Use webhook-validator skill
```
**Purpose:** Ensure webhooks are configured and active.

**Decision:**
- ❌ Subscription expired → Run SubscriptionManager function
- ❌ Webhook endpoint failing → Fix URL or function key
- ✅ Webhook healthy → Check Graph API mailbox or permissions

---

### **Step 5: Pipeline Test** (validation/regression testing)
```
Use pipeline-test skill
```
**Purpose:** Validate complete system with synthetic test.

**Decision:**
- ✅ Test passes <60s → System healthy
- ⚠️ Test slow >60s → Investigate performance (Step 3)
- ❌ Test fails → Check poison queues and logs (Step 2 & 3)

---

## 💡 Common Troubleshooting Scenarios

### **Scenario 1: No emails being processed**
**Path:** Health Check → Webhook Validator → Queue Inspector → Log Analyzer

**Skills to use:**
1. `azure-health-check` - Verify Function App running
2. `webhook-validator` - Check subscription active and webhook accessible
3. `queue-inspector` - Confirm messages arriving in queues
4. `appinsights-log-analyzer` - Check for errors

---

### **Scenario 2: Messages stuck in specific queue**
**Path:** Queue Inspector → Log Analyzer → Health Check

**Skills to use:**
1. `queue-inspector` - Identify bottleneck queue
2. `appinsights-log-analyzer` - Find function errors for that queue's processor
3. `azure-health-check` - Verify function deployed and permissions correct

---

### **Scenario 3: After deployment validation**
**Path:** Health Check → Pipeline Test

**Skills to use:**
1. `azure-health-check` - Verify deployment successful
2. `pipeline-test` - Run end-to-end synthetic test

---

### **Scenario 4: Performance degradation**
**Path:** Pipeline Test → Log Analyzer → Queue Inspector

**Skills to use:**
1. `pipeline-test` - Measure current latency
2. `appinsights-log-analyzer` - Check for slow functions or dependency timeouts
3. `queue-inspector` - Check for queue backlogs

---

### **Scenario 5: Webhooks stopped working suddenly**
**Path:** Webhook Validator → Log Analyzer

**Skills to use:**
1. `webhook-validator` - Check subscription expiration and endpoint
2. `appinsights-log-analyzer` - Look for webhook authentication errors

---

## 🚀 Quick Command Reference

```bash
# Development Skills (already documented elsewhere)
/skill:quality-check --mode pre-commit
/skill:azure-config --action verify-settings --env prod
/skill:azure-function --name NewFunc --trigger queue --input-queue data

# Diagnostic Skills (use via natural language)
"Use the azure-health-check skill"
"Use the queue-inspector skill"
"Use the appinsights-log-analyzer skill"
"Use the webhook-validator skill"
"Use the pipeline-test skill"
```

---

## 📝 Key Technical Details

### **Architecture:**
- Azure Function App with 7 functions
- Microsoft Graph API integration (webhooks + polling fallback)
- Azure Storage queues for message processing
- Azure Table Storage for vendor lookup and transaction log
- Azure Blob Storage for email attachments
- Application Insights for monitoring

### **Pipeline Flow:**
```
Email Arrives
    ↓
MailWebhook (HTTP) → webhook-notifications queue [PRIMARY: <10s]
    OR
MailIngest (Timer, hourly) → raw-mail queue [FALLBACK]
    ↓
ExtractEnrich (Queue) ← webhook-notifications + raw-mail
    ↓
to-post queue
    ↓
PostToAP (Queue)
    ↓
notify queue
    ↓
Notify (Queue) → Teams Webhook
```

### **Critical Tables:**
- `VendorMaster` - Vendor lookup (PartitionKey: "Vendor", RowKey: normalized vendor name)
- `InvoiceTransactions` - Audit trail (PartitionKey: YYYYMM, RowKey: ULID)
- `GraphSubscriptions` - Webhook state (PartitionKey: "GraphSubscription", RowKey: subscription_id)

### **Queue Names:**
- `webhook-notifications` - Graph API notifications (webhook path)
- `raw-mail` - Email metadata + blob URL (both paths converge)
- `to-post` - Enriched vendor data
- `notify` - Notification messages
- `*-poison` - Failed messages after 5 retries

### **SLA Targets:**
- End-to-end processing: <60 seconds
- Webhook response: <3 seconds
- Queue processing: <10 seconds per stage

---

## 🎓 Tips for LLMs Using These Skills

1. **Always start with azure-health-check** when user reports general issues
2. **Use queue-inspector early** to understand message flow state
3. **Invoke skills via natural language** - Say "Use the X skill" not bash commands
4. **Reference skill files** in `.claude/skills/*.md` for detailed instructions
5. **Follow recommended workflow** (Health → Queue → Logs → Webhook → Pipeline)
6. **Skills output structured reports** - Parse and summarize for user
7. **Provide remediation commands** from skill output
8. **Chain skills when needed** - Health check might reveal need for webhook validation

---

## 📚 Additional Resources

- **Full Skills Guide:** `docs/SKILLS_GUIDE.md`
- **Architecture:** `docs/ARCHITECTURE.md`
- **Deployment Guide:** `docs/DEPLOYMENT_GUIDE.md`
- **Troubleshooting:** `docs/operations/TROUBLESHOOTING_GUIDE.md`

---

**Version:** 1.0
**Last Updated:** 2025-11-23
**Maintained By:** Engineering Team

**For LLM Use:**
This document is optimized for LLM consumption. Skills are invoked through natural language - simply state "Use the {skill-name} skill" and Claude Code will execute the appropriate diagnostic workflow.
