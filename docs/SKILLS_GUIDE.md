# Claude Code Skills Guide

Complete guide to using Claude Code skills in the Invoice Agent project.

## 📚 What Are Skills?

Skills are **reusable prompt templates** stored as markdown files that Claude Code reads and executes. Think of them as macros or scripts that automate common development tasks with consistent quality.

**Key Benefits:**
- **Consistency:** Same patterns applied every time
- **Speed:** Complex tasks automated in seconds
- **Quality:** Built-in best practices and standards
- **Learning:** Documents how to perform tasks

## 📂 Skill Location

Skills are stored in `.claude/skills/` as markdown files:

```
.claude/
└── skills/
    ├── quality-check.md      # Run quality gates
    ├── azure-config.md        # Manage Azure secrets/settings
    └── azure-function.md      # Generate new Azure Functions
```

## 🎯 How to Use Skills

### Basic Syntax

```
/skill:skill-name --parameter value --flag
```

**Examples:**
```
/skill:quality-check --mode pre-commit
/skill:azure-config --action add-secret --name api-key --env dev
/skill:azure-function --name ProcessRefund --trigger queue --input-queue refunds
```

### Parameters

Skills accept parameters to customize their behavior:
- **Required parameters:** Must be provided
- **Optional parameters:** Have defaults or prompts
- **Flags:** Boolean options like `--fix` or `--dry-run`

---

## 🛠️ Available Skills

## Development Skills

These skills assist with code generation, quality checks, and configuration management.

### 1. Quality Check Skill

**Purpose:** Run comprehensive quality gates before commits or deployments.

**File:** `.claude/skills/quality-check.md`

**What It Does:**
- Runs pytest with coverage requirements (≥60%)
- Checks code formatting (Black)
- Runs linting (Flake8)
- Performs type checking (mypy strict mode)
- Scans for security issues (bandit)
- Validates function line counts (≤25 lines)

**Parameters:**
- `--mode`: Quality check level
  - `pre-commit` (default): Fast checks before committing
  - `pre-pr`: Full checks before creating PR
  - `pre-deploy`: Comprehensive checks before deployment
- `--fix`: Auto-fix formatting issues

**When to Use:**
- ✅ Before every commit
- ✅ Before creating a pull request
- ✅ Before deploying to staging/production
- ✅ After making code changes
- ✅ When troubleshooting CI/CD failures

**Examples:**

```bash
# Quick check before committing
/skill:quality-check --mode pre-commit

# Auto-fix formatting issues
/skill:quality-check --mode pre-commit --fix

# Full check before creating PR
/skill:quality-check --mode pre-pr

# Comprehensive check before deployment
/skill:quality-check --mode pre-deploy
```

**Expected Output:**
```
🔍 Quality Check Results (mode: pre-commit)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Tests:        98/98 passing (96% coverage)
✅ Formatting:   All files formatted correctly
✅ Linting:      No issues found
✅ Type Check:   All type annotations valid
✅ Security:     No vulnerabilities detected
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Overall: ✅ PASSED - Ready to commit!
```

**Common Issues:**
- **Coverage fails:** Add tests to increase coverage above 60%
- **Formatting fails:** Run with `--fix` flag to auto-format
- **Type errors:** Add missing type hints or fix type mismatches
- **Long functions:** Extract helper functions to keep ≤25 lines

---

### 2. Azure Configuration Skill

**Purpose:** Manage Azure Key Vault secrets and Function App settings across environments.

**File:** `.claude/skills/azure-config.md`

**What It Does:**
- Generates secure random secrets
- Adds/updates Key Vault secrets
- Configures Function App to reference Key Vault
- Syncs staging slot settings from production
- Verifies settings are accessible
- Restarts Function Apps to load changes

**Actions:**
- `add-secret`: Add or update a Key Vault secret
- `sync-staging`: Sync production settings to staging slot
- `generate-secret`: Generate cryptographically secure secret
- `verify-settings`: Check for undefined or missing settings
- `restart`: Restart Function App to load new settings

