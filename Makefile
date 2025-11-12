.PHONY: help setup run dev test test-unit test-integration test-coverage lint lint-fix type-check clean stop start-azurite stop-azurite seed-vendors

# Default Python and paths
PYTHON := python3
VENV := src/venv
VENV_BIN := $(VENV)/bin
VENV_PYTHON := $(VENV_BIN)/python
VENV_PIP := $(VENV_BIN)/pip
PROJECT_ROOT := $(shell pwd)

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[1;33m
NC := \033[0m

help: ## Show this help message
	@echo "$(BLUE)Invoice Agent - Development Commands$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""

setup: ## Initial setup - run this first!
	@echo "$(BLUE)Running initial setup...$(NC)"
	@./scripts/setup-local.sh

run: ## Start Azure Functions locally
	@echo "$(BLUE)Starting Azure Functions...$(NC)"
	@if [ ! -d "$(VENV)" ]; then \
		echo "$(YELLOW)Virtual environment not found. Run 'make setup' first.$(NC)"; \
		exit 1; \
	fi
	@cd src && $(VENV_BIN)/func start

dev: run ## Alias for 'run' - start functions locally

test: ## Run all tests with coverage
	@echo "$(BLUE)Running tests with coverage...$(NC)"
	@if [ ! -d "$(VENV)" ]; then \
		echo "$(YELLOW)Virtual environment not found. Run 'make setup' first.$(NC)"; \
		exit 1; \
	fi
	@export PYTHONPATH=$(PROJECT_ROOT)/src && $(VENV_PYTHON) -m pytest tests/ -v --cov=functions --cov=shared --cov-report=term-missing --cov-report=html

test-unit: ## Run unit tests only
	@echo "$(BLUE)Running unit tests...$(NC)"
	@export PYTHONPATH=$(PROJECT_ROOT)/src && $(VENV_PYTHON) -m pytest tests/unit -v --cov=functions --cov=shared

test-integration: ## Run integration tests only
	@echo "$(BLUE)Running integration tests...$(NC)"
	@if ! docker ps | grep -q invoice-agent-azurite; then \
		echo "$(YELLOW)Azurite is not running. Starting it now...$(NC)"; \
		make start-azurite; \
		sleep 3; \
	fi
	@export PYTHONPATH=$(PROJECT_ROOT)/src && $(VENV_PYTHON) -m pytest tests/integration -v -m integration

test-coverage: ## Run tests and open coverage report in browser
	@echo "$(BLUE)Running tests and generating coverage report...$(NC)"
	@export PYTHONPATH=$(PROJECT_ROOT)/src && $(VENV_PYTHON) -m pytest tests/ -v --cov=functions --cov=shared --cov-report=html
	@echo "$(GREEN)Opening coverage report...$(NC)"
	@open htmlcov/index.html || xdg-open htmlcov/index.html || start htmlcov/index.html

lint: ## Check code quality (black, flake8, mypy)
	@echo "$(BLUE)Checking code formatting with black...$(NC)"
	@$(VENV_PYTHON) -m black --check src/ tests/ --line-length=120
	@echo "$(BLUE)Checking code style with flake8...$(NC)"
	@$(VENV_PYTHON) -m flake8 src/ tests/ --max-line-length=120 --extend-ignore=E203,W503
	@echo "$(GREEN)Lint checks passed!$(NC)"

lint-fix: ## Auto-fix code formatting issues
	@echo "$(BLUE)Formatting code with black...$(NC)"
	@$(VENV_PYTHON) -m black src/ tests/ --line-length=120
	@echo "$(GREEN)Code formatted!$(NC)"

type-check: ## Run mypy type checking
	@echo "$(BLUE)Running type checking with mypy...$(NC)"
	@$(VENV_PYTHON) -m mypy src/functions src/shared --strict --ignore-missing-imports

start-azurite: ## Start Azurite storage emulator
	@echo "$(BLUE)Starting Azurite...$(NC)"
	@docker compose up -d azurite
	@echo "$(GREEN)Azurite started!$(NC)"

stop-azurite: ## Stop Azurite storage emulator
	@echo "$(BLUE)Stopping Azurite...$(NC)"
	@docker compose down
	@echo "$(GREEN)Azurite stopped!$(NC)"

stop: stop-azurite ## Stop all services

seed-vendors: ## Seed vendor data into local storage
	@echo "$(BLUE)Seeding vendor data...$(NC)"
	@if ! docker ps | grep -q invoice-agent-azurite; then \
		echo "$(YELLOW)Azurite is not running. Starting it now...$(NC)"; \
		make start-azurite; \
		sleep 3; \
	fi
	@export AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;QueueEndpoint=http://127.0.0.1:10001/devstoreaccount1;TableEndpoint=http://127.0.0.1:10002/devstoreaccount1;" && \
	$(VENV_PYTHON) infrastructure/scripts/seed_vendors.py
	@echo "$(GREEN)Vendor data seeded!$(NC)"

clean: ## Clean build artifacts and caches
	@echo "$(BLUE)Cleaning build artifacts...$(NC)"
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	@rm -f .coverage 2>/dev/null || true
	@rm -rf src/.pytest_cache 2>/dev/null || true
	@echo "$(GREEN)Cleaned!$(NC)"

clean-all: clean ## Clean everything including venv
	@echo "$(BLUE)Cleaning virtual environment...$(NC)"
	@rm -rf $(VENV)
	@echo "$(GREEN)Everything cleaned!$(NC)"

install-dev-tools: ## Install development tools (black, flake8, etc.)
	@echo "$(BLUE)Installing development tools...$(NC)"
	@$(VENV_PIP) install black flake8 mypy pre-commit bandit
	@echo "$(GREEN)Development tools installed!$(NC)"

install-pre-commit: ## Install pre-commit hooks
	@echo "$(BLUE)Installing pre-commit hooks...$(NC)"
	@if [ ! -f .pre-commit-config.yaml ]; then \
		echo "$(YELLOW).pre-commit-config.yaml not found$(NC)"; \
		exit 1; \
	fi
	@$(VENV_BIN)/pre-commit install
	@echo "$(GREEN)Pre-commit hooks installed!$(NC)"

status: ## Check system status
	@echo "$(BLUE)System Status:$(NC)"
	@echo ""
	@echo "$(GREEN)Python:$(NC)"
	@python3 --version || echo "$(YELLOW)Not found$(NC)"
	@echo ""
	@echo "$(GREEN)Virtual Environment:$(NC)"
	@if [ -d "$(VENV)" ]; then echo "  Found at $(VENV)"; else echo "  $(YELLOW)Not found - run 'make setup'$(NC)"; fi
	@echo ""
	@echo "$(GREEN)Azure Functions Core Tools:$(NC)"
	@func --version 2>/dev/null || echo "  $(YELLOW)Not found$(NC)"
	@echo ""
	@echo "$(GREEN)Docker:$(NC)"
	@docker --version 2>/dev/null || echo "  $(YELLOW)Not found$(NC)"
	@echo ""
	@echo "$(GREEN)Azurite:$(NC)"
	@if docker ps | grep -q invoice-agent-azurite; then echo "  Running"; else echo "  $(YELLOW)Not running$(NC)"; fi
	@echo ""

watch-tests: ## Watch tests and re-run on changes
	@echo "$(BLUE)Watching tests...$(NC)"
	@$(VENV_PYTHON) -m pytest_watch tests/ -v
