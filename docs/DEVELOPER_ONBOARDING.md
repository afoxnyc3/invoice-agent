# Developer Onboarding Guide

**Last Updated:** November 13, 2025

Welcome to the Invoice Agent team! This guide will get you productive within 2 hours. Follow each section in order.

## Quick Overview (5 minutes)

**What is Invoice Agent?**
- Automated email-to-AP system using Azure Functions
- Processes 100-200 invoices daily
- Matches vendor emails to GL codes and routes to accounting
- Built with Python 3.11, Azure Functions, Table Storage, Pydantic

**Tech Stack:**
- Backend: Python 3.11, Azure Functions (Serverless)
- Storage: Azure Table Storage, Blob Storage
- Integration: Microsoft Graph API (email), Teams webhooks
- Testing: pytest, coverage, mypy
- Deployment: GitHub Actions, Bicep IaC

**Key Features:**
- Email polling every 5 minutes
- Vendor enrichment with GL codes
- AP email routing
- Teams notifications
- Simple HTTP API for vendor management

**Where You'll Work:**
- `src/functions/` - Function code
- `src/shared/` - Shared utilities
- `tests/` - Test suite
- `docs/` - Documentation
- `infrastructure/` - Bicep templates

---

## Prerequisites (15 minutes)

### 1. Install Required Tools

**macOS:**
```bash
# Python 3.11+
brew install python@3.11

# Docker (for local Azure storage emulator)
brew install docker  # or download Docker Desktop

# Azure CLI (for deployments)
brew install azure-cli

# Verify installations
python3 --version        # Should be 3.11+
docker --version         # Should be 20.10+
az --version             # Should be 2.50+
```

**Windows:**
- Python: https://www.python.org/downloads/ (select 3.11+)
- Docker: https://www.docker.com/products/docker-desktop
- Azure CLI: https://learn.microsoft.com/cli/azure/install-azure-cli-windows

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install python3.11 docker.io azure-cli
```

### 2. Create GitHub Account & Get Access

- [ ] Create GitHub account (if new)
- [ ] Ask tech lead to add you to organization
- [ ] Clone the repository:
  ```bash
  git clone https://github.com/your-org/invoice-agent.git
  cd invoice-agent
  ```

### 3. Azure Access

- [ ] Request Azure subscription access (if needed for testing)
- [ ] Get added to resource groups:
  - `rg-invoice-agent-dev` (development)
  - `rg-invoice-agent-prod` (production, read-only initially)

**Verify Access:**
```bash
az login
az account show  # Confirm subscription
az functionapp list --resource-group rg-invoice-agent-dev
```

---

## Local Environment Setup (20 minutes)

### Step 1: Run Setup Script

The setup script automates everything - virtual environment, dependencies, local storage, vendor data.

```bash
cd /path/to/invoice-agent

# Run the automated setup
./scripts/setup-local.sh

# This does:
# - Creates Python virtual environment
# - Installs dependencies from requirements.txt
# - Starts Azurite (local Azure storage emulator)
# - Creates tables: VendorMaster, InvoiceTransactions
# - Creates queues: raw-mail, to-post, notify (+ poison queues)
# - Seeds 25 sample vendors for testing
# - Creates local.settings.json from template
# - Installs pre-commit hooks
```

### Step 2: Activate Virtual Environment

```bash
# macOS/Linux
source src/venv/bin/activate

# Windows
src\venv\Scripts\activate

# Verify activation (you should see (venv) in prompt)
python --version
```

### Step 3: Verify Setup

```bash
# Check Docker container is running
docker ps | grep azurite
# Should show: mcr.microsoft.com/azure-storage/azurite

# Check Python dependencies
pip list | grep azure
# Should show: azure-functions, azure-data-tables, etc.

# Check local.settings.json exists
ls src/local.settings.json
# Should exist and contain storage connection strings
```

---

## Running Functions Locally (10 minutes)

### Start the Functions

```bash
# Activate venv first
source src/venv/bin/activate

# Navigate to src and start functions
cd src
func start

