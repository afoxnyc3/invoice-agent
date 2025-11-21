# CLAUDE.md - Invoice Agent Development Guide

This file provides workflow instructions for Claude Code when working with code in this repository.

> **For technical architecture and system specifications, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**

---

## Development Workflow Overview

### The Golden Rule
**Always use feature branches, parallel agents, and pull requests before merging to main.** This ensures code quality, traceability, and the ability to review changes before they ship.

### Development Pattern
```
Issue Created → Feature Branch → Parallel Agents → Code Review (PR) → Merge to Main
```

---

## Feature Branch & PR Workflow

### When to Use Feature Branches
- **Always** - Every piece of work (feature, bugfix, docs, refactor)
- Create from `main`, merge back to `main` after PR approval
- Keep branches focused (one issue per branch)

### Branch Naming Pattern
```
feature/issue-XX-descriptive-name
bugfix/issue-XX-descriptive-name
refactor/issue-XX-descriptive-name
docs/issue-XX-descriptive-name
```

### Model Selection for Task Complexity
- **HAIKU** (30min-2hr): Config, scripts, docs, tooling
- **SONNET** (2-6hr): Pipelines, workflows, API integration, features
- **OPUS** (6+hr): System redesign, optimization, novel problems

---

## Commit Message Standards

### Format
```
type(scope): brief description

Detailed explanation of what changed and why.

Closes #XX (if applicable)
```

### Types
- `feat:` New feature
- `fix:` Bug fix
- `refactor:` Code reorganization without feature change
- `docs:` Documentation only
- `test:` Tests only
- `chore:` Dependency updates, tooling

### Examples
```
feat: add email domain normalization to ExtractEnrich

- Implement case-insensitive domain matching
- Replace dots with underscores in row keys
- Add validation for email format

Closes #8

---

fix: handle unknown vendor gracefully in ExtractEnrich

When vendor not found in VendorMaster, send registration
email to requestor instead of failing silently.

---

docs: complete vendor management guide

Added comprehensive guide with:
- Initial setup procedures
- Adding/updating vendors
- Query examples
- Troubleshooting
- Disaster recovery

Closes #14
```

---

## Pull Request Checklist

### Before Creating PR
- [ ] Feature branch created from `main`
- [ ] All acceptance criteria met
- [ ] Code follows project constraints (25-line functions, import structure, etc.)
- [ ] Tests pass locally
- [ ] Type checking passes (mypy)
- [ ] Security scan passes (bandit)
- [ ] Documentation updated
- [ ] No hardcoded secrets or credentials
- [ ] Commits have meaningful messages

### PR Description Template
```markdown
## Summary
One-line description of changes.

## What Changed
- Bullet point 1
- Bullet point 2
- Bullet point 3

## Acceptance Criteria
- [x] Criteria 1
- [x] Criteria 2
- [x] Criteria 3

## Testing
- Unit tests: 96% coverage maintained
- Integration tests: All passing
- Manual testing: Verified X, Y, Z

## Documentation
- Updated docs/FILE.md
- Added inline code comments
- Updated README

## Related Issues
Closes #XX
```

---

## Quality Gates (Must Pass Before Merge)

### Code Quality
- ✅ Black formatting check passes
- ✅ Flake8 linting passes
- ✅ mypy type checking passes
- ✅ 60% test coverage minimum

### Testing
- ✅ Unit tests: 100% passing
- ✅ Integration tests: 100% passing (if applicable)
- ✅ All tests use pytest with PYTHONPATH=./src

### Security
- ✅ bandit security scan passes
- ✅ No hardcoded credentials
- ✅ No secrets in code or docs

### Documentation
- ✅ CLAUDE.md updated if constraints changed
- ✅ Function docstrings complete
- ✅ README updated for new features
- ✅ CHANGELOG.md updated with user-facing changes

### Project Constraints
- ✅ Functions ≤25 lines (extract helpers)
- ✅ Import structure: `from shared.*`, `from functions.*`
- ✅ ULID used for transaction IDs
- ✅ Pydantic validation on all data models
- ✅ Error handling on all external calls

---

## Code Quality Standards

### Function Design
- **Max 25 lines per function** - Forces atomic, testable functions
- Each function must handle one specific task
- All external calls require explicit error handling
- Use ULID for transaction IDs (sortable, unique)

### Type Safety
- **Full type hints** - mypy in strict mode
- All function signatures fully typed
- All Pydantic models use strict validation

### Testing Requirements
- **60% coverage minimum** for MVP
- **Unit tests** for business logic
- **Integration tests** for queue flow
- **Fixtures** for queue messages

### Logging Standards
- **Structured logging** with correlation IDs
- **Log levels:** ERROR for failures, INFO for success, DEBUG for details
- **Application Insights** integration
- **Correlation ID** (ULID) in all log entries