**Parameters:**
- `--action`: Operation to perform (required)
- `--name`: Secret/setting name (required for add-secret)
- `--value`: Secret value (optional, will prompt if not provided)
- `--env`: Environment - dev or prod (required)
- `--dry-run`: Preview without executing (optional)

**When to Use:**
- ✅ Setting up webhook secrets
- ✅ Before deploying to staging (sync settings!)
- ✅ Adding new API keys or credentials
- ✅ Troubleshooting "undefined" errors
- ✅ After Bicep infrastructure updates

**Examples:**

**Generate a secure secret:**
```bash
/skill:azure-config --action generate-secret
```

**Add a secret to Key Vault (dev environment):**
```bash
/skill:azure-config --action add-secret --name graph-client-state --env dev
# Claude will prompt for the secret value securely
```

**Add a secret with value provided:**
```bash
/skill:azure-config --action add-secret --name api-key --value "sk_abc123..." --env prod
```

**Sync staging slot before deployment (CRITICAL):**
```bash
/skill:azure-config --action sync-staging --env prod
```

**Verify all settings are accessible:**
```bash
/skill:azure-config --action verify-settings --env dev
```

**Restart Function App after settings change:**
```bash
/skill:azure-config --action restart --env prod
```

**Preview operations without executing:**
```bash
/skill:azure-config --action add-secret --name test-secret --env dev --dry-run
```

**Expected Output:**
```
🔧 Azure Configuration: add-secret
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Environment: dev
Resource Group: rg-invoice-agent-dev
Key Vault: kv-invoice-agent-dev
Function App: func-invoice-agent-dev

Adding secret: graph-client-state
Secret URI: https://kv-invoice-agent-dev.vault.azure.net/secrets/graph-client-state/abc123

Configuring Function App setting: GRAPH_CLIENT_STATE
Reference: @Microsoft.KeyVault(SecretUri=https://...)

Restarting Function App... ✅

Verifying access... ✅
Setting loaded successfully!

✅ Configuration completed successfully
```

**Common Issues:**
- **"undefined" in settings:** Run `verify-settings` to diagnose, then `restart`
- **Permission denied:** Check Managed Identity has Key Vault Secrets User role
- **Staging slot issues:** Always `sync-staging` before deploying to staging

---

### 3. Azure Function Skill

**Purpose:** Scaffold new Azure Functions following project coding standards.

**File:** `.claude/skills/azure-function.md`

**What It Does:**
- Generates complete function implementation
- Creates function.json with proper bindings
- Adds Pydantic models for queue messages
- Generates comprehensive unit tests
- Updates project documentation
- Follows all project coding standards (25-line limit, error handling, etc.)

**Parameters:**
- `--name`: Function name in PascalCase (required)
- `--trigger`: Trigger type (required)
  - `timer`: Timer trigger with cron schedule
  - `queue`: Queue trigger
  - `http`: HTTP trigger
  - `blob`: Blob trigger
- `--input-queue`: Input queue name (for queue trigger)
- `--output-queue`: Output queue name (if writing to queue)
- `--schedule`: Cron schedule (for timer trigger)
- `--http-methods`: HTTP methods comma-separated (for HTTP trigger)
- `--description`: Function purpose description (required)

**When to Use:**
- ✅ Creating new Azure Functions
- ✅ Adding features that require new processing steps
- ✅ Building new API endpoints
- ✅ Creating scheduled tasks

**Examples:**

**Queue-triggered function:**
```bash
/skill:azure-function \
  --name ProcessRefund \
  --trigger queue \
  --input-queue refund-requests \
  --output-queue refund-processed \
  --description "Process refund requests and validate against transaction history"
```

**Timer-triggered function (cron job):**
```bash
/skill:azure-function \
  --name DailyReport \
  --trigger timer \
  --schedule "0 0 9 * * *" \
  --description "Generate daily invoice processing summary and send to management"
```

**HTTP API endpoint:**
```bash
/skill:azure-function \
  --name UpdateVendor \
  --trigger http \
  --http-methods POST,PUT \
  --description "Update vendor information in VendorMaster table with validation"
```

**Expected Output:**
```
🎉 Azure Function Generated: ProcessRefund
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Trigger Type: queue
Input: refund-requests queue
Output: refund-processed queue
Description: Process refund requests and validate against transaction history

📁 Files Created:
✅ src/ProcessRefund/__init__.py (45 lines)
✅ src/ProcessRefund/function.json
✅ tests/unit/test_process_refund.py
✅ src/shared/models.py (updated with RefundRequest model)

📋 Next Steps:
1. Review generated code for business logic accuracy
2. Implement helper functions (main function currently 15 lines)
3. Add specific field validation to Pydantic model
4. Run tests: pytest tests/unit/test_process_refund.py -v
5. Run quality check: /skill:quality-check --mode pre-commit
6. Update ARCHITECTURE.md with detailed processing steps

🔍 Code Review Checklist:
- [x] Main function ≤25 lines
- [x] All external calls have error handling
- [x] Type hints complete (mypy strict)
- [x] Docstrings follow Google style
- [ ] Tests cover happy path + errors (customize tests)
- [x] Correlation ID in all log messages
- [x] Pydantic models use strict mode
- [x] Import structure correct (from shared.*)

💡 Helpful Commands:
# Run tests
pytest tests/unit/test_process_refund.py -v --cov=ProcessRefund

# Check formatting
black src/ProcessRefund tests/unit/test_process_refund.py

# Type check
mypy src/ProcessRefund/__init__.py --strict

# Run quality gates
/skill:quality-check --mode pre-commit
```

**What You Need to Do After:**
1. **Review generated code** - Claude generates a scaffold; customize business logic
2. **Implement helper functions** - Add the actual processing logic
3. **Customize tests** - Update test assertions for your specific logic
4. **Run quality check** - Ensure all standards met
5. **Update docs** - Add architecture details to ARCHITECTURE.md

---

## Diagnostic Skills

These skills help troubleshoot Azure Functions execution issues, monitor pipeline health, and diagnose configuration problems.

### 4. Azure Health Check Skill

**Purpose:** Comprehensive diagnostic of Function App runtime, configuration, and permissions.

**File:** `.claude/skills/azure-health-check.md`

**What It Checks:**
- Function App runtime status (running/stopped)
- All 7 functions deployed correctly
- Application settings and Key Vault references
- Managed Identity permissions (Storage, Key Vault)
- Key Vault access policies
- Application Insights configuration

**When to Use:**
- ✅ Function App not responding or behaving unexpectedly
- ✅ After deploying infrastructure or code changes
- ✅ Investigating "accepts requests but doesn't execute" issues
- ✅ Before troubleshooting specific function failures
- ✅ Regular health checks of production environment

**How to Use:**
```bash
# Invoke without parameters (defaults to prod)
Use the skill and Claude will execute all health checks

# Claude will check:
# - Runtime status
# - Configuration validity
# - Permissions
# - Deployment completeness
```

**Expected Output:**
```
=== AZURE FUNCTIONS HEALTH CHECK REPORT ===
Environment: prod

RUNTIME STATUS:
  ✅ Function app state: Running
  ✅ HTTPS only: Enabled

CONFIGURATION:
  ✅ All required app settings present
  ⚠️ Key Vault reference malformed: GRAPH_CLIENT_STATE

PERMISSIONS:
  ✅ Managed Identity configured
  ❌ Missing role: Storage Queue Data Contributor

IMMEDIATE ACTIONS REQUIRED:
  1. Fix Key Vault reference syntax
  2. Add Storage Queue Data Contributor role
```

**Common Issues Detected:**
- ❌ Malformed Key Vault references
- ❌ Missing Managed Identity role assignments
- ❌ Functions not deployed or missing
- ⚠️ Application Insights not configured

---

### 5. Queue Inspector Skill

**Purpose:** Real-time visibility into Azure Storage queue message flow and bottlenecks.

**File:** `.claude/skills/queue-inspector.md`

**What It Analyzes:**
- Message counts in all pipeline queues
- Peek at message contents (non-destructive)
- Poison queue contents (failed messages)
- Pipeline bottleneck detection
- Message flow analysis

