#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$PROJECT_ROOT/src/venv"
AZURITE_CONTAINER_NAME="invoice-agent-azurite"
PYTHON_MIN_VERSION="3.11"

# Helper functions
print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        print_error "$1 is not installed"
        return 1
    fi
    print_success "$1 is installed"
    return 0
}

# Check prerequisites
print_header "Checking Prerequisites"

if ! check_command python3; then
    print_error "Python 3 is required. Install from https://www.python.org/downloads/"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [[ "$PYTHON_MAJOR" -lt 3 ]] || [[ "$PYTHON_MAJOR" -eq 3 && "$PYTHON_MINOR" -lt 11 ]]; then
    print_error "Python 3.11+ is required (found $PYTHON_VERSION)"
    exit 1
fi
print_success "Python $PYTHON_VERSION detected"

if ! check_command docker; then
    print_error "Docker is required. Install from https://www.docker.com/get-started"
    exit 1
fi

if ! docker info &> /dev/null; then
    print_error "Docker daemon is not running. Please start Docker Desktop."
    exit 1
fi
print_success "Docker is running"

# Setup Python virtual environment
print_header "Setting up Python Virtual Environment"

if [ -d "$VENV_DIR" ]; then
    print_warning "Virtual environment already exists at $VENV_DIR"
    read -p "Do you want to recreate it? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Removing existing virtual environment..."
        rm -rf "$VENV_DIR"
    else
        print_info "Using existing virtual environment"
    fi
fi

if [ ! -d "$VENV_DIR" ]; then
    print_info "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    print_success "Virtual environment created"
fi

# Activate virtual environment
print_info "Activating virtual environment..."
source "$VENV_DIR/bin/activate"
print_success "Virtual environment activated"

# Install dependencies
print_header "Installing Python Dependencies"

print_info "Upgrading pip..."
pip install --upgrade pip -q

print_info "Installing requirements..."
pip install -r "$PROJECT_ROOT/src/requirements.txt" -q
print_success "Dependencies installed"

# Install Azure Functions Core Tools check
if ! command -v func &> /dev/null; then
    print_warning "Azure Functions Core Tools not detected"
    print_info "Install from: https://learn.microsoft.com/en-us/azure/azure-functions/functions-run-local"
    print_info "For macOS: brew tap azure/functions && brew install azure-functions-core-tools@4"
else
    FUNC_VERSION=$(func --version)
    print_success "Azure Functions Core Tools $FUNC_VERSION detected"
fi

# Start Azurite
print_header "Starting Azurite Storage Emulator"

if docker ps -a --format '{{.Names}}' | grep -q "^${AZURITE_CONTAINER_NAME}$"; then
    if docker ps --format '{{.Names}}' | grep -q "^${AZURITE_CONTAINER_NAME}$"; then
        print_warning "Azurite container is already running"
    else
        print_info "Starting existing Azurite container..."
        docker start "$AZURITE_CONTAINER_NAME" > /dev/null
        print_success "Azurite container started"
    fi
else
    print_info "Creating and starting Azurite container..."
    docker run -d \
        --name "$AZURITE_CONTAINER_NAME" \
        -p 10000:10000 \
        -p 10001:10001 \
        -p 10002:10002 \
        -v invoice-agent-azurite-data:/data \
        mcr.microsoft.com/azure-storage/azurite:latest \
        azurite --blobHost 0.0.0.0 --queueHost 0.0.0.0 --tableHost 0.0.0.0
    print_success "Azurite container created and started"
fi

# Wait for Azurite to be ready
print_info "Waiting for Azurite to be ready..."
MAX_RETRIES=30
RETRY_COUNT=0
while ! curl -s http://127.0.0.1:10000/ > /dev/null 2>&1; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        print_error "Azurite failed to start after $MAX_RETRIES seconds"
        exit 1
    fi
    sleep 1
done
print_success "Azurite is ready"

# Install Azure Storage tools for table/queue creation
print_info "Installing azure-cli (for storage setup)..."
pip install azure-cli -q 2>/dev/null || print_warning "azure-cli installation skipped (optional)"

# Create storage tables and queues
print_header "Creating Storage Tables and Queues"

# Connection string for Azurite
AZURITE_CONNECTION_STRING="DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;QueueEndpoint=http://127.0.0.1:10001/devstoreaccount1;TableEndpoint=http://127.0.0.1:10002/devstoreaccount1;"