# Expected output:
# Azure Functions Core Tools ... (version 4.x)
# ...
# MailIngest: timerTrigger
# ExtractEnrich: queueTrigger
# PostToAP: queueTrigger
# Notify: queueTrigger
# AddVendor: httpTrigger
```

Functions are now running locally on `http://localhost:7071`

### Test AddVendor Endpoint

```bash
# In a new terminal (keep func start running)
curl -X POST http://localhost:7071/api/AddVendor \
  -H "Content-Type: application/json" \
  -d '{
    "vendor_name": "Test Vendor",
    "vendor_domain": "test.example.com",
    "expense_dept": "IT",
    "gl_code": "6100",
    "allocation_schedule": "MONTHLY",
    "billing_party": "Company HQ"
  }'

# Expected response:
# {"status":"success","vendor":"Test Vendor"}
```

---

## Understanding the Code Structure (20 minutes)

### Key Directories

```
invoice-agent/
├── src/functions/
│   ├── MailIngest/       # Email polling (timer trigger)
│   ├── ExtractEnrich/    # Vendor matching (queue trigger)
│   ├── PostToAP/         # AP email send (queue trigger)
│   ├── Notify/           # Teams webhook (queue trigger)
│   └── AddVendor/        # Vendor CRUD API (HTTP trigger)
│
├── src/shared/
│   ├── models.py         # Pydantic data models
│   ├── logger.py         # Structured logging
│   ├── retry.py          # Exponential backoff
│   ├── graph_api.py      # Microsoft Graph client
│   └── helpers.py        # Utility functions
│
├── tests/
│   ├── unit/             # Fast unit tests
│   ├── integration/      # Queue/storage tests
│   └── fixtures/         # Test data & mocks
│
└── docs/
    ├── ARCHITECTURE.md   # System design
    ├── LOCAL_DEVELOPMENT.md
    └── operations/       # Runbooks & playbooks
```

### Understanding a Function (MailIngest)

```python
# src/functions/MailIngest/__init__.py
import azure.functions as func
from shared.graph_api import get_messages  # Microsoft Graph
from shared.models import RawMail          # Data validation
from azure.storage.queue import QueueClient  # Queue API

def main(myTimer: func.TimerRequest):
    """Timer-triggered function that runs every 5 minutes."""

    # 1. Get unread emails from shared mailbox
    messages = get_messages(client)

    # 2. For each message, save attachment to blob storage
    # 3. Create RawMail model with email + blob URL
    # 4. Put RawMail message in queue for next function
    # 5. Mark email as read
```

**Flow Through System:**
```
MailIngest (email) → RawMail queue → ExtractEnrich (vendor match)
                                      ↓
                                    to-post queue → PostToAP (send)
                                                     ↓
                                                   notify queue → Notify (Teams)
```

---

## Running Tests (15 minutes)

### Unit Tests (Fast)

```bash
# From repo root, with venv activated
make test

# Or manually:
export PYTHONPATH=./src
pytest tests/unit -v

# Expected: All tests pass, >60% coverage
```

### Integration Tests (Requires Azurite)

```bash
# Azurite should be running from setup script
pytest tests/integration -v -m integration

# These test actual queue/storage interactions
```

### Check Code Quality

```bash
# Format check (Black)
make lint

# Type checking (mypy)
mypy src/functions src/shared --strict

# Security scan (Bandit)
bandit -r src/functions src/shared
```

---

## Making Your First Change (30 minutes)

### Task: Add a New Vendor Field

**Goal:** Add "contact_email" field to vendors (example change)

### Step 1: Create Feature Branch

```bash
git checkout -b feature/issue-XX-add-contact-field
# Replace XX with actual issue number
```

### Step 2: Update Data Model

Edit `src/shared/models.py`:

```python
class VendorMaster(BaseModel):
    # ... existing fields ...
    ContactEmail: str = Field(..., description="Vendor contact email")

    @validator("ContactEmail")
    def validate_email(cls, v):
        if "@" not in v:
            raise ValueError("ContactEmail must be valid email")
        return v
```

### Step 3: Update AddVendor Function

Edit `src/functions/AddVendor/__init__.py`:

```python
vendor_data = {
    # ... existing fields ...
    "ContactEmail": data.get("contact_email"),
}
```

### Step 4: Write Tests

Create test in `tests/unit/test_models.py`:

```python
def test_vendor_with_contact_email():
    vendor = VendorMaster(
        RowKey="test_com",
        VendorName="Test Inc",
        ContactEmail="contact@test.com",
        # ... required fields ...
    )
    assert vendor.ContactEmail == "contact@test.com"

def test_vendor_invalid_email():
    with pytest.raises(ValidationError):
        VendorMaster(
            ContactEmail="invalid-email",
            # ... other fields ...
        )
```

### Step 5: Run Tests

```bash
pytest tests/unit/test_models.py -v

# Should pass both tests
```

### Step 6: Commit & Push

```bash
git add .
git commit -m "feat: add contact_email field to VendorMaster

- Add ContactEmail field to vendor model
- Update AddVendor endpoint to accept contact_email
- Add email validation
- Add unit tests for validation"

git push -u origin feature/issue-XX-add-contact-field
```

### Step 7: Create Pull Request

Go to GitHub and create PR from your branch to `main`

---

## Key Code Patterns

### Pattern 1: Error Handling

```python
from shared.retry import retry_with_backoff

@retry_with_backoff(max_retries=3, backoff_factor=2)
def call_external_api():
    # Retries 3x with exponential backoff (1s, 2s, 4s)
    response = requests.get(url)
    if response.status_code >= 400:
        raise Exception(f"API error: {response.status_code}")
    return response.json()
```

### Pattern 2: Data Validation

```python
from shared.models import RawMail

def process_message(msg_str):
    # Parse and validate with Pydantic
    data = json.loads(msg_str)

    try:
        raw_mail = RawMail(**data)  # Validates schema
    except ValidationError as e:
        logger.error(f"Invalid message: {e}")
        raise

    # Now safe to use: raw_mail.sender, raw_mail.blob_url, etc.
```

### Pattern 3: Logging

```python
from shared.logger import get_logger

logger = get_logger(__name__)

def process_invoice(transaction_id):
    logger.info(f"Processing invoice: {transaction_id}")

    try:
        # ... work ...
        logger.info(f"Successfully processed: {transaction_id}")
    except Exception as e:
        logger.error(f"Failed to process {transaction_id}: {str(e)}")
        raise
```

### Pattern 4: Queue Messages

```python
from azure.storage.queue import QueueClient
from shared.models import EnrichedInvoice
import json

# Put message in queue
def enqueue_invoice(invoice: EnrichedInvoice):
    client = QueueClient.from_connection_string(
        os.environ["AzureWebJobsStorage"],
        "to-post"
    )
    client.send_message(invoice.model_dump_json())

# Get message from queue
def dequeue_invoice(msg: func.QueueMessage):
    invoice = EnrichedInvoice(**json.loads(msg.get_body()))
    # Now use invoice.vendor_name, invoice.gl_code, etc.
```

---

## Architecture Overview (20 minutes read)

See [ARCHITECTURE.md](./ARCHITECTURE.md) for deep dive, but here's the summary:

**Design Principles:**
- Serverless (Azure Functions) for cost efficiency
- Queue-based decoupling for resilience
- Table Storage for simple, fast vendor lookups
- Managed Identity for secure authentication
- Simple Teams webhooks (not complex bots)

**Data Models (Pydantic):**
- `RawMail` - Email + blob URL (MailIngest → ExtractEnrich)
- `EnrichedInvoice` - Vendor + GL code (ExtractEnrich → PostToAP)
- `NotificationMessage` - Alert info (PostToAP → Notify)
- `VendorMaster` - Lookup table (used by ExtractEnrich)

**Error Strategy:**
- Transient errors: Retry 3x with backoff
- Business errors: Flag and continue
- Critical errors: Alert ops team

---

## Daily Development Workflow

### Start of Day

```bash
# 1. Update code from GitHub
git checkout main
git pull origin main

# 2. Create feature branch
git checkout -b feature/issue-XX-description

# 3. Activate venv
source src/venv/bin/activate

# 4. Start local functions (if needed)
cd src && func start
```

