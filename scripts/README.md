# Development Scripts

Helper scripts for local development and testing.

## Setup Scripts

### setup-local.sh

Main setup script that configures the complete local development environment.

**Usage:**
```bash
./scripts/setup-local.sh
```

**What it does:**
- Validates Python 3.11+ and Docker prerequisites
- Creates Python virtual environment in `src/venv/`
- Installs all dependencies from `requirements.txt`
- Starts Azurite storage emulator in Docker
- Creates required storage tables and queues
- Copies `local.settings.json` from template
- Seeds sample vendor data
- Installs pre-commit hooks

**Idempotent:** Safe to run multiple times. Will skip existing resources.

## Utility Scripts

Additional scripts can be added here for:
- Data seeding variations
- Test data generation
- Environment cleanup
- Deployment helpers
- Migration scripts

## Examples

### First-time Setup
```bash
# Clone the repo
git clone <repo-url>
cd invoice-agent

# Run setup
./scripts/setup-local.sh

# Activate venv and start developing
source src/venv/bin/activate
```

### Daily Development
```bash
# Activate venv
source src/venv/bin/activate

# Start services
make run
```

### Reset Environment
```bash
# Clean everything
make clean-all

# Re-run setup
./scripts/setup-local.sh
```