**Queue Pipeline Flow:**
```
Email Arrives
    ↓
MailWebhook → webhook-notifications queue
    ↓
ExtractEnrich ← webhook-notifications + raw-mail
    ↓
to-post queue
    ↓
PostToAP
    ↓
notify queue
    ↓
Notify → Teams Webhook
```

**When to Use:**
- ✅ Messages not flowing through pipeline
- ✅ Functions appear healthy but no processing happening
- ✅ Investigating message processing delays
- ✅ Checking for poison queue failures
- ✅ Validating end-to-end message flow

**How to Use:**
```bash
# Inspect all queues (defaults to prod)
Use the skill and Claude will check all pipeline queues

# Claude will report:
# - Current message counts
# - Poison queue contents
# - Bottleneck detection
# - Sample message previews
```

**Expected Output:**
```
=== QUEUE INSPECTOR REPORT ===

QUEUE DEPTHS:
  webhook-notifications: 0 messages
  raw-mail: 3 messages
  to-post: 0 messages
  notify: 0 messages

POISON QUEUES:
  ⚠️ raw-mail-poison: 2 failed messages

PIPELINE HEALTH:
  ⚠️ Bottleneck detected at: raw-mail
  ExtractEnrich function may be failing

IMMEDIATE ACTIONS:
  1. Check Application Insights for ExtractEnrich errors
  2. Inspect poison message content
```

**Common Issues Detected:**
- ⚠️ Messages stuck in specific queue (bottleneck)
- ❌ High poison queue counts (repeated failures)
- 📭 All queues empty but emails not processed
- 🔄 Messages with high dequeue counts (retry loop)

---

### 6. Application Insights Log Analyzer Skill

**Purpose:** Query and analyze Application Insights telemetry to diagnose function execution failures.

**File:** `.claude/skills/appinsights-log-analyzer.md`

**What It Analyzes:**
- Exceptions and error-level logs
- Function invocation statistics
- Transaction traces by correlation ID
- Performance and timeout risks
- External dependency failures (Graph API, Storage, Teams)

**When to Use:**
- ✅ Functions are failing but error messages unclear
- ✅ Tracing specific transaction flow through pipeline
- ✅ Performance analysis (slow functions, timeouts)
- ✅ Dependency failure investigation
- ✅ Understanding error patterns and frequency

**How to Use:**
```bash
# Analyze last hour of logs (defaults to prod, 1h)
Use the skill and Claude will query Application Insights

# Claude can optionally:
# - Focus on specific time range (1h, 6h, 24h, 7d)
# - Filter by function name
# - Trace specific transaction_id
```

**Expected Output:**
```
=== APPLICATION INSIGHTS LOG ANALYSIS ===
Time Range: Last 1h

EXCEPTION SUMMARY:
  Total: 5 exceptions
  Most Common: KeyError - 'vendor' not in dictionary

FUNCTION HEALTH:
  MailIngest:      ✅ 100% success (12 invocations)
  ExtractEnrich:   ⚠️ 62.5% success (8 invocations)
  PostToAP:        ✅ 100% success (5 invocations)

DEPENDENCY FAILURES:
  Storage: 2 failures (Table EntityNotFound - VendorMaster)

TOP ISSUES:
  1. ExtractEnrich KeyError - missing vendor field (5x)
  2. VendorMaster table lookup failing (2x)

RECOMMENDED ACTIONS:
  1. Seed VendorMaster table with vendor data
  2. Add defensive key checking in ExtractEnrich
```

**Common Issues Detected:**
- 🔑 Key Vault access denied
- 📦 Storage account access failures
- 🔍 Table Storage EntityNotFound
- 🔗 Graph API authentication failures
- ⏱️ Function timeout approaching

---

### 7. Graph API Webhook Validator Skill

**Purpose:** Validate Microsoft Graph API webhook subscription configuration, permissions, and endpoint accessibility.

**File:** `.claude/skills/webhook-validator.md`

**What It Validates:**
- Active subscription status and expiration
- Environment variables (GRAPH_TENANT_ID, GRAPH_CLIENT_ID, etc.)
- Webhook endpoint URL format and accessibility
- Client state secret configuration
- Graph API authentication (token acquisition)
- Required API permissions
- SubscriptionManager function deployment

**When to Use:**
- ✅ Webhooks not triggering for new emails
- ✅ After webhook configuration changes
- ✅ Subscription expired or about to expire
- ✅ Investigating webhook authentication issues
- ✅ Regular webhook health monitoring

**How to Use:**
```bash
# Invoke skill (Claude will prompt for env, defaults to prod)
Use webhook-validator skill

# Claude will check:
# - Subscription status
# - Endpoint accessibility
# - Authentication
# - Configuration validity
```

**Expected Output:**
```
=== GRAPH API WEBHOOK VALIDATOR REPORT ===
Environment: prod

SUBSCRIPTION STATUS:
  ✅ Active subscription: 1 found
  ✅ Expiration: 132 hours remaining
  ✅ Subscription ID: abc123...

WEBHOOK ENDPOINT:
  ✅ HTTPS protocol
  ✅ Function key present
  ✅ Validation handshake successful
  ✅ Notification POST accepted (202)

GRAPH API AUTHENTICATION:
  ✅ Token acquisition successful
  ✅ Mailbox accessible

OVERALL STATUS: ✅ HEALTHY
```

**Common Issues Detected:**
- ❌ Subscription expired or missing
- ❌ Webhook URL malformed or inaccessible
- ❌ Client state mismatch
- ❌ Graph API authentication failures
- ⚠️ Subscription expiring soon (<48 hours)

---

### 8. End-to-End Pipeline Test Skill

**Purpose:** Test the complete email processing pipeline with a synthetic message and measure performance.

**File:** `.claude/skills/pipeline-test.md`

**What It Tests:**
- Message injection and queue flow
- Processing through all 4 queues
- Transaction record creation
- Blob storage integration
- End-to-end latency (<60s SLA)
- Poison queue health

**Pipeline Flow Tested:**
```
Test Message
    ↓
Entry Queue (webhook-notifications or raw-mail)
    ↓
ExtractEnrich → to-post queue
    ↓
PostToAP → notify queue
    ↓
Notify → Transaction Record + Blob
```

**When to Use:**
- ✅ After deploying code or infrastructure changes
- ✅ Validating complete system health
- ✅ Performance regression testing
- ✅ Verifying SLA compliance (<60s)
- ✅ Troubleshooting end-to-end flow issues

**How to Use:**
```bash
# Invoke skill (Claude will prompt for env, entry point, timeout)
Use pipeline-test skill

# Recommended settings:
# - env: dev (safer for testing)
# - entry_point: raw-mail (simpler path)
# - timeout: 120 (allows retries)
```

**Expected Output:**
```
=== END-TO-END PIPELINE TEST REPORT ===
Transaction ID: TEST-1732394821-A3F2

TEST EXECUTION:
  ✅ Test message injected into raw-mail queue

QUEUE FLOW:
  raw-mail: ✅ Processed (3s)
  to-post: ✅ Processed (5s)
  notify: ✅ Processed (2s)

TRANSACTION RECORD:
  ✅ Record created
  Status: unknown (expected for test)

PERFORMANCE:
  Total Duration: 15s
  SLA Target: <60s
  Status: ✅ Within SLA
  Rating: Excellent

OVERALL RESULT: ✅ PASS
```

**Common Issues Detected:**
- ⚠️ High latency (>60 seconds)
- ❌ Messages stuck in specific queue
- ❌ Transaction record not created
- ❌ Test message in poison queue
- ⚠️ Exceptions in Application Insights logs

---

## 🔍 Recommended Diagnostic Workflow

When troubleshooting Function App issues, use diagnostic skills in this order:

### Step 1: Health Check
```
Use azure-health-check skill first
```
**Purpose:** Validate infrastructure, configuration, and permissions.

**Decision:**
- If critical issues found (stopped app, missing permissions) → Fix before proceeding
- If all clear → Proceed to queue inspection

