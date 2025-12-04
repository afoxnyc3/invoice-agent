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

## Issue-Driven Development Workflow

### The Process
All work items are tracked as GitHub Issues and follow this workflow:

```
Issue Created → Prioritized → Branch Created → Implementation → PR → Review → Merge → Issue Closed
```

### Issue Prioritization

| Priority | Label | Timeline | Criteria |
|----------|-------|----------|----------|
| P0 | `priority:critical` | This Week | Blocking production, security vulnerability, data loss risk |
| P1 | `priority:high` | This Sprint | Significant quality/reliability impact |
| P2 | `priority:medium` | Next Sprint | Improvement, non-blocking |
| P3 | `priority:low` | Backlog | Nice-to-have, future enhancement |

### Issue Labels

**Priority:**
- `priority:critical` - Must fix immediately
- `priority:high` - Fix this sprint
- `priority:medium` - Fix next sprint
- `priority:low` - Backlog

**Type:**
- `type:bug` - Something is broken
- `type:feature` - New functionality
- `type:test` - Test coverage
- `type:docs` - Documentation
- `type:infra` - Infrastructure/CI/CD
- `type:cleanup` - Tech debt, refactoring

### Branch Naming from Issues

```
{type}/issue-{number}-{brief-description}

Examples:
- bugfix/issue-5-fix-message-loss
- test/issue-1-mail-webhook-tests
- infra/issue-4-staging-settings-sync
- cleanup/issue-7-remove-dead-code
```

### Linking Issues to PRs

Always reference the issue in:
1. Branch name: `bugfix/issue-5-fix-message-loss`
2. PR title: `fix: resolve message loss in MailWebhookProcessor (closes #5)`
3. PR description: `Closes #5`

### GitHub Projects Integration

We use GitHub Projects for sprint tracking with the "Invoice Agent Roadmap" project board.

**Board Columns:**
- **Backlog** - P3 items not yet scheduled
- **Next Sprint** - P2 items for upcoming sprint
- **Current Sprint** - P0/P1 items for this 2-week sprint
- **In Progress** - Actively being worked on
- **In Review** - PR submitted, awaiting review
- **Done** - Completed and merged

**Sprint Cadence:** 2 weeks
- P0 (Critical): Fix this week
- P1 (High): Fix this sprint (2 weeks)
- P2 (Medium): Fix next sprint
- P3 (Low): Backlog

**Sprint Commands:**
```bash
# View project board
gh project view "Invoice Agent Roadmap" --owner @me

# Add issue to project
gh project item-add "Invoice Agent Roadmap" --owner @me --url <issue-url>

# View current sprint items
gh issue list --label "priority:critical,priority:high" --state open

# View all issues by priority
gh issue list --state open --json number,title,labels --jq 'sort_by(.labels[0].name)'
```

### Audit-Driven Issues

Periodic codebase audits generate issues tagged with `audit:YYYY-MM`. This allows:
- Tracking technical debt over time
- Measuring remediation velocity
- Prioritizing based on audit findings

**Running an Audit:**
1. Use `/prime` to onboard with project context
2. Request comprehensive codebase audit
3. Review findings and create issues
4. Add `audit:YYYY-MM` label to all generated issues
5. Prioritize and add to project board

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
- [ ] **Code formatted with black** (`black src/ tests/`)
- [ ] **Linting passes** (`flake8 src/ tests/`)
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
- Unit tests: 85%+ coverage maintained (389 tests)
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
- ✅ 85% test coverage minimum

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
- **Max cyclomatic complexity 10** - Measure actual decision points, not arbitrary line counts
  - **Complexity 1-3**: Ideal (most functions)
  - **Complexity 4-7**: Acceptable (moderate complexity)
  - **Complexity 8-10**: Review & consider refactoring (high complexity)
  - **Complexity >10**: Must refactor (unacceptable)
- **Line count guidance** (soft limit, not enforced):
  - Aim for ≤25 lines for simple functions
  - Orchestration/main functions: ≤50 lines acceptable
  - Templates/data builders: ≤40 lines acceptable
  - Configuration/initialization: ≤35 lines acceptable
- **When to extract helper functions**:
  1. When complexity approaches 8 (proactive reduction)
  2. When a function has multiple distinct responsibilities
  3. When logic is reusable across multiple call sites
  4. When error handling adds significant lines
- **Each function must handle one specific task**
- **All external calls require explicit error handling**
- **Use ULID for transaction IDs** (sortable, unique)

### Type Safety
- **Full type hints** - mypy in strict mode
- All function signatures fully typed
- All Pydantic models use strict validation

### Testing Requirements
- **85% coverage minimum** (enforced by pytest)
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
pytest tests/unit --cov=functions --cov=shared --cov-fail-under=85 -v

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
- [ ] Coverage ≥85% (`pytest --cov`)
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
| Test Coverage | ≥85% | `pytest --cov` |
| Code Duplication | <5% | Code review |
| Function Complexity | ≤10 | Code review (cyclomatic) |
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
- **PDF vendor extraction** using pdfplumber + Azure OpenAI (gpt-4o-mini)
- **AI-powered vendor identification** with graceful fallback to email domain
- Attachment storage to Azure Blob
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
- Advanced PDF parsing (invoice amounts, line items - Phase 2)
- OCR for scanned/image-based PDFs (Phase 2)
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

## Skills Reference

Skills are reusable diagnostic and automation prompts in `.claude/skills/`. Use them proactively when conditions match.

### When to Use Skills (Decision Matrix)

| Condition | Skill | Action |
|-----------|-------|--------|
| Before any commit | `quality-check` | Run with `--mode pre-commit` |
| Before creating PR | `quality-check` | Run with `--mode pre-pr` |
| Adding Azure secrets | `azure-config` | Use `--action add-secret` |
| Before deploying to staging | `azure-config` | Use `--action sync-staging` |
| Creating new Azure Function | `azure-function` | Scaffold with triggers/queues |
| Functions not executing | `azure-health-check` | Check runtime, config, permissions |
| Messages stuck in queues | `queue-inspector` | Check depths, poison queues |
| Investigating errors | `appinsights-log-analyzer` | Query traces and exceptions |
| Webhooks not triggering | `webhook-validator` | Check subscription, endpoint |
| Testing full pipeline | `pipeline-test` | Run synthetic message test |
| Duplicate invoices reported | `deduplication-analyzer` | Analyze dedup effectiveness |
| Measuring webhook success | `webhook-metrics-analyzer` | Compare webhook vs fallback |
| Setting up duplicate alerts | `alert-config-builder` | Create Azure Monitor rules |
| Building dedup tests | `dedup-test-builder` | Generate test fixtures |
| Implementing mailbox restrictions | `graph-security-policy` | Configure Application Access Policy |

### Skill Categories

**Development (use during coding):**
- `quality-check` - Run before commits/PRs
- `azure-function` - Scaffold new functions
- `azure-config` - Manage secrets/settings

**Diagnostic (use when troubleshooting):**
- `azure-health-check` - First step for any Azure issue
- `queue-inspector` - Check message flow
- `appinsights-log-analyzer` - Deep error analysis
- `webhook-validator` - Webhook-specific issues
- `pipeline-test` - End-to-end validation

**Analysis (use for metrics/reporting):**
- `deduplication-analyzer` - Duplicate detection metrics
- `webhook-metrics-analyzer` - Webhook performance metrics

**Configuration (use for setup tasks):**
- `alert-config-builder` - Create monitoring alerts
- `dedup-test-builder` - Generate test cases
- `graph-security-policy` - Mailbox access restrictions

### Diagnostic Workflow

When troubleshooting Function App issues, use skills in this order:

1. **azure-health-check** → Verify infrastructure is healthy
2. **queue-inspector** → Check if messages are flowing
3. **appinsights-log-analyzer** → Get detailed error messages
4. **webhook-validator** → If webhook-specific issue

### Skill Invocation

Development skills use parameters:
```bash
/skill:quality-check --mode pre-commit --fix
/skill:azure-config --action sync-staging --env prod
```

Diagnostic skills are conversational:
- "Use the azure-health-check skill"
- "Run the queue-inspector skill for prod"