### During Development

```bash
# 1. Write tests first (TDD)
# 2. Implement code to make tests pass
# 3. Run all tests frequently
make test

# 4. Check code quality
make lint

# 5. Run just your changes
pytest tests/unit/test_your_file.py -v
```

### Before Committing

```bash
# 1. Run full test suite
make test

# 2. Run linting and type checks
make lint

# 3. Verify no hardcoded secrets
git diff | grep -i "password\|secret\|key"

# 4. Update docs if needed (inline comments, docstrings)

# 5. Commit with clear message
git commit -m "type: description

Detailed explanation of what changed and why."
```

### Create Pull Request

- Link to GitHub issue
- Describe what you changed
- Note any breaking changes
- Request review from tech lead

---

## Getting Help

### When You're Stuck

1. **Check existing docs first:**
   - [ARCHITECTURE.md](./ARCHITECTURE.md) - System design
   - [Troubleshooting Guide](./operations/TROUBLESHOOTING_GUIDE.md) - Common errors
   - [LOCAL_DEVELOPMENT.md](./LOCAL_DEVELOPMENT.md) - Local setup issues

2. **Search existing code:**
   ```bash
   # Find how other functions handle similar problems
   grep -r "ValidationError" src/functions/
   ```

3. **Check tests:**
   ```bash
   # Tests show how code is meant to be used
   grep -r "ExtractEnrich" tests/
   ```

4. **Ask the team:**
   - Slack: #invoice-agent-dev
   - Office hours: See team calendar

### Common Questions

**Q: How do I run a single function locally?**
```bash
func start --functions MailIngest
```

**Q: How do I test with real Azure instead of Azurite?**
- Update `local.settings.json` to use real storage account
- Be careful not to process real invoices!

**Q: How do I debug a function?**
```bash
# Add breakpoints in VS Code
# Install Debugger for Python extension
# Run with: func start --python
```

**Q: How do I add a new NPM/Python dependency?**
```bash
# Add to requirements.txt, then:
pip install -r requirements.txt

# Commit both requirements.txt and lock file
```

---

## Important Rules

### Code Quality

- **Max 25 lines per function** (helps readability, extract helpers)
- **Full type hints** - Use `str`, `int`, not just `Any`
- **All external calls must be try/except** - No silent failures
- **Pydantic validation** - All input data models validated
- **Logging required** - ERROR for failures, INFO for success

### Security

- **No hardcoded secrets** - Use env vars or Key Vault
- **No passwords in logs** - Mask sensitive data
- **HTTPS only** - All external APIs
- **Managed Identity** - Use for Azure services

### Testing

- **60% coverage minimum** - Run `pytest --cov`
- **Unit tests for all business logic** - Fast, isolated
- **Integration tests for flows** - Queue paths, storage
- **No mocking external services unless unavoidable**

### Git

- **Feature branches** - Always branch from main
- **Clear commit messages** - Describe what and why
- **No direct merges to main** - PRs required
- **Squash and merge** - Keep history clean

---

## Next Steps

1. **Today:**
   - [ ] Complete this onboarding
   - [ ] Run local setup
   - [ ] Make your first test change
   - [ ] Create a PR

2. **This Week:**
   - [ ] Complete first assigned issue
   - [ ] Review [ARCHITECTURE.md](./ARCHITECTURE.md)
   - [ ] Pair-program with senior dev
   - [ ] Deploy to dev environment

3. **This Month:**
   - [ ] Deploy to production (with review)
   - [ ] Become on-call backup
   - [ ] Review own code quality metrics
   - [ ] Take on mentoring tasks

---

## Team Contact Info

- **Tech Lead:** See GitHub team page
- **On-Call:** Check Slack #invoice-agent-oncall
- **DevOps:** See team directory
- **Slack Channels:**
  - #invoice-agent-dev (questions)
  - #invoice-agent-status (daily updates)
  - #invoice-agent-incidents (critical issues)

---

**Welcome to the team! You've got this.** 🚀

---

**Next:** Read [ARCHITECTURE.md](./ARCHITECTURE.md) to understand system design deeply.