---

### Step 2: Queue Inspector
```
Use queue-inspector skill
```
**Purpose:** Determine if messages are flowing or stuck.

**Decision:**
- If queues empty → Check if messages being created (webhook/timer)
- If bottleneck detected → Identify which function is failing
- If poison queues have messages → Inspect failed messages
- Proceed to log analysis for details

---

### Step 3: Log Analysis
```
Use appinsights-log-analyzer skill
```
**Purpose:** Get detailed error messages and root cause.

**Decision:** Use error logs to:
- Fix code bugs
- Adjust configuration
- Seed missing data (VendorMaster)
- Update permissions

---

## 🔄 Typical Workflow

### New Feature Development

```bash
# 1. Generate new function
/skill:azure-function --name ProcessInvoice --trigger queue --input-queue invoices --description "Process incoming invoices"

# 2. Implement business logic (customize generated code)
# ... edit src/ProcessInvoice/__init__.py ...

# 3. Run quality checks
/skill:quality-check --mode pre-commit --fix

# 4. If tests fail, fix and re-check
/skill:quality-check --mode pre-commit

# 5. Before creating PR
/skill:quality-check --mode pre-pr
```

### Deployment Workflow

```bash
# 1. Sync staging slot settings (CRITICAL!)
/skill:azure-config --action sync-staging --env prod

# 2. Run comprehensive quality check
/skill:quality-check --mode pre-deploy

# 3. If all passes, deploy via CI/CD
git push origin main
```

### Adding Configuration

```bash
# 1. Generate secure secret
/skill:azure-config --action generate-secret

# 2. Add to Key Vault
/skill:azure-config --action add-secret --name webhook-secret --env prod
# Paste generated secret when prompted

# 3. Verify it's accessible
/skill:azure-config --action verify-settings --env prod
```

---

## 🎓 Creating Your Own Skills

Want to create a custom skill? Here's the format:

```markdown
# Skill Name

Brief description of what this skill does.

## Purpose

Detailed explanation of the skill's purpose and benefits.

## Parameters

- `--param-name`: Description (required/optional)
- `--flag`: Description

## Instructions

Step-by-step instructions for Claude to follow:

1. First step with example commands
2. Second step with validation
3. Final step with output

## Output Format

Example of the expected output format.

## Examples

Concrete usage examples.

## Notes

Additional considerations or warnings.
```

**Save to:** `.claude/skills/your-skill-name.md`

**Use with:** `/skill:your-skill-name --param value`

---

## 📊 Skill Comparison Matrix

### Development Skills
| Skill | Frequency | Time Saved | Complexity Reduced | Best For |
|-------|-----------|------------|-------------------|----------|
| quality-check | Very High | 5-10 min | ⭐⭐⭐ | Every commit |
| azure-config | Medium | 15-20 min | ⭐⭐⭐⭐⭐ | Deployments, secrets |
| azure-function | High | 30-45 min | ⭐⭐⭐⭐⭐ | New features |

### Diagnostic Skills
| Skill | Frequency | Time Saved | Complexity Reduced | Best For |
|-------|-----------|------------|-------------------|----------|
| azure-health-check | Medium | 10-15 min | ⭐⭐⭐⭐ | Infrastructure issues |
| queue-inspector | High | 5-10 min | ⭐⭐⭐ | Pipeline bottlenecks |
| appinsights-log-analyzer | High | 15-20 min | ⭐⭐⭐⭐⭐ | Error diagnosis |
| webhook-validator | Low | 10-15 min | ⭐⭐⭐⭐ | Webhook config issues |
| pipeline-test | Medium | 20-30 min | ⭐⭐⭐⭐⭐ | End-to-end validation |

---

## 🚨 Common Pitfalls

### Mistake 1: Not syncing staging slot
**Problem:** Deploy to staging, get "undefined" errors  
**Solution:** Always run `/skill:azure-config --action sync-staging --env prod` before deploying

### Mistake 2: Skipping quality checks
**Problem:** CI/CD pipeline fails after push  
**Solution:** Run `/skill:quality-check --mode pre-commit` before every commit

### Mistake 3: Not customizing generated code
**Problem:** Function has no business logic  
**Solution:** `/skill:azure-function` generates a scaffold - you must add logic

### Mistake 4: Forgetting to restart after config changes
**Problem:** New settings not loaded  
**Solution:** Always restart Function App after adding secrets

---

## 💡 Pro Tips

### Tip 1: Chain Skills for Complex Workflows
```bash
# Generate function, then check quality
/skill:azure-function --name NewFunc --trigger queue --input-queue data --description "Process data"
# ... implement logic ...
/skill:quality-check --mode pre-commit --fix
```

### Tip 2: Use --dry-run for Safety
```bash
# Preview what would happen
/skill:azure-config --action add-secret --name test --env prod --dry-run
```

### Tip 3: Quality Check Modes
- Use `pre-commit` during development (fast)
- Use `pre-pr` before creating pull request (thorough)
- Use `pre-deploy` before production deployment (comprehensive)

### Tip 4: Keep Skills Updated
If you discover new patterns or best practices, update the skill files to encode that knowledge for future use.

---

## 📖 Quick Reference

### Development Skills

**Quality Check**
```bash
/skill:quality-check --mode pre-commit [--fix]
```

**Azure Config**
```bash
# Common operations
/skill:azure-config --action generate-secret
/skill:azure-config --action add-secret --name SECRET_NAME --env ENV
/skill:azure-config --action sync-staging --env prod
/skill:azure-config --action verify-settings --env ENV
/skill:azure-config --action restart --env ENV
```

**Azure Function**
```bash
# Queue trigger
/skill:azure-function --name FuncName --trigger queue --input-queue in --output-queue out --description "..."

# Timer trigger
/skill:azure-function --name FuncName --trigger timer --schedule "0 0 * * * *" --description "..."

# HTTP trigger
/skill:azure-function --name FuncName --trigger http --http-methods POST --description "..."
```

### Diagnostic Skills

**Azure Health Check**
```bash
# Invoke skill - Claude will prompt for env (defaults to prod)
Use azure-health-check skill
```

**Queue Inspector**
```bash
# Invoke skill - Claude will check all queues
Use queue-inspector skill
```

**Application Insights Log Analyzer**
```bash
# Invoke skill - Claude will query last hour of logs
Use appinsights-log-analyzer skill

# Can specify time range when asked (1h, 6h, 24h, 7d)
```

**Graph API Webhook Validator**
```bash
# Invoke skill - Claude will validate webhook configuration
Use webhook-validator skill

# Claude will check subscription, endpoint, authentication
```

**End-to-End Pipeline Test**
```bash
# Invoke skill - Claude will run synthetic test
Use pipeline-test skill

# Recommended: Use dev env, raw-mail entry point
```

---

## 🎯 Next Steps

### For Development
1. **Try the quality check skill:**
   ```bash
   /skill:quality-check --mode pre-commit
   ```

2. **Explore azure-config for current project:**
   ```bash
   /skill:azure-config --action verify-settings --env dev
   ```

3. **Generate a test function to see the workflow:**
   ```bash
   /skill:azure-function --name TestFunction --trigger http --description "Test skill generation"
   ```

### For Troubleshooting
1. **Check Function App health:**
   ```
   Use azure-health-check skill
   ```

2. **Inspect queue message flow:**
   ```
   Use queue-inspector skill
   ```

3. **Analyze recent errors:**
   ```
   Use appinsights-log-analyzer skill
   ```

4. **Validate webhook configuration:**
   ```
   Use webhook-validator skill
   ```

5. **Test complete pipeline:**
   ```
   Use pipeline-test skill
   ```

### For Learning
1. **Read the skill files** in `.claude/skills/` to understand how they work
2. **Create your own skill** for a task you do frequently
3. **Update existing skills** with new patterns you discover

---

**Last Updated:** 2025-11-23
**Maintained By:** Engineering Team
**Version:** 2.0

For questions or issues with skills, create a GitHub issue or discuss in the #invoice-automation Teams channel.
