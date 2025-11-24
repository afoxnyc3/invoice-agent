# CLAUDE.md - Development Workflow Guide

**Purpose:** Development standards and workflow for Invoice Agent
**Audience:** Developers, AI assistants, code reviewers
**Status:** Production-Ready (Lessons Learned Edition)

> **Technical specifications in [SPEC.md](SPEC.md) | This document covers development workflow**

---

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [Development Workflow](#development-workflow)
3. [Code Quality Standards](#code-quality-standards)
4. [Testing Requirements](#testing-requirements)
5. [Git Workflow](#git-workflow)
6. [Infrastructure Development](#infrastructure-development)
7. [Deployment Procedures](#deployment-procedures)
8. [Common Tasks & Skills](#common-tasks--skills)
9. [Troubleshooting Guide](#troubleshooting-guide)

---

## Quick Reference

### Project Constraints

| Category | Standard | Tool/Check |
|----------|----------|------------|
| **Complexity** | Cyclomatic ≤10 | `radon cc --min C` |
| **Parameters** | ≤3 per function | Manual review |
| **Nesting** | ≤3 levels deep | Manual review |
| **Test Coverage** | ≥60% | `pytest --cov` |
| **Type Checking** | 100% coverage | `mypy --strict` |
| **Security** | No high/critical | `bandit -ll` |

### Essential Commands

```bash
# Setup
make setup              # Initialize local environment

# Development
make run                # Start functions locally
make test               # Run tests with coverage
make lint               # Check code quality
make complexity         # Check cyclomatic complexity

# Deployment
make deploy-dev         # Deploy to development
make deploy-staging     # Deploy to staging slot
make deploy-prod        # Swap staging to production

# Infrastructure
make infra-validate     # Validate Bicep templates
make infra-test         # Run infrastructure tests
make infra-deploy       # Deploy infrastructure
```

### Critical Paths

```
Source Code:        src/
├─ Functions:       MailWebhook/, ExtractEnrich/, PostToAP/, etc.
├─ Shared Utils:    shared/
└─ Config:          host.json, requirements.txt

Tests:              tests/
├─ Unit:            unit/
├─ Integration:     integration/
└─ Infrastructure:  infrastructure/

Infrastructure:     infrastructure/
├─ Bicep:           bicep/
├─ Parameters:      parameters/
└─ Scripts:         scripts/

Documentation:      lessons/
├─ Spec:            SPEC.md (architecture)
└─ Workflow:        CLAUDE.md (this file)
```

---

## Development Workflow

### The Golden Rule

**Always use feature branches → Pull Requests → Code Review → Merge to main**

```
Issue Created → Feature Branch → Development → PR → Review → Merge to Main
```

No exceptions. Direct commits to `main` are blocked by branch protection.

---

### Standard Development Cycle

#### 1. Start New Work

```bash
# Create feature branch from main
git checkout main
git pull origin main
git checkout -b feature/issue-42-add-pdf-extraction

# Naming convention
feature/issue-XX-short-description   # New feature
bugfix/issue-XX-short-description    # Bug fix
refactor/issue-XX-short-description  # Code refactor
docs/issue-XX-short-description      # Documentation
```

#### 2. Write Code

**Follow TDD (Test-Driven Development):**

```bash
# 1. Write failing test
pytest tests/unit/test_pdf_extraction.py -v  # ❌ FAIL

# 2. Write minimal code to pass
# Edit: src/shared/pdf_extractor.py

# 3. Run test again
pytest tests/unit/test_pdf_extraction.py -v  # ✅ PASS

# 4. Refactor if needed (keep tests passing)

# 5. Check complexity
radon cc src/shared/pdf_extractor.py --min C  # Should be empty (no complex functions)
```

**Development Loop:**

```bash
# Make changes...

# Run affected tests
pytest tests/unit/test_extract_enrich.py -v

# Check all tests
make test

# Check code quality
make lint

# Check complexity
make complexity

# Commit when all green
git add src/shared/pdf_extractor.py tests/unit/test_pdf_extraction.py
git commit -m "feat(extract): add PDF text extraction using PyPDF2"
```

#### 3. Create Pull Request

```bash
# Push branch
git push origin feature/issue-42-add-pdf-extraction

# Create PR (use GitHub CLI or web UI)
gh pr create \
  --title "feat: Add PDF text extraction for invoices" \
  --body "$(cat <<'EOF'
## Summary
Adds PDF text extraction to improve vendor identification from attachments.

## Changes
- Added `shared/pdf_extractor.py` with PyPDF2 integration
- Updated `ExtractEnrich` to use PDF extraction as fallback
- Added 12 unit tests for PDF parsing edge cases

## Testing
- ✅ Unit tests: 98/98 passing (96% coverage maintained)
- ✅ Integration test: PDF invoices from Adobe, AWS, Stripe
- ✅ Manual test: 10 real invoices from last month

## Acceptance Criteria
- [x] Extract vendor name from PDF if email sender is generic
- [x] Handle multi-page PDFs
- [x] Graceful fallback if PDF is encrypted/image-based
- [x] Tests cover edge cases (empty PDF, malformed PDF)

Closes #42
EOF
)"
```

#### 4. Code Review

**Reviewer Checklist:**

- [ ] Tests added/updated for new functionality
- [ ] Complexity metrics passing (`radon cc` shows no functions >10)
- [ ] Type hints complete (`mypy --strict` passes)
- [ ] Security scan passes (`bandit`)
- [ ] Documentation updated (docstrings, README if needed)
- [ ] No hardcoded secrets or credentials
- [ ] Error handling on external calls (Graph API, Table Storage)
- [ ] Logging includes correlation IDs

**Common Review Comments:**

```python
# ❌ BAD: High complexity, no error handling
def process_invoice(msg):
    email = json.loads(msg)
    if email['sender']:
        vendor = table.get_entity('Vendor', email['sender'].split('@')[1])
        if vendor:
            if vendor['GLCode'].startswith('6'):
                dept = 'IT'
            elif vendor['GLCode'].startswith('7'):
                dept = 'Marketing'
            else:
                dept = 'General'
    send_to_ap(email, dept)

# ✅ GOOD: Low complexity, error handling, clear flow
def process_invoice(msg: str) -> None:
    """Process invoice message from raw-mail queue."""
    try:
        email = parse_message(msg)
        vendor = lookup_vendor(email.sender)
        enriched = enrich_with_vendor(email, vendor)
        send_to_ap(enriched)
    except VendorNotFoundError:
        handle_unknown_vendor(email)
    except GraphAPIError as e:
        logger.error(f"Graph API error: {e}", extra={"correlation_id": email.id})
        raise  # Retry via queue
```

#### 5. Merge & Deploy

```bash
# After PR approval
git checkout main
git pull origin main  # Get latest

# GitHub branch protection requires:
# ✅ All tests passing
# ✅ Code review approval
# ✅ No merge conflicts

# Merge via GitHub UI (squash and merge)
# CI/CD automatically deploys to staging

# Monitor staging deployment
az functionapp deployment list-publishing-profiles \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --slot staging

# After smoke tests pass, promote to production (manual approval gate)
```

---

## Code Quality Standards

### ❌ OLD: Arbitrary Line Limits (Don't Use)

```python
# OLD RULE - DEPRECATED
# Max 25 lines per function
```

**Why this was wrong:**
- Arbitrary metric doesn't measure true complexity
- Forces unnecessary extraction of single-use helpers
- Makes simple linear flows harder to understand
- Testing becomes harder (more mocking required)

---

### ✅ NEW: Complexity-Based Metrics

**Code Quality Metrics (Required):**

#### 1. Cyclomatic Complexity ≤10

**What it measures:** Number of independent paths through code (branches, loops)

```python
# Complexity = 1 (linear, no branches) ✅
def process_invoice(msg):
    email = parse_message(msg)
    vendor = lookup_vendor(email.sender)
    send_to_ap(email, vendor)
    return vendor

# Complexity = 5 (4 conditions + 1) ⚠️
def categorize_vendor(vendor):
    if vendor.gl_code.startswith('6'):  # +1
        return 'IT'
    elif vendor.gl_code.startswith('7'):  # +1
        return 'Marketing'
    elif vendor.gl_code.startswith('8'):  # +1
        return 'Operations'
    else:  # +1
        return 'General'

# Refactor to reduce complexity ✅
DEPT_MAPPING = {
    '6': 'IT',
    '7': 'Marketing',
    '8': 'Operations'
}

def categorize_vendor(vendor):
    first_digit = vendor.gl_code[0]
    return DEPT_MAPPING.get(first_digit, 'General')
```

**Check complexity:**

```bash
# Show functions with complexity >10
radon cc src/ --min C

# Show all complexity scores
radon cc src/ -s

# Fail build if any function >10
radon cc src/ --total-average --max C
```

**Pre-commit hook:**

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: complexity-check
        name: Check Cyclomatic Complexity
        entry: radon cc src/ --min C
        language: system
        pass_filenames: false
        fail_fast: true
```

---

#### 2. Parameters per Function ≤3

**Why:** More than 3 parameters suggests function is doing too much or needs data object.

```python
# ❌ BAD: Too many parameters (7)
def send_invoice_email(
    to: str,
    subject: str,
    body: str,
    attachment_url: str,
    vendor_name: str,
    gl_code: str,
    transaction_id: str
):
    pass

# ✅ GOOD: Use data object (1 parameter)
@dataclass
class Invoice:
    to: str
    subject: str
    body: str
    attachment_url: str
    vendor_name: str
    gl_code: str
    transaction_id: str

def send_invoice_email(invoice: Invoice):
    pass

# ✅ GOOD: Split responsibilities (2 parameters)
def send_email(message: EmailMessage):
    """Send email via Graph API."""
    pass

def create_invoice_email(invoice: Invoice) -> EmailMessage:
    """Compose email from invoice data."""
    return EmailMessage(
        to=invoice.to,
        subject=f"Invoice: {invoice.vendor_name} - GL {invoice.gl_code}",
        body=render_template(invoice),
        attachments=[invoice.attachment_url]
    )
```

---

#### 3. Nesting Depth ≤3 Levels

**Why:** Deep nesting is hard to test and understand.

```python
# ❌ BAD: 4 levels of nesting
def process_invoice(msg):
    if msg:  # Level 1
        email = parse_message(msg)
        if email.has_attachment:  # Level 2
            vendor = extract_vendor(email)
            if vendor:  # Level 3
                enrichment = lookup_enrichment(vendor)
                if enrichment:  # Level 4 - TOO DEEP
                    send_to_ap(email, enrichment)

# ✅ GOOD: Early returns, guard clauses
def process_invoice(msg):
    if not msg:
        return

    email = parse_message(msg)
    if not email.has_attachment:
        logger.warning("Email has no attachment", extra={"email_id": email.id})
        return

    vendor = extract_vendor(email)
    if not vendor:
        handle_unknown_vendor(email)
        return

    enrichment = lookup_enrichment(vendor)
    send_to_ap(email, enrichment)
```

---

#### 4. Extract on Reuse (Not Proactively)

**Principle:** Don't create helper functions until you have 2+ callers.

```python
# ❌ BAD: Extracting too early (single use)
def process_invoice(msg):
    email = parse_message(msg)
    vendor_key = get_vendor_key(email)  # Only called here
    vendor = lookup_vendor(vendor_key)
    send_to_ap(email, vendor)

def get_vendor_key(email):
    """Extract vendor key from email."""  # Single use
    return email.sender.split('@')[1].lower().replace('.', '_')

# ✅ GOOD: Inline until second use
def process_invoice(msg):
    email = parse_message(msg)
    vendor_key = email.sender.split('@')[1].lower().replace('.', '_')
    vendor = lookup_vendor(vendor_key)
    send_to_ap(email, vendor)

# ✅ GOOD: Extract when second caller appears
def process_invoice(msg):
    email = parse_message(msg)
    vendor_key = normalize_vendor_key(email.sender)  # Now used in 2+ places
    vendor = lookup_vendor(vendor_key)
    send_to_ap(email, vendor)

def handle_unknown_vendor(email):
    vendor_key = normalize_vendor_key(email.sender)  # Second caller
    notify_admin(f"Unknown vendor: {vendor_key}")
```

---

### Function Design Checklist

**Before committing a function, verify:**

- [ ] Cyclomatic complexity ≤10 (`radon cc`)
- [ ] Parameters ≤3 (or uses data object)
- [ ] Nesting depth ≤3 levels
- [ ] Single responsibility (does one thing)
- [ ] Type hints on all parameters and return
- [ ] Docstring explains purpose (not implementation)
- [ ] Error handling on external calls (API, database, file I/O)
- [ ] Logging includes correlation ID

---

## Testing Requirements

### Test Coverage Standards

**Minimum:** 60% overall coverage (enforced in CI/CD)
**Target:** 90%+ coverage for business logic
**Current:** 96% (98 tests passing)

```bash
# Run tests with coverage report
pytest --cov=functions --cov=shared --cov-report=html

# Fail build if coverage <60%
pytest --cov=functions --cov=shared --cov-fail-under=60

# View HTML report
open htmlcov/index.html
```

---

### Test Structure

**Unit Tests (Fast, Isolated):**

```python
# tests/unit/test_vendor_lookup.py
import pytest
from shared.vendor_lookup import normalize_vendor_key, lookup_vendor
from azure.core.exceptions import ResourceNotFoundError

def test_normalize_vendor_key_lowercase():
    """Vendor keys should be lowercase."""
    assert normalize_vendor_key("Billing@Adobe.com") == "adobe_com"

def test_normalize_vendor_key_replace_dots():
    """Dots should be replaced with underscores."""
    assert normalize_vendor_key("invoices@aws.amazon.com") == "aws_amazon_com"

@pytest.mark.parametrize("email,expected", [
    ("billing@adobe.com", "adobe_com"),
    ("invoices@stripe.com", "stripe_com"),
    ("noreply@github.com", "github_com"),
])
def test_normalize_vendor_key_examples(email, expected):
    """Test multiple vendor key normalizations."""
    assert normalize_vendor_key(email) == expected

def test_lookup_vendor_found(mock_table_client):
    """Vendor lookup should return entity when found."""
    mock_table_client.get_entity.return_value = {
        'VendorName': 'Adobe Inc',
        'GLCode': '6100',
        'ExpenseDept': 'IT'
    }

    vendor = lookup_vendor('adobe_com')

    assert vendor.vendor_name == 'Adobe Inc'
    assert vendor.gl_code == '6100'
    mock_table_client.get_entity.assert_called_once_with('Vendor', 'adobe_com')

def test_lookup_vendor_not_found(mock_table_client):
    """Vendor lookup should return None when not found."""
    mock_table_client.get_entity.side_effect = ResourceNotFoundError

    vendor = lookup_vendor('unknown_com')

    assert vendor is None
```

**Integration Tests (Slower, Real Dependencies):**

```python
# tests/integration/test_end_to_end.py
import pytest
from azure.storage.queue import QueueClient
from azure.data.tables import TableServiceClient

@pytest.mark.integration
def test_invoice_processing_end_to_end(azurite_storage):
    """Test complete pipeline from email to notification."""
    # 1. Seed vendor data
    table_client = azurite_storage.get_table_client('VendorMaster')
    table_client.create_entity({
        'PartitionKey': 'Vendor',
        'RowKey': 'adobe_com',
        'VendorName': 'Adobe Inc',
        'GLCode': '6100',
        'ExpenseDept': 'IT'
    })

    # 2. Queue raw email
    queue_client = azurite_storage.get_queue_client('raw-mail')
    queue_client.send_message(json.dumps({
        'id': '01JCK3Q7H8ZVXN3BARC9GWAEZM',
        'sender': 'billing@adobe.com',
        'subject': 'Invoice #12345',
        'blob_url': 'https://test.blob/invoice.pdf',
        'received_at': '2024-11-09T14:00:00Z'
    }))

    # 3. Trigger ExtractEnrich function
    # (Simulated or via Functions runtime)

    # 4. Verify enriched message in to-post queue
    to_post_queue = azurite_storage.get_queue_client('to-post')
    messages = to_post_queue.receive_messages()
    msg = next(messages)

    enriched = json.loads(msg.content)
    assert enriched['vendor_name'] == 'Adobe Inc'
    assert enriched['gl_code'] == '6100'
    assert enriched['expense_dept'] == 'IT'

    # 5. Verify transaction logged
    txn_table = azurite_storage.get_table_client('InvoiceTransactions')
    txn = txn_table.get_entity('202411', '01JCK3Q7H8ZVXN3BARC9GWAEZM')
    assert txn['Status'] == 'processed'
```

---

### Test Fixtures (DRY Principle)

```python
# tests/conftest.py
import pytest
from unittest.mock import MagicMock
from azure.data.tables import TableClient

@pytest.fixture
def mock_table_client():
    """Mock Azure Table Storage client."""
    client = MagicMock(spec=TableClient)
    return client

@pytest.fixture
def sample_raw_mail():
    """Sample RawMail message for testing."""
    return {
        'id': '01JCK3Q7H8ZVXN3BARC9GWAEZM',
        'sender': 'billing@adobe.com',
        'subject': 'Invoice #12345 - November 2024',
        'blob_url': 'https://storage.blob/invoices/raw/invoice123.pdf',
        'received_at': '2024-11-09T14:00:00Z',
        'attachment_count': 1
    }

@pytest.fixture
def sample_vendor():
    """Sample VendorMaster entity for testing."""
    return {
        'PartitionKey': 'Vendor',
        'RowKey': 'adobe_com',
        'VendorName': 'Adobe Inc',
        'ExpenseDept': 'IT',
        'GLCode': '6100',
        'AllocationScheduleNumber': 'MONTHLY',
        'BillingParty': 'Company HQ'
    }
```

---

### Testing Best Practices

**DO:**
- ✅ Test business logic (vendor lookup, enrichment, routing)
- ✅ Test error handling (unknown vendor, Graph API failures)
- ✅ Test edge cases (empty email, malformed JSON, missing attachment)
- ✅ Use descriptive test names (`test_vendor_lookup_returns_none_when_not_found`)
- ✅ Mock external dependencies (Graph API, Table Storage)
- ✅ Use fixtures for common test data

**DON'T:**
- ❌ Test framework code (Azure Functions runtime, Pydantic validation)
- ❌ Test third-party libraries (MSAL, Azure SDK)
- ❌ Write tests that depend on external services (use mocks)
- ❌ Write tests that require specific execution order

---

## Git Workflow

### Conventional Commits (Required)

**Format:**

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code change without feature/bug change
- `docs`: Documentation only
- `test`: Tests only
- `chore`: Dependency updates, tooling
- `perf`: Performance improvement
- `ci`: CI/CD changes

**Scopes:**
- `extract`: ExtractEnrich function
- `post`: PostToAP function
- `notify`: Notify function
- `webhook`: MailWebhook function
- `infra`: Infrastructure (Bicep)
- `shared`: Shared utilities

**Examples:**

```bash
# Feature
git commit -m "feat(extract): add PDF text extraction using PyPDF2

Added PDF parsing as fallback when email sender is generic.
Uses PyPDF2 to extract text and regex to find vendor name.

Closes #42"

# Bug fix
git commit -m "fix(post): handle Graph API throttling errors

Added exponential backoff retry logic for 429 status codes.
Honors Retry-After header from Graph API response.

Fixes #58"

# Refactor
git commit -m "refactor(shared): extract vendor normalization to shared utility

Moved normalize_vendor_key from ExtractEnrich to shared/vendors.py
for reuse in AddVendor function."

# Documentation
git commit -m "docs: update deployment guide with staging slot sync

Added section on syncing app settings from production to staging
after Bicep deployment. Includes sync-staging-settings.sh script.

Closes #64"

# Breaking change
git commit -m "feat(extract)!: change VendorMaster table schema

BREAKING CHANGE: VendorMaster RowKey now uses email domain
instead of vendor name. Requires data migration script.

Migration: python scripts/migrate_vendor_keys.py

Closes #72"
```

**Why Conventional Commits:**
- Automated changelog generation (`git-cliff`, `standard-version`)
- Semantic versioning automation
- Clear commit history for code review
- Easy to filter commits by type (`git log --grep="^feat"`)

**Official Reference:**
- [Conventional Commits Specification](https://www.conventionalcommits.org/)

---

### Branch Protection Rules

**Main Branch (Protected):**

- ✅ Require pull request before merging
- ✅ Require approvals: 1
- ✅ Dismiss stale reviews when new commits pushed
- ✅ Require status checks to pass:
  - `test` (pytest with 60% coverage)
  - `lint` (black, flake8, mypy, bandit)
  - `complexity` (radon cc)
  - `infrastructure-validate` (Bicep validation)
- ✅ Require branches to be up to date
- ✅ No force pushes
- ✅ No deletions

---

### Git Hooks (Pre-Commit)

**Install pre-commit framework:**

```bash
pip install pre-commit
pre-commit install
```

**Configuration (`.pre-commit-config.yaml`):**

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.11.0
    hooks:
      - id: black
        language_version: python3.11

  - repo: https://github.com/pycqa/flake8
    rev: 6.1.0
    hooks:
      - id: flake8
        args: [--config=.flake8]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.0
    hooks:
      - id: mypy
        args: [--strict, --ignore-missing-imports]
        additional_dependencies: [types-requests]

  - repo: local
    hooks:
      - id: complexity-check
        name: Check Cyclomatic Complexity
        entry: radon cc src/ --min C
        language: system
        pass_filenames: false

      - id: pytest
        name: Run pytest
        entry: pytest
        args: [--cov=functions, --cov=shared, --cov-fail-under=60, -q]
        language: system
        pass_filenames: false

      - id: no-secrets
        name: Check for secrets
        entry: bash -c 'git diff --cached --name-only | xargs grep -E "(password|secret|api[_-]?key|token)" && exit 1 || exit 0'
        language: system
```

---

## Infrastructure Development

### Bicep Development Workflow

#### 1. Validate Templates

```bash
# Build Bicep to ARM (validates syntax)
az bicep build --file infrastructure/bicep/main.bicep

# Validate deployment (checks resources, RBAC, etc.)
az deployment group validate \
  --resource-group rg-invoice-agent-dev \
  --template-file infrastructure/bicep/main.bicep \
  --parameters infrastructure/parameters/dev.json
```

#### 2. What-If Analysis (Preview Changes)

```bash
# See what would change (dry-run)
az deployment group what-if \
  --resource-group rg-invoice-agent-dev \
  --template-file infrastructure/bicep/main.bicep \
  --parameters infrastructure/parameters/dev.json

# Output shows:
# + Resource will be created
# ~ Resource will be modified
# - Resource will be deleted
# = Resource unchanged
```

#### 3. Deploy Infrastructure

```bash
# Deploy to development
az deployment group create \
  --resource-group rg-invoice-agent-dev \
  --template-file infrastructure/bicep/main.bicep \
  --parameters infrastructure/parameters/dev.json

# Deploy to production (with confirmation)
az deployment group create \
  --resource-group rg-invoice-agent-prod \
  --template-file infrastructure/bicep/main.bicep \
  --parameters infrastructure/parameters/prod.json \
  --confirm-with-what-if
```

---

### Infrastructure Testing (NEW)

**Problem Solved:** Staging slot configuration drift caused deployment failures.

**Solution:** Automated infrastructure tests catch drift before production.

#### 1. Pre-Deployment Tests (Bicep Validation)

```bash
# tests/infrastructure/test_bicep_validation.sh
#!/bin/bash
set -e

echo "🔍 Validating Bicep templates..."

# Build all templates (syntax check)
for bicep_file in infrastructure/bicep/**/*.bicep; do
  echo "Building $bicep_file..."
  az bicep build --file "$bicep_file"
done

# Validate against dev environment
echo "Validating dev deployment..."
az deployment group validate \
  --resource-group rg-invoice-agent-dev \
  --template-file infrastructure/bicep/main.bicep \
  --parameters infrastructure/parameters/dev.json

echo "✅ Bicep validation passed"
```

#### 2. Post-Deployment Tests (Python)

```python
# tests/infrastructure/test_deployment.py
import pytest
from azure.identity import DefaultAzureCredential
from azure.mgmt.web import WebSiteManagementClient
from azure.mgmt.storage import StorageManagementClient

@pytest.fixture
def web_client():
    credential = DefaultAzureCredential()
    return WebSiteManagementClient(credential, SUBSCRIPTION_ID)

def test_function_app_exists(web_client):
    """Verify Function App is deployed."""
    app = web_client.web_apps.get(RG_NAME, FUNCTION_APP_NAME)
    assert app is not None
    assert app.state == 'Running'

def test_staging_slot_exists(web_client):
    """Verify staging slot is configured."""
    slots = list(web_client.web_apps.list_slots(RG_NAME, FUNCTION_APP_NAME))
    slot_names = [slot.name.split('/')[-1] for slot in slots]
    assert 'staging' in slot_names

def test_app_settings_parity(web_client):
    """Verify staging and production have same critical settings."""
    prod_settings = web_client.web_apps.list_application_settings(
        RG_NAME, FUNCTION_APP_NAME
    ).properties

    staging_settings = web_client.web_apps.list_application_settings(
        RG_NAME, FUNCTION_APP_NAME, slot='staging'
    ).properties

    # Critical settings that must match
    critical_keys = [
        'FUNCTIONS_WORKER_RUNTIME',
        'GRAPH_TENANT_ID',
        'GRAPH_CLIENT_ID',
        'WEBSITE_RUN_FROM_PACKAGE'
    ]

    for key in critical_keys:
        assert prod_settings.get(key) == staging_settings.get(key), \
            f"Setting '{key}' differs between prod and staging"

def test_managed_identity_configured(web_client):
    """Verify Managed Identity is enabled."""
    app = web_client.web_apps.get(RG_NAME, FUNCTION_APP_NAME)
    assert app.identity is not None
    assert app.identity.type == 'SystemAssigned'

def test_rbac_roles_assigned():
    """Verify Managed Identity has required RBAC roles."""
    from azure.mgmt.authorization import AuthorizationManagementClient

    # Get function app identity
    app = web_client.web_apps.get(RG_NAME, FUNCTION_APP_NAME)
    principal_id = app.identity.principal_id

    # Get role assignments
    auth_client = AuthorizationManagementClient(credential, SUBSCRIPTION_ID)
    assignments = list(auth_client.role_assignments.list_for_scope(
        scope=f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RG_NAME}"
    ))

    # Filter to this principal
    principal_roles = [
        a for a in assignments if a.principal_id == principal_id
    ]

    # Check required roles
    required_roles = [
        'Storage Blob Data Contributor',
        'Storage Queue Data Contributor',
        'Storage Table Data Contributor'
    ]

    role_names = [get_role_name(a.role_definition_id) for a in principal_roles]

    for role in required_roles:
        assert role in role_names, f"Missing RBAC role: {role}"
```

#### 3. Configuration Sync Validation

```bash
# scripts/validate-staging-config.sh
#!/bin/bash
set -e

FUNCTION_APP="func-invoice-agent-prod"
RG="rg-invoice-agent-prod"

echo "🔍 Validating staging slot configuration..."

# Get production settings
prod_settings=$(az functionapp config appsettings list \
  --name $FUNCTION_APP \
  --resource-group $RG \
  --output json)

# Get staging settings
staging_settings=$(az functionapp config appsettings list \
  --name $FUNCTION_APP \
  --resource-group $RG \
  --slot staging \
  --output json)

# Compare critical settings
critical_keys=("FUNCTIONS_WORKER_RUNTIME" "GRAPH_TENANT_ID" "WEBSITE_RUN_FROM_PACKAGE")

for key in "${critical_keys[@]}"; do
  prod_value=$(echo $prod_settings | jq -r ".[] | select(.name==\"$key\") | .value")
  staging_value=$(echo $staging_settings | jq -r ".[] | select(.name==\"$key\") | .value")

  if [ "$prod_value" != "$staging_value" ]; then
    echo "❌ MISMATCH: $key"
    echo "  Production: $prod_value"
    echo "  Staging:    $staging_value"
    exit 1
  fi
done

echo "✅ Staging configuration matches production"
```

**Run in CI/CD:**

```yaml
# .github/workflows/infrastructure.yml
jobs:
  infrastructure-test:
    runs-on: ubuntu-latest
    steps:
      - name: Validate Bicep
        run: ./tests/infrastructure/test_bicep_validation.sh

      - name: Deploy to Dev
        run: |
          az deployment group create \
            --resource-group rg-invoice-agent-dev \
            --template-file infrastructure/bicep/main.bicep \
            --parameters infrastructure/parameters/dev.json

      - name: Run Post-Deployment Tests
        run: pytest tests/infrastructure/ -v

      - name: Validate Staging Config
        run: ./scripts/validate-staging-config.sh
```

---

## Deployment Procedures

### Deployment Pattern: Blue-Green via Staging Slots

**Goal:** Zero-downtime deployments with instant rollback

```
Code → Test → Build → Deploy to Staging → Smoke Tests → Swap Slots → Production
```

---

### Step-by-Step Deployment

#### 1. Pre-Deployment Checks

```bash
# Ensure all tests pass locally
make test

# Ensure code quality passes
make lint

# Ensure complexity within limits
make complexity

# Ensure infrastructure valid
make infra-validate
```

#### 2. Deploy to Staging Slot

```bash
# Build and package functions
cd src
func pack --output ../artifacts/invoice-agent.zip

# Deploy to staging slot
func azure functionapp publish func-invoice-agent-prod \
  --slot staging \
  --python

# Wait for deployment to complete
az functionapp deployment list-publishing-profiles \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --slot staging
```

#### 3. Sync App Settings (Critical)

```bash
# Run configuration sync script
./scripts/sync-staging-settings.sh

# Verify parity
./scripts/validate-staging-config.sh
```

#### 4. Run Smoke Tests

```bash
# Test staging slot endpoints
pytest tests/smoke/ --env staging -v

# Example smoke tests:
# - GET /api/health → 200 OK
# - POST /api/AddVendor → 201 Created
# - Verify queue connectivity
# - Verify Table Storage access
```

#### 5. Swap Slots (Production Deployment)

```bash
# Swap staging → production (zero downtime)
az functionapp deployment slot swap \
  --resource-group rg-invoice-agent-prod \
  --name func-invoice-agent-prod \
  --slot staging \
  --target-slot production

# Monitor swap progress
az functionapp deployment slot list \
  --resource-group rg-invoice-agent-prod \
  --name func-invoice-agent-prod
```

#### 6. Verify Production

```bash
# Check production health
curl -f https://func-invoice-agent-prod.azurewebsites.net/api/health

# Monitor Application Insights
az monitor app-insights metrics show \
  --app func-invoice-agent-prod \
  --metric "requests/count" \
  --interval PT1M

# Check function logs
az functionapp log tail \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod
```

#### 7. Rollback (If Needed)

```bash
# Swap back to previous version (instant rollback)
az functionapp deployment slot swap \
  --resource-group rg-invoice-agent-prod \
  --name func-invoice-agent-prod \
  --slot production \
  --target-slot staging

# Previous version is now in production
# Broken version is now in staging
```

---

### Deployment Automation (GitHub Actions)

**See CI/CD section in [SPEC.md](SPEC.md#cicd-pipeline-enhanced) for complete workflow**

---

## Common Tasks & Skills

### Skill 1: Adding a New Vendor

```bash
# Option 1: Via HTTP endpoint (programmatic)
curl -X POST https://func-invoice-agent-prod.azurewebsites.net/api/AddVendor \
  -H "Content-Type: application/json" \
  -d '{
    "email_domain": "newvendor.com",
    "vendor_name": "New Vendor Inc",
    "expense_dept": "Marketing",
    "gl_code": "7200",
    "allocation_schedule": "MONTHLY",
    "billing_party": "Company HQ"
  }'

# Option 2: Via Azure Portal (manual)
# 1. Navigate to Storage Account → Tables → VendorMaster
# 2. Add Entity:
#    PartitionKey: Vendor
#    RowKey: newvendor_com
#    VendorName: New Vendor Inc
#    ExpenseDept: Marketing
#    GLCode: 7200
#    AllocationScheduleNumber: MONTHLY
#    BillingParty: Company HQ

# Option 3: Via Python script (bulk import)
python infrastructure/scripts/seed_vendors.py --file data/vendors.csv --env prod
```

---

### Skill 2: Debugging Failed Invoices

```bash
# 1. Check Application Insights for errors
az monitor app-insights query \
  --app func-invoice-agent-prod \
  --analytics-query "
    traces
    | where severityLevel >= 3
    | where timestamp > ago(1h)
    | project timestamp, message, customDimensions
    | order by timestamp desc
  "

# 2. Check poison queue for failed messages
az storage queue peek \
  --name raw-mail-poison \
  --account-name stginvoiceagentprod \
  --auth-mode login

# 3. Get specific transaction details
az storage table query \
  --account-name stginvoiceagentprod \
  --table-name InvoiceTransactions \
  --filter "RowKey eq '01JCK3Q7H8ZVXN3BARC9GWAEZM'" \
  --auth-mode login

# 4. Replay failed message (after fixing issue)
# Get message from poison queue
message=$(az storage queue peek --name raw-mail-poison --account-name stginvoiceagentprod --auth-mode login)

# Requeue to raw-mail
az storage queue put \
  --name raw-mail \
  --account-name stginvoiceagentprod \
  --message "$message" \
  --auth-mode login
```

---

### Skill 3: Monitoring System Health

```bash
# Check queue depths
az storage queue list \
  --account-name stginvoiceagentprod \
  --auth-mode login \
  --query "[].{name:name, messageCount:approximateMessageCount}"

# Check function execution count (last hour)
az monitor app-insights metrics show \
  --app func-invoice-agent-prod \
  --metric "performanceCounters/executionCount" \
  --start-time $(date -u -d '1 hour ago' +"%Y-%m-%dT%H:%M:%SZ") \
  --end-time $(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Check error rate
az monitor app-insights query \
  --app func-invoice-agent-prod \
  --analytics-query "
    requests
    | where timestamp > ago(1h)
    | summarize
        Total = count(),
        Errors = countif(success == false),
        ErrorRate = todouble(countif(success == false)) / count() * 100
  "

# Check vendor match rate (custom metric)
az monitor app-insights query \
  --app func-invoice-agent-prod \
  --analytics-query "
    customMetrics
    | where name == 'vendor_matches'
    | where timestamp > ago(24h)
    | summarize
        Total = sum(value),
        Found = sumif(value, customDimensions.found == 'true')
    | extend MatchRate = (Found / Total) * 100
  "
```

---

### Skill 4: Local Development Setup

```bash
# 1. Clone repository
git clone https://github.com/your-org/invoice-agent.git
cd invoice-agent

# 2. Install dependencies
make setup

# Equivalent to:
# cd src
# python -m venv venv
# source venv/bin/activate
# pip install -r requirements.txt

# 3. Configure local settings
cp src/local.settings.json.template src/local.settings.json
# Edit local.settings.json with Azure credentials

# 4. Start Azurite (local Azure Storage emulator)
docker run -d -p 10000:10000 -p 10001:10001 -p 10002:10002 \
  --name azurite \
  mcr.microsoft.com/azure-storage/azurite

# 5. Create local tables and queues
python scripts/setup-local.sh

# 6. Run functions locally
cd src
func start

# Functions available at:
# http://localhost:7071/api/MailWebhook
# http://localhost:7071/api/AddVendor
```

---

### Skill 5: Renewing Graph API Subscription Manually

```bash
# If SubscriptionManager fails, manually renew:

# 1. Get current subscription ID
az storage table query \
  --account-name stginvoiceagentprod \
  --table-name GraphSubscriptions \
  --filter "IsActive eq true" \
  --auth-mode login

# 2. Get access token
TOKEN=$(az account get-access-token --resource https://graph.microsoft.com --query accessToken -o tsv)

# 3. Renew subscription
curl -X PATCH https://graph.microsoft.com/v1.0/subscriptions/{subscription-id} \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "expirationDateTime": "2024-12-01T00:00:00Z"
  }'

# 4. Update GraphSubscriptions table
az storage table entity update \
  --account-name stginvoiceagentprod \
  --table-name GraphSubscriptions \
  --partition-key GraphSubscription \
  --row-key {subscription-id} \
  --entity ExpirationDateTime="2024-12-01T00:00:00Z" \
  --auth-mode login
```

---

## Troubleshooting Guide

### Common Issues

#### Issue 1: Staging Slot Settings Out of Sync

**Symptoms:**
- Functions fail in staging with "undefined" errors
- Environment variables not found

**Solution:**

```bash
# Sync production settings to staging
./scripts/sync-staging-settings.sh

# Restart staging slot
az functionapp restart \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --slot staging
```

**Prevention:** Run `sync-staging-settings.sh` after every Bicep deployment

---

#### Issue 2: High Cyclomatic Complexity

**Symptoms:**
- `radon cc` shows functions with complexity >10
- CI/CD fails on complexity check

**Solution:**

```python
# Before: Complexity = 12 (too high)
def categorize_invoice(invoice):
    if invoice.gl_code.startswith('6'):
        if invoice.amount > 10000:
            return 'high-value-it'
        elif invoice.amount > 1000:
            return 'medium-value-it'
        else:
            return 'low-value-it'
    elif invoice.gl_code.startswith('7'):
        if invoice.amount > 5000:
            return 'high-value-marketing'
        else:
            return 'low-value-marketing'
    # ... more branches

# After: Complexity = 2 (good)
CATEGORY_RULES = [
    (lambda i: i.gl_code.startswith('6') and i.amount > 10000, 'high-value-it'),
    (lambda i: i.gl_code.startswith('6') and i.amount > 1000, 'medium-value-it'),
    (lambda i: i.gl_code.startswith('6'), 'low-value-it'),
    (lambda i: i.gl_code.startswith('7') and i.amount > 5000, 'high-value-marketing'),
    (lambda i: i.gl_code.startswith('7'), 'low-value-marketing'),
]

def categorize_invoice(invoice):
    for condition, category in CATEGORY_RULES:
        if condition(invoice):
            return category
    return 'uncategorized'
```

---

#### Issue 3: Test Coverage Drop

**Symptoms:**
- `pytest --cov-fail-under=60` fails
- CI/CD fails on coverage check

**Solution:**

```bash
# 1. Identify uncovered code
pytest --cov=functions --cov=shared --cov-report=html
open htmlcov/index.html

# 2. Add tests for uncovered functions
# Example: shared/pdf_extractor.py at 40% coverage

# 3. Write tests
# tests/unit/test_pdf_extractor.py
def test_extract_text_from_pdf():
    """Test PDF text extraction."""
    # Add test

# 4. Verify coverage increased
pytest --cov=shared.pdf_extractor --cov-report=term-missing
```

---

## Official References

### Development Tools
- [Azure Functions Python Guide](https://learn.microsoft.com/en-us/azure/azure-functions/functions-reference-python)
- [Pytest Documentation](https://docs.pytest.org/)
- [Radon (Complexity)](https://radon.readthedocs.io/)
- [Black (Formatter)](https://black.readthedocs.io/)
- [mypy (Type Checking)](https://mypy.readthedocs.io/)

### Standards
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Semantic Versioning](https://semver.org/)
- [Python Type Hints (PEP 484)](https://peps.python.org/pep-0484/)

### Azure Resources
- [Azure Functions Core Tools](https://learn.microsoft.com/en-us/azure/azure-functions/functions-run-local)
- [Azure CLI Reference](https://learn.microsoft.com/en-us/cli/azure/)
- [Bicep Documentation](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/)

---

**Version:** 2.0 (Lessons Learned Edition)
**Last Updated:** 2024-11-23
**Maintained By:** Engineering Team
**Replaces:** `CLAUDE.md` (root)