# Create tables using Python script
python3 << 'EOF'
import sys
from azure.data.tables import TableServiceClient
from azure.core.exceptions import ResourceExistsError

connection_string = "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;QueueEndpoint=http://127.0.0.1:10001/devstoreaccount1;TableEndpoint=http://127.0.0.1:10002/devstoreaccount1;"

table_service = TableServiceClient.from_connection_string(connection_string)

tables = ["VendorMaster", "InvoiceTransactions"]
for table_name in tables:
    try:
        table_service.create_table(table_name)
        print(f"✓ Created table: {table_name}")
    except ResourceExistsError:
        print(f"⚠ Table already exists: {table_name}")
    except Exception as e:
        print(f"✗ Error creating table {table_name}: {e}", file=sys.stderr)
EOF

# Create queues using Python script
python3 << 'EOF'
import sys
from azure.storage.queue import QueueServiceClient
from azure.core.exceptions import ResourceExistsError

connection_string = "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;QueueEndpoint=http://127.0.0.1:10001/devstoreaccount1;TableEndpoint=http://127.0.0.1:10002/devstoreaccount1;"

queue_service = QueueServiceClient.from_connection_string(connection_string)

queues = ["raw-mail", "to-post", "notify", "raw-mail-poison", "to-post-poison", "notify-poison"]
for queue_name in queues:
    try:
        queue_service.create_queue(queue_name)
        print(f"✓ Created queue: {queue_name}")
    except ResourceExistsError:
        print(f"⚠ Queue already exists: {queue_name}")
    except Exception as e:
        print(f"✗ Error creating queue {queue_name}: {e}", file=sys.stderr)
EOF

print_success "Storage resources created"

# Create local.settings.json if not exists
print_header "Configuring Local Settings"

LOCAL_SETTINGS_PATH="$PROJECT_ROOT/src/local.settings.json"
LOCAL_SETTINGS_TEMPLATE="$PROJECT_ROOT/src/local.settings.json.template"

if [ -f "$LOCAL_SETTINGS_PATH" ]; then
    print_warning "local.settings.json already exists"
else
    if [ -f "$LOCAL_SETTINGS_TEMPLATE" ]; then
        cp "$LOCAL_SETTINGS_TEMPLATE" "$LOCAL_SETTINGS_PATH"
        print_success "Created local.settings.json from template"
        print_warning "Remember to update Azure credentials in local.settings.json"
    else
        print_error "Template file not found: $LOCAL_SETTINGS_TEMPLATE"
    fi
fi

# Seed vendor data
print_header "Seeding Vendor Data"

if [ -f "$PROJECT_ROOT/infrastructure/scripts/seed_vendors.py" ]; then
    export AZURE_STORAGE_CONNECTION_STRING="$AZURITE_CONNECTION_STRING"
    python3 "$PROJECT_ROOT/infrastructure/scripts/seed_vendors.py" "$AZURITE_CONNECTION_STRING"
    print_success "Vendor data seeded"
else
    print_warning "Vendor seeding script not found"
fi

# Install pre-commit hooks (if configured)
if [ -f "$PROJECT_ROOT/.pre-commit-config.yaml" ]; then
    print_header "Installing Pre-commit Hooks"
    pip install pre-commit -q
    cd "$PROJECT_ROOT" && pre-commit install
    print_success "Pre-commit hooks installed"
fi

# Final summary
print_header "Setup Complete!"

echo ""
print_success "Local development environment is ready!"
echo ""
print_info "Next steps:"
echo "  1. Activate virtual environment: source src/venv/bin/activate"
echo "  2. Update Azure credentials in: src/local.settings.json"
echo "  3. Start functions locally: cd src && func start"
echo "  4. Run tests: pytest"
echo ""
print_info "Useful commands:"
echo "  - make run        # Start Azure Functions"
echo "  - make test       # Run tests with coverage"
echo "  - make lint       # Check code quality"
echo "  - make stop       # Stop Azurite"
echo "  - make clean      # Clean build artifacts"
echo ""
print_info "Azurite endpoints:"
echo "  - Blob:  http://127.0.0.1:10000"
echo "  - Queue: http://127.0.0.1:10001"
echo "  - Table: http://127.0.0.1:10002"
echo ""
print_info "Connection string (already in local.settings.json):"
echo "  UseDevelopmentStorage=true"
echo ""