---

## Critical Constraints

### Import Structure (Azure Functions Compatible)
- **IMPORTANT:** Use `from shared.*` not `from src.shared.*`
- **IMPORTANT:** Use `from functions.*` not `from src.functions.*`
- Tests run with `PYTHONPATH=./src` set (configured in pytest.ini)
- This matches Azure Functions runtime working directory expectations

### Queue Message Flow
- `webhook-notifications`: Graph API change notifications (NEW - webhook path)
- `raw-mail`: Email metadata + blob URL (fallback timer path)
- `to-post`: Enriched vendor data with GL codes
- `notify`: Formatted notification messages
- Poison queue after 5 retry attempts

### Data Models (Pydantic)
- `RawMail`: Email ingestion schema
- `EnrichedInvoice`: Vendor-enriched data
- `NotificationMessage`: Teams webhook payload
- All models require strict validation

---

## Development Commands

### Local Development Setup
See [docs/LOCAL_DEVELOPMENT.md](docs/LOCAL_DEVELOPMENT.md) for detailed instructions.

```bash
# Setup environment
cd src
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure (copy template and add Azure credentials)
cp local.settings.json.template local.settings.json

# Run locally with Azure Functions Core Tools
func start

# Run specific function for testing
func start --functions MailIngest
```

### Testing Commands
```bash
# Unit tests with coverage (from repo root, pytest.ini configured)
export PYTHONPATH=./src
pytest tests/unit --cov=functions --cov=shared --cov-fail-under=60 -v

# Or use pytest.ini configuration (automatically sets PYTHONPATH)
pytest

# Integration tests (requires Azurite)
docker run -d -p 10000:10000 -p 10001:10001 -p 10002:10002 azurite
pytest tests/integration -m integration

# Type checking
mypy src/functions src/shared --strict

# Security scan
bandit -r src/functions src/shared
```

### Code Quality Commands
```bash
# Format code
black src/functions src/shared tests/

# Check formatting
black --check src/functions src/shared tests/

# Lint
flake8 src/functions src/shared tests/

# Type check
mypy src/functions src/shared --strict

# Security scan
bandit -r src/functions src/shared
```

---

## Deployment Workflow

### Pre-Deployment Validation Checklist

**Before pushing to main:**
- [ ] All tests passing locally (`pytest`)
- [ ] Coverage ≥60% (`pytest --cov`)
- [ ] Code formatted (`black --check`)
- [ ] Linting passes (`flake8`)
- [ ] Type checking passes (`mypy`)
- [ ] Security scan passes (`bandit`)
- [ ] No hardcoded secrets or credentials

**For infrastructure changes:**
- [ ] Bicep templates validated (`az bicep build`)
- [ ] Parameter files match environments (dev/prod)
- [ ] Service principal permissions documented
- [ ] Key Vault secrets configured
- [ ] Staging slot app settings synced
- [ ] Rollback procedure tested

### Staging Slot Deployment Pattern

Azure Function Apps use a **slot swap pattern** for zero-downtime deployments:

```
Code → Test → Build → Deploy to Staging → Smoke Tests → Swap to Production
```

**Critical: Staging Slot App Settings**

Staging slot does NOT auto-sync app settings from production. After Bicep deployment:

```bash
# Get production settings
az functionapp config appsettings list \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --output json > /tmp/prod-settings.json

# Apply to staging slot
az functionapp config appsettings set \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --slot staging \
  --settings @/tmp/prod-settings.json

# Restart staging slot
az functionapp restart \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --slot staging
```

**Why?** Bicep copies initial config, but changes to production settings don't replicate to staging. This must be done manually before each deployment cycle or settings will show `undefined` errors.

### Deployment Commands
See [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) for detailed instructions.

```bash
# Deploy infrastructure (Bicep)
az deployment group create \
  --resource-group rg-invoice-agent-$ENV \
  --template-file infrastructure/bicep/main.bicep \
  --parameters infrastructure/parameters/$ENV.json

# Deploy functions
func azure functionapp publish func-invoice-agent-$ENV --python

# Seed vendor data
python infrastructure/scripts/seed_vendors.py --env $ENV
```

### Deployment Lessons Learned (Critical for Next Iteration)
1. **Staging Slot Configuration**: Must manually sync app settings from production to staging after Bicep deployment. See [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) Step 2.5.
2. **Artifact Path Handling**: GitHub Actions download-artifact@v4 creates directory automatically. Upload ZIP directly, not in subdirectory.
3. **Function App Restart**: App settings changes require Function App restart to take effect. Not automatic.
4. **CI/CD Workflow**: Test + Build must pass BEFORE staging deployment. Staging deployment blocks production approval.

---

## Quality Metrics to Track

Track these across all work:

