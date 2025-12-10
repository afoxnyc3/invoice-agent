# Local Development Guide

Complete guide for setting up and working with the Invoice Agent locally.

## Quick Start

Get up and running in under 2 minutes:

```bash
# 1. Clone and navigate to the project
cd /path/to/invoice-agent

# 2. Run the setup script (does everything for you!)
./scripts/setup-local.sh

# 3. Activate the virtual environment
source src/venv/bin/activate

# 4. Start the Functions locally
cd src && func start
```

That's it! Your local development environment is ready.

## Prerequisites

Before running setup, ensure you have:

- **Python 3.11+** - [Download here](https://www.python.org/downloads/)
- **Docker Desktop** - [Download here](https://www.docker.com/get-started)
- **Azure Functions Core Tools** (optional but recommended)
  - macOS: `brew tap azure/functions && brew install azure-functions-core-tools@4`
  - Windows: `npm install -g azure-functions-core-tools@4`
  - Linux: [Installation guide](https://learn.microsoft.com/en-us/azure/azure-functions/functions-run-local)

### Verify Prerequisites

```bash
python3 --version    # Should be 3.11 or higher
docker --version     # Should be 20.10 or higher
func --version       # Should be 4.x (optional)
```

## What the Setup Script Does

The `setup-local.sh` script automates the entire local environment setup:

1. **Checks Prerequisites** - Validates Python 3.11+ and Docker
2. **Creates Virtual Environment** - In `src/venv/`
3. **Installs Dependencies** - All packages from `requirements.txt`
4. **Starts Azurite** - Storage emulator in Docker container
5. **Creates Storage Resources**:
   - Tables: `VendorMaster`, `InvoiceTransactions`
   - Queues: `raw-mail`, `to-post`, `notify` (+ poison queues)
6. **Copies Config** - `local.settings.json` from template
7. **Seeds Vendor Data** - 10 sample vendors for testing
8. **Installs Pre-commit Hooks** - Automated code quality checks

The script is **idempotent** - safe to run multiple times.

## Development Workflows

### Running Functions Locally

**Option 1: Using Make (Recommended)**
```bash
make run
```

**Option 2: Manual**
```bash
source src/venv/bin/activate
cd src
func start
```

The Functions will be available at `http://localhost:7071`

### Running Tests

**All tests with coverage:**
```bash
make test
```

**Unit tests only:**
```bash
make test-unit
```

**Integration tests (requires Azurite):**
```bash
make test-integration
```

**Coverage report (opens in browser):**
```bash
make test-coverage
```

**Manual test execution:**
```bash
source src/venv/bin/activate
export PYTHONPATH=./src
pytest tests/ -v --cov=functions --cov=shared
```

### Code Quality Checks

**Check code style (no changes):**
```bash
make lint
```

**Auto-fix formatting:**
```bash
make lint-fix
```

**Type checking:**
```bash
make type-check
```

**Pre-commit hooks (runs on every commit):**
```bash
# Install hooks
make install-pre-commit

# Run manually
pre-commit run --all-files
```

### Debugging with VS Code

The project includes pre-configured VS Code launch configurations:

1. **Debug Current File** - Run the Python file you're currently viewing
2. **Debug Pytest Current File** - Debug the test file you're viewing
3. **Debug All Tests** - Debug the entire test suite
4. **Debug Unit Tests** - Debug only unit tests
5. **Debug Integration Tests** - Debug only integration tests
6. **Attach to Functions** - Attach debugger to running Functions

**To debug:**
1. Open any function or test file
2. Press `F5` or click "Run and Debug" in the sidebar
3. Select the appropriate configuration
4. Set breakpoints and debug as normal

### Testing the Full Pipeline

Simulate a complete invoice processing workflow:

```bash
# 1. Start Azurite (if not running)
make start-azurite

# 2. Start Functions
make run

# 3. In another terminal, trigger MailIngest
curl http://localhost:7071/admin/functions/MailIngest

# 4. Check queue processing
# Monitor logs in the terminal where Functions are running

# 5. Inspect storage with Azure Storage Explorer
# Connection string: UseDevelopmentStorage=true
```

### Inspecting Storage

**Using Azure Storage Explorer:**
1. Download [Azure Storage Explorer](https://azure.microsoft.com/en-us/products/storage/storage-explorer/)
2. Connect to local emulator (automatic detection)
3. Browse tables, queues, and blobs

**Using Python:**
```python
from azure.data.tables import TableServiceClient

conn_str = "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;..."
service = TableServiceClient.from_connection_string(conn_str)

# List all vendors
table = service.get_table_client("VendorMaster")
vendors = list(table.query_entities("PartitionKey eq 'Vendor'"))
for v in vendors:
    print(f"{v['VendorName']} - GL: {v['GLCode']}")
```

**Using Azure CLI:**
```bash
# Set connection to Azurite
export AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;QueueEndpoint=http://127.0.0.1:10001/devstoreaccount1;TableEndpoint=http://127.0.0.1:10002/devstoreaccount1;"

# Query vendors
az storage entity query --table-name VendorMaster --filter "PartitionKey eq 'Vendor'"

# Peek queue messages
az storage message peek --queue-name raw-mail
```

## Useful Commands

### Environment Management

```bash
# Activate virtual environment
source src/venv/bin/activate

# Deactivate virtual environment
deactivate

# Recreate virtual environment
make clean-all
make setup
```

### Docker/Azurite Management

```bash
# Start Azurite
make start-azurite

# Stop Azurite
make stop-azurite

# View Azurite logs
docker logs invoice-agent-azurite

# Restart Azurite (clean state)
docker compose down
docker volume rm invoice-agent-azurite-data
make start-azurite
```

### Vendor Management

```bash
# Seed vendors
make seed-vendors

# Clear and reseed
python3 infrastructure/scripts/clear_vendors.py --env prod --force
make seed-vendors
```

### Cleanup

```bash
# Clean build artifacts and caches
make clean

# Clean everything including venv
make clean-all

# Reset to fresh state
make clean-all
make setup
```

### Status Check

```bash
# Check system status
make status

# Output:
# System Status:
# Python: 3.11.x
# Virtual Environment: Found at src/venv
# Azure Functions Core Tools: 4.x
# Docker: 24.x
# Azurite: Running
```

## Configuration

### local.settings.json

This file contains all local configuration. It's created from the template during setup.

**Important settings:**

```json
{
  "Values": {
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "FUNCTIONS_WORKER_RUNTIME": "python",

    "GRAPH_TENANT_ID": "your-tenant-id",
    "GRAPH_CLIENT_ID": "your-client-id",
    "GRAPH_CLIENT_SECRET": "your-client-secret",

    "INVOICE_MAILBOX": "invoices@yourcompany.com",
    "AP_EMAIL_ADDRESS": "accountspayable@yourcompany.com",
    "TEAMS_WEBHOOK_URL": "https://outlook.office.com/webhook/...",

    "AZURE_OPENAI_ENDPOINT": "https://your-openai.openai.azure.com/",
    "AZURE_OPENAI_API_KEY": "your-azure-openai-api-key",

    "ENVIRONMENT": "local",
    "LOG_LEVEL": "DEBUG"
  }
}
```

**For Microsoft Graph API (email access):**
1. Create an Azure AD app registration
2. Add API permissions: `Mail.Read`, `Mail.Send`
3. Create a client secret
4. Update the `GRAPH_*` and `INVOICE_MAILBOX` variables above

**For PDF vendor extraction (optional but recommended):**
1. Create an Azure OpenAI resource
2. Deploy the `gpt-4o-mini` model
3. Update the `AZURE_OPENAI_*` variables above

> **Note:** `MAIL_WEBHOOK_URL` and `GRAPH_CLIENT_STATE` are only needed in production for Graph API webhooks. Local development uses timer-based polling via MailIngest.

### Azurite Connection Strings

**Short form (recommended for local.settings.json):**
```
UseDevelopmentStorage=true
```

**Full form (for scripts and tools):**
```
DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;QueueEndpoint=http://127.0.0.1:10001/devstoreaccount1;TableEndpoint=http://127.0.0.1:10002/devstoreaccount1;
```

### Azurite Endpoints

- **Blob Storage**: `http://127.0.0.1:10000`
- **Queue Storage**: `http://127.0.0.1:10001`
- **Table Storage**: `http://127.0.0.1:10002`

## Troubleshooting

### Port Already in Use

**Problem:** Azurite won't start due to port conflicts.

**Solution:**
```bash
# Check what's using the ports
lsof -i :10000
lsof -i :10001
lsof -i :10002

# Kill the process or change Azurite ports in docker-compose.yml
docker compose down
# Edit docker-compose.yml to use different ports
docker compose up -d
```

### Azurite Not Starting

**Problem:** Docker container exits immediately.

**Solution:**
```bash
# Check Docker logs
docker logs invoice-agent-azurite

# Remove old container and volume
docker compose down
docker volume rm invoice-agent-azurite-data
make start-azurite

# Verify it's running
docker ps | grep azurite
curl http://127.0.0.1:10000/
```

### Tests Failing

**Problem:** Tests fail with import errors or connection errors.

**Solution:**
```bash
# Ensure PYTHONPATH is set
export PYTHONPATH=./src

# Ensure Azurite is running (for integration tests)
make start-azurite

# Reinstall dependencies
source src/venv/bin/activate
pip install -r src/requirements.txt

# Clear pytest cache
make clean
pytest tests/
```

### Functions Not Starting

**Problem:** `func start` fails or doesn't detect functions.

**Solution:**
```bash
# Ensure you're in the src/ directory
cd src

# Ensure venv is activated
source venv/bin/activate

# Check local.settings.json exists
ls -la local.settings.json

# Check function definitions
ls -la functions/*/function.json

# Try verbose mode
func start --verbose
```

### Virtual Environment Issues

**Problem:** Packages not found or wrong Python version.

**Solution:**
```bash
# Completely recreate venv
rm -rf src/venv
python3 -m venv src/venv
source src/venv/bin/activate
pip install --upgrade pip
pip install -r src/requirements.txt
```

### Import Errors

**Problem:** `ModuleNotFoundError` for `shared` or `functions`.

**Solution:**
- Tests use `from shared.*` and `from functions.*` (NOT `from src.shared.*`)
- Always set `PYTHONPATH=./src` before running tests
- VS Code settings handle this automatically
- pytest.ini is configured with the correct path

### Docker Daemon Not Running

**Problem:** `Cannot connect to the Docker daemon`

**Solution:**
- Start Docker Desktop
- Wait for the whale icon to appear (macOS) or tray icon (Windows)
- Verify: `docker info`

### Permission Denied on setup-local.sh

**Problem:** `Permission denied` when running setup script.

**Solution:**
```bash
chmod +x scripts/setup-local.sh
./scripts/setup-local.sh
```

### Graph API Authentication Errors

**Problem:** Functions can't connect to Microsoft Graph.

**Solution:**
1. Verify Azure AD app registration exists
2. Check API permissions are granted (admin consent required)
3. Verify client secret hasn't expired
4. Update `local.settings.json` with correct values
5. For local testing, consider using a test mailbox

## Development Tips

### Hot Reload

Azure Functions supports hot reload in development mode:
- Python files are reloaded automatically when changed
- No need to restart `func start` for code changes
- Restart required for config changes in `local.settings.json`

### Environment Variables

Load different configurations:
```bash
# Development
export ENVIRONMENT=local
export LOG_LEVEL=DEBUG

# Testing
export ENVIRONMENT=test
export LOG_LEVEL=INFO
```

### Queue Message Testing

Manually enqueue messages for testing:
```python
from azure.storage.queue import QueueClient

conn_str = "UseDevelopmentStorage=true"
queue = QueueClient.from_connection_string(conn_str, "raw-mail")

message = {
    "message_id": "test-123",
    "subject": "Invoice from Adobe",
    "sender": "billing@adobe.com",
    "received_at": "2025-11-11T10:00:00Z",
    "blob_url": "invoices/test-123.pdf"
}

import json
queue.send_message(json.dumps(message))
```

### Table Storage Inspection

Quick Python script to inspect tables:
```python
from azure.data.tables import TableServiceClient

conn = "UseDevelopmentStorage=true"
service = TableServiceClient.from_connection_string(conn)

# List all tables
for table in service.list_tables():
    print(f"Table: {table.name}")

# Query specific table
table = service.get_table_client("VendorMaster")
entities = list(table.query_entities("PartitionKey eq 'Vendor'"))
print(f"Found {len(entities)} vendors")
```

### Performance Testing

Load test the pipeline:
```bash
# Generate test emails
python tests/helpers/generate_test_emails.py --count 50

# Monitor queue depth
watch -n 1 'az storage message peek --queue-name raw-mail --num-messages 32'
```

## Docker Compose Profiles

The `docker-compose.yml` includes optional services:

**Start with MailHog (email testing):**
```bash
docker compose --profile mail-testing up -d
```

**Access MailHog UI:**
```
http://localhost:8025
```

## IDE Setup

### VS Code (Recommended)

The project includes complete VS Code configuration:
- `.vscode/launch.json` - Debug configurations
- `.vscode/settings.json` - Python, formatting, linting settings

**Extensions to install:**
- Python (ms-python.python)
- Pylance (ms-python.vscode-pylance)
- Black Formatter (ms-python.black-formatter)
- Azure Functions (ms-azuretools.vscode-azurefunctions)

### PyCharm

1. Open project root
2. Set interpreter: `src/venv/bin/python`
3. Mark `src/` as Sources Root
4. Set working directory to project root
5. Add environment variable: `PYTHONPATH=./src`

### Vim/Neovim

Add to your config:
```vim
" Set Python path
let $PYTHONPATH = getcwd() . '/src'

" Use project venv
let g:python3_host_prog = getcwd() . '/src/venv/bin/python'
```

## Additional Resources

- [Azure Functions Python Developer Guide](https://learn.microsoft.com/en-us/azure/azure-functions/functions-reference-python)
- [Azurite Documentation](https://learn.microsoft.com/en-us/azure/storage/common/storage-use-azurite)
- [Microsoft Graph API Reference](https://learn.microsoft.com/en-us/graph/api/overview)
- [pytest Documentation](https://docs.pytest.org/)
- [Black Code Formatter](https://black.readthedocs.io/)

## Getting Help

1. Check this guide first
2. Review existing tests for examples
3. Check logs: `docker logs invoice-agent-azurite`
4. Check Functions logs: `cd src && func start --verbose`
5. Ask the team in Slack #invoice-agent

---

**Last Updated:** 2025-11-11
**Maintained By:** Engineering Team