> **Full Documentation:** See [docs/SKILLS_GUIDE.md](docs/SKILLS_GUIDE.md) for detailed parameters, examples, and output formats.

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
- ✅ All 9 functions deployed and active
  - **MailWebhook** (HTTP) - Receives Graph API notifications
  - **MailWebhookProcessor** (Queue) - Processes webhook notifications with **PDF extraction**
  - **SubscriptionManager** (Timer) - Auto-renews subscriptions every 6 days
  - **MailIngest** (Timer) - Hourly fallback/safety net
  - **ExtractEnrich** (Queue) - Uses AI-extracted vendor names, falls back to email domain
  - **PostToAP** (Queue) - Routes enriched invoices to AP
  - **Notify** (Queue) - Teams webhook notifications
  - **AddVendor** (HTTP) - Vendor management API
  - **Health** (HTTP) - Health check endpoint
- ✅ **PDF Vendor Extraction** (Nov 24, 2024)
  - Intelligent vendor extraction from PDF invoices using pdfplumber + Azure OpenAI
  - 95%+ accuracy, ~500ms latency, ~$0.001/invoice cost
  - Graceful fallback to email domain extraction if PDF extraction fails
  - No breaking changes - optional feature with degradation path
- ✅ CI/CD pipeline operational (389 tests, 85%+ coverage)
- ✅ All P0 and P1 issues resolved (Nov 28, 2025)
- ✅ Infrastructure ready (staging + production slots)
- ✅ Webhook subscription active and tested
- ✅ VendorMaster table seeded and operational
- ✅ System ready for production invoice processing
- ✅ **AZQR Phase 1 Complete** (Dec 3, 2024)
  - Container soft delete, Key Vault diagnostics, auto-heal, cost tags
  - $0-2/month cost impact for diagnostic log ingestion

**Architecture Change:**
```
BEFORE: Timer (5 min) → Poll Mailbox → Process (5 min latency, $2/month)
AFTER:  Email Arrives → Webhook (<10 sec) → Process (<10 sec latency, $0.60/month)
```

**Next Steps:**
1. End-to-end production testing with webhook flow
2. Performance measurement and monitoring (actual metrics vs targets)
3. Monitor processing in Application Insights
4. Address P2 issues in next sprint

---

## Architecture Decision Records (ADRs)

### Location

ADRs are stored in `/docs/adr/` with naming convention `NNNN-short-title.md`

### When to Create an ADR

Create an ADR when making decisions about:
- Frameworks, languages, or major dependencies
- Database or storage choices
- API design patterns or data models
- Authentication/authorization approaches
- Infrastructure or deployment architecture
- Integration patterns with external systems
- Significant refactoring strategies

### When NOT to Create an ADR

- Bug fixes or minor patches
- Implementation details that don't affect architecture
- Dependency version updates (unless major breaking changes)
- Code style or formatting decisions

### ADR Workflow

1. When reviewing code that involves architectural decisions, check `/docs/adr/` for relevant existing ADRs
2. If a change conflicts with an existing ADR, flag it — don't assume the ADR is wrong
3. If a significant decision lacks an ADR, recommend creating one
4. When creating ADRs, use the template at `/docs/adr/0000-template.md`

### ADR Quality Standards

- **Context**: Should be understandable by someone unfamiliar with the project
- **Rationale**: Include key reasons for the decision
- **Decision**: Clear, active voice ("We will..." not "It was decided...")
- **Consequences**: Honest about tradeoffs, include mitigations for negatives

### Current ADR Count

- **31 ADRs** documented (0001-0031)
- **4 Superseded**: 0004, 0008, 0012, 0017
- See [docs/adr/README.md](docs/adr/README.md) for full index

---

## Quick Reference

### Essential Files
- **This file** - Development workflow and standards
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - Technical architecture and system design
- [docs/adr/README.md](docs/adr/README.md) - Architecture Decision Records index
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
- ADRs: `docs/adr/`

---

**Version:** 2.8 (Documentation Audit)
**Last Updated:** 2024-12-04
**Maintained By:** Engineering Team