| Metric | Target | Check |
|--------|--------|-------|
| Test Coverage | ≥60% | `pytest --cov` |
| Code Duplication | <5% | Code review |
| Function Size | ≤25 lines | `wc -l` |
| Comment Ratio | >10% | Code review |
| Type Coverage | 100% | `mypy --strict` |
| Security Scan Pass | 100% | `bandit` |
| Documentation | Complete | README checks |

---

## Common Pitfalls to Avoid

❌ **Don't:**
- Merge directly to main without PR
- Create sub-agents without clear acceptance criteria
- Skip testing before pushing
- Commit with unclear messages
- Hardcode secrets or credentials
- Ignore type checking or linting errors
- Create functions >25 lines
- Use wrong import structure (`from src.shared.*`)

✅ **Do:**
- Use feature branches for every issue
- Define acceptance criteria upfront
- Run tests and linting locally first
- Write descriptive commit messages
- Use GitHub secrets for credentials
- Fix all linting and type errors
- Extract helper functions for clarity
- Use correct imports (`from shared.*`)

---

## Scope Boundaries

### IN SCOPE ✅
- **Real-time email processing** via Graph API webhooks (<10 second latency)
- **Webhook subscription management** (automatic renewal every 6 days)
- **Fallback hourly polling** as safety net for missed notifications
- Attachment storage to Azure Blob
- Vendor extraction from email sender/subject
- Vendor lookup and enrichment (4 fields)
- AP email routing with standardized format
- Simple Teams webhook notifications
- Error handling and logging
- Transaction audit trail

### OUT OF SCOPE ❌
- Approval workflows (NetSuite handles)
- Payment processing (NetSuite handles)
- Complex vendor management UI (NetSuite handles)
- Interactive Teams cards with buttons
- PDF parsing (Phase 2)
- AI/LLM extraction (Phase 2)
- Multi-mailbox support (Phase 3)

---

## Slash Commands & Automation

The project includes AI automation slash commands in `.claude/commands/`:

- `/init` - Set up local environment and Azure infrastructure
- `/build` - Generate function code from specifications
- `/test` - Run comprehensive test suite before PR
- `/deploy` - Deploy to Azure with staging slot pattern
- `/status` - Check system health and queue depths

**Development Workflow:**
1. Use `/init` to set up environment
2. Use `/build` to generate functions
3. Use `/test` to validate
4. Use `/deploy` for production
5. Use `/status` to monitor health

---

## Communication Style

When working with this codebase, Claude should:

- **Be concise** - No fluff, get to the point
- **Show status** - ✅ Done, 🔄 In Progress, ❌ Failed
- **Explain errors** - What failed and why
- **Suggest fixes** - Don't just report problems

---

## Current Focus

**Webhook Migration Complete (Nov 20, 2024)**

Migrated from timer-based polling to event-driven webhooks using Microsoft Graph Change Notifications. System now processes emails in real-time (<10 seconds) with 70% cost savings.

**Current State:**
- ✅ All 7 functions deployed and active
  - **New:** MailWebhook (HTTP) - Receives Graph API notifications
  - **New:** SubscriptionManager (Timer) - Auto-renews subscriptions every 6 days
  - **Modified:** MailIngest - Now hourly fallback/safety net (was 5-min primary)
  - Existing: ExtractEnrich, PostToAP, Notify, AddVendor
- ✅ CI/CD pipeline operational (98 tests passing, 96% coverage)
- ✅ Infrastructure ready (staging + production slots)
- ✅ Webhook subscription active and tested
- 🟡 Awaiting vendor data seed to activate live processing

**Architecture Change:**
```
BEFORE: Timer (5 min) → Poll Mailbox → Process (5 min latency, $2/month)
AFTER:  Email Arrives → Webhook (<10 sec) → Process (<10 sec latency, $0.60/month)
```

**Next Steps:**
1. Seed VendorMaster table
2. End-to-end production testing with webhook flow
3. Performance measurement and monitoring
4. Phase 2: PDF extraction and AI vendor matching

---

## Quick Reference

### Essential Files
- **This file** - Development workflow and standards
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - Technical architecture and system design
- [docs/LOCAL_DEVELOPMENT.md](docs/LOCAL_DEVELOPMENT.md) - Local setup and development
- [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) - Deployment procedures
- [docs/operations/TROUBLESHOOTING_GUIDE.md](docs/operations/TROUBLESHOOTING_GUIDE.md) - Common issues and fixes
- [README.md](README.md) - Project overview and quick start

### Critical Paths
- Function code: `src/functions/`
- Shared utilities: `src/shared/`
- Tests: `tests/unit/` and `tests/integration/`
- Infrastructure: `infrastructure/bicep/`
- Documentation: `docs/`

---

**Version:** 2.0 (Refactored for clarity)
**Last Updated:** 2025-11-20
**Maintained By:** Engineering Team
