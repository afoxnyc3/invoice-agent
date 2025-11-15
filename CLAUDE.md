# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

## Deployment Validation Checklist

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

---

## Staging Slot Deployment Pattern

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

## Integration with Slash Commands

Once development workflow is established, these slash commands streamline work:

- `/init` - Initialize new feature branch with issue context
- `/build` - Generate code stubs from specification
- `/test` - Run full test suite before PR
- `/deploy` - Merge feature branch and trigger CI/CD
- `/status` - Show current branch status and blockers

---

## Project Overview

Azure serverless invoice processing system that automates email-to-AP workflow using queue-based Azure Functions, Table Storage for vendor lookups, and Teams webhooks for notifications. NetSuite handles all approval workflows downstream.

## Architecture & Flow

```
Email (5min timer) → MailIngest → Queue → ExtractEnrich → Queue → PostToAP → Queue → Notify → Teams
                         ↓                      ↓                     ↓
                    Blob Storage          VendorMaster         InvoiceTransactions
```

### Key Design Decisions
- **Serverless Functions** over containers: Variable workload (5-50/day) makes pay-per-execution ideal
- **Table Storage** over Cosmos DB: 100x cheaper for simple vendor lookups (<1000 vendors)
- **Queue-based** decoupling: Natural error boundaries and retry mechanisms
- **Email routing** to AP: Maintains existing workflow, no NetSuite integration needed for MVP
- **Simple webhooks** only: No Teams bot framework complexity

## Commands

### Local Development
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

### Testing
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

### Deployment
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

## Slash Commands

The project includes AI automation slash commands in `.claude/commands/`:
- `/init` - Set up local environment and Azure infrastructure
- `/build` - Generate function code from specifications
- `/test` - Run comprehensive test suite
- `/deploy` - Deploy to Azure with staging slot pattern
- `/status` - Check system health and queue depths

## Critical Constraints

### Function Design
- **25-line function limit** enforced for maintainability (helper functions extracted)
- Each function must handle one specific task
- All external calls require explicit error handling
- Use ULID for transaction IDs (sortable, unique)

### Import Structure (Azure Functions Compatible)
- **IMPORTANT:** Use `from shared.*` not `from src.shared.*`
- **IMPORTANT:** Use `from functions.*` not `from src.functions.*`
- Tests run with `PYTHONPATH=./src` set (configured in pytest.ini)
- This matches Azure Functions runtime working directory expectations

### Queue Message Flow
- `raw-mail`: Email metadata + blob URL
- `to-post`: Enriched vendor data with GL codes
- `notify`: Formatted notification messages
- Poison queue after 5 retry attempts

### Data Models (Pydantic)
- `RawMail`: Email ingestion schema
- `EnrichedInvoice`: Vendor-enriched data
- `NotificationMessage`: Teams webhook payload
- All models require strict validation

## Integration Points

### Microsoft Graph API
- Auth: Service principal with certificate/secret
- Permissions: `Mail.Read`, `Mail.Send`
- Throttling: Honor retry-after headers
- Mailbox: Shared inbox configured via `INVOICE_MAILBOX` env var

### Azure Table Storage
- `VendorMaster`: PartitionKey="Vendor", RowKey=vendor_name_lower
- `InvoiceTransactions`: PartitionKey=YYYYMM, RowKey=ULID
- Batch operations for performance
- No complex queries (use PartitionKey+RowKey only)

### Teams Webhooks
- Simple message cards only (no adaptive cards)
- Non-critical path (failures don't block processing)
- Three types: success (green), warning (orange), error (red)

## Error Handling Patterns

### Transient Failures
- Retry 3x with exponential backoff (2s, 4s, 8s)
- Graph API throttling: Use retry-after header
- Queue visibility timeout: 5 minutes

### Business Errors
- Unknown vendor: Flag and continue with "UNKNOWN"
- Missing attachment: Process anyway, log warning
- Malformed email: Skip and mark as read

### Critical Failures
- Storage down: Circuit breaker pattern
- Graph API auth failure: Alert ops, halt processing
- Key Vault unreachable: Use cached secrets (1hr TTL)

## Performance Targets

- End-to-end: <60 seconds per invoice
- Vendor match rate: >80%
- Error rate: <1%
- Concurrent processing: 50 invoices
- Cold start: ~2-4 seconds (Python on Linux)

## Current Implementation Status

**Phase 1 (MVP) - DEPLOYED TO PRODUCTION (Nov 14, 2024):**
- ✅ Project structure and documentation
- ✅ Infrastructure templates (Bicep) - Deployed to Azure
- ✅ Data models and schemas (Pydantic with full validation)
- ✅ Core functions - All 5 deployed and active in production
  - MailIngest: Email polling with blob storage (timer trigger)
  - ExtractEnrich: Vendor lookup and enrichment (queue trigger)
  - PostToAP: Email composition and sending (queue trigger)
  - Notify: Teams webhook notifications (queue trigger)
  - AddVendor: HTTP endpoint for vendor management (HTTP trigger)
- ✅ Integration with Graph API (full MSAL auth, retry, throttling)
- ✅ Shared utilities (ULID, logger, retry logic, email parser)
- ✅ CI/CD Pipeline (98 tests passing, 96% coverage, slot swap pattern)
- ✅ Staging slot configuration (manual setup after infrastructure deployment)
- 🟡 Vendor seeding script (implemented at infrastructure/scripts/seed_vendors.py, **execution pending**)

### Deployment Lessons Learned (Critical for Next Iteration)
1. **Staging Slot Configuration**: Must manually sync app settings from production to staging after Bicep deployment. See DEPLOYMENT_GUIDE.md Step 2.5.
2. **Artifact Path Handling**: GitHub Actions download-artifact@v4 creates directory automatically. Upload ZIP directly, not in subdirectory.
3. **Function App Restart**: App settings changes require Function App restart to take effect. Not automatic.
4. **CI/CD Workflow**: Test + Build must pass BEFORE staging deployment. Staging deployment blocks production approval.

### Activation Blockers (Prevents Live Processing)
- **VendorMaster table is empty**: Must run seed script before system can match vendors
- **No production testing**: Waiting for vendor data to perform end-to-end test

### Recommended Next Actions
1. Execute: `python infrastructure/scripts/seed_vendors.py --env prod`
2. Send test invoice email to configured mailbox
3. Monitor Application Insights for execution
4. Verify Teams notifications received
5. Measure actual end-to-end performance

**Phase 2 (Planned - Not Started):**
- PDF extraction (OCR/text extraction)
- AI vendor matching (fuzzy matching for unknowns)
- Duplicate detection

**Phase 3 (Future - Not Planned):**
- NetSuite integration (direct API posting)
- Power BI analytics dashboard
- Multi-mailbox support