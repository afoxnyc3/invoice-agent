# Azure Serverless Development Skill

Scaffold new Azure Functions following project coding standards and patterns.

## Purpose

Generate complete Azure Function implementations that follow invoice-agent project standards:
- ≤25 lines per function (extract helpers)
- Proper error handling and logging
- Pydantic validation models
- ULID correlation IDs
- Correct import structure (`from shared.*`, `from functions.*`)
- Complete unit tests (96% coverage standard)
- Type hints (mypy strict mode)

## Parameters

- `--name`: Function name (required) - PascalCase, e.g., "ProcessRefund"
- `--trigger`: Trigger type (required)
  - `timer`: Timer trigger (cron schedule)
  - `queue`: Queue trigger
  - `http`: HTTP trigger
  - `blob`: Blob trigger
- `--input-queue`: Input queue name (for queue trigger)
- `--output-queue`: Output queue name (if function writes to queue)
- `--schedule`: Cron schedule (for timer trigger)
- `--http-methods`: HTTP methods (for HTTP trigger), default: POST
- `--description`: Function purpose (1-2 sentences)

## Instructions

When this skill is invoked, generate a complete function implementation following these steps:

### 1. Validate Function Name & Parameters

- Check function name is PascalCase
- Validate trigger type and required parameters
- Ensure no duplicate function exists in `src/` directory
- Confirm output directory: `src/{FunctionName}/`

### 2. Generate function.json (Bindings)

Create `src/{FunctionName}/function.json` with appropriate bindings based on trigger type.

**Timer Trigger Template:**
```json
{
  "scriptFile": "__init__.py",
  "bindings": [
    {
      "name": "timer",
      "type": "timerTrigger",
      "direction": "in",
      "schedule": "0 0 * * * *"
    }
  ]
}
```

**Queue Trigger Template:**
```json
{
  "scriptFile": "__init__.py",
  "bindings": [
    {
      "name": "msg",
      "type": "queueTrigger",
      "direction": "in",
      "queueName": "input-queue-name",
      "connection": "AzureWebJobsStorage"
    },
    {
      "name": "outQueueItem",
      "type": "queue",
      "direction": "out",
      "queueName": "output-queue-name",
      "connection": "AzureWebJobsStorage"
    }
  ]
}
```

**HTTP Trigger Template:**
```json
{
  "scriptFile": "__init__.py",
  "bindings": [
    {
      "authLevel": "function",
      "type": "httpTrigger",
      "direction": "in",
      "name": "req",
      "methods": ["post"]
    },
    {
      "type": "http",
      "direction": "out",
      "name": "$return"
    }
  ]
}
```

### 3. Generate __init__.py (Main Function Code)

Create `src/{FunctionName}/__init__.py` following project patterns:

**Code Structure Template:**
```python
"""
{FunctionName} - {description}

{Extended description of what this function does, including:
- Input: What data/messages it receives
- Processing: What transformations/operations it performs
- Output: What it produces/sends
}
"""

import os
import logging
import json
import traceback
import azure.functions as func
from shared.ulid_generator import generate_ulid
# Import additional shared modules as needed:
# from shared.graph_client import GraphAPIClient
# from shared.models import RawMail, EnrichedInvoice
# from azure.storage.blob import BlobServiceClient

logger = logging.getLogger(__name__)


def main({binding_parameters}):
    """
    {One-line function purpose}

    Args:
        {binding_parameters}: Description of each parameter

    Returns:
        {return_type}: Description of return value (if applicable)

    Raises:
        {Exception types}: When they occur
    """
    try:
        # Generate correlation ID for tracking
        correlation_id = generate_ulid()
        logger.info(f"{FunctionName} started: {correlation_id}")

        # === MAIN PROCESSING LOGIC ===
        # Keep this section ≤25 lines total
        # Extract complex logic to helper functions below

        # Example for queue trigger:
        # message = json.loads(msg.get_body().decode("utf-8"))
        # result = process_message(message, correlation_id)
        # outQueueItem.set(json.dumps(result))

        logger.info(f"{FunctionName} completed: {correlation_id}")

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in message: {str(e)}")
        logger.debug(traceback.format_exc())
        raise
    except KeyError as e:
        logger.error(f"Missing required field: {str(e)}")
        logger.error("Check environment variables or message schema")
        logger.debug(traceback.format_exc())
        raise
    except Exception as e:
        logger.error(f"{FunctionName} failed: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(traceback.format_exc())
        raise


# === HELPER FUNCTIONS ===
# Extract business logic here to keep main() ≤25 lines

def helper_function_name(param: str) -> dict:
    """
    Brief description of what this helper does.

    Args:
        param: Description

    Returns:
        dict: Description of return value
    """
    # Implementation
    pass
```

**Key Code Standards to Apply:**
1. **Imports:** Always `from shared.*` NOT `from src.shared.*`
2. **Logging:** Include correlation IDs in all log statements
3. **Error Handling:** Catch specific exceptions, log with traceback
4. **Type Hints:** Full annotations for all function signatures
5. **Line Limit:** Main function body ≤25 lines, extract helpers
6. **Docstrings:** Google-style format for all functions

### 4. Generate Pydantic Models (if processing queue messages)

If function processes queue messages, add or update models in `src/shared/models.py`:

```python
class {ModelName}(BaseModel):
    """
    Schema for {description}.

    Used by: {FunctionName}
    Queue: {queue_name}
    """
    id: str = Field(..., description="Transaction ID (ULID)")
    # Add fields with appropriate types and validation
    field_name: str = Field(..., description="Field description")

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'  # Strict - no extra fields allowed
    )
```

### 5. Generate Unit Tests

Create `tests/unit/test_{snake_case_function_name}.py`:

```python
"""
Unit tests for {FunctionName} function.

Ensures {FunctionName} correctly processes {input} and produces {output}.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
import azure.functions as func
from {FunctionName} import main


class Test{FunctionName}:
    """Test suite for {FunctionName} Azure Function."""

    def test_successful_processing(self, mocker):
        """Test successful {description}."""
        # Arrange
        # Create mock input (queue message, HTTP request, etc.)
        # Mock external dependencies (Graph API, Storage, etc.)

        # Act
        result = main(mock_input)

        # Assert
        assert result is not None
        # Add specific assertions based on expected output

    def test_invalid_json_handling(self, mocker):
        """Test handling of malformed JSON input."""
        # Arrange: Create invalid JSON
        # Act & Assert: Verify proper error handling

    def test_missing_required_fields(self, mocker):
        """Test handling of incomplete message data."""
        # Test Pydantic validation or KeyError handling

    def test_external_service_failure(self, mocker):
        """Test handling of external dependency failures."""
        # Mock Graph API failure, Storage failure, etc.
        # Verify retry logic or error logging

    # Add more tests to achieve 96% coverage:
    # - Edge cases (empty strings, null values, etc.)
    # - Different error scenarios
    # - Happy path variations
```

**Testing Standards:**
- Use fixtures from `tests/fixtures/` where applicable
- Mock external services (GraphAPIClient, BlobServiceClient, etc.)
- Test both success and failure paths
- Achieve 96% coverage (project standard)
- Use `mocker` fixture for clean mocking

### 6. Update Project Documentation

Add function documentation to relevant files:

**Update README.md** (if adding new user-facing functionality):
```markdown
### {FunctionName}
- **Trigger:** {trigger_type}
- **Purpose:** {description}
- **Input:** {input_description}
- **Output:** {output_description}
- **Status:** ✅ Active / 🟡 Pending / ❌ Not Implemented
```

**Update docs/ARCHITECTURE.md** (System Components section):
```markdown
#### {Number}. {FunctionName} Function
**Purpose**: {one_line_description}

- **Trigger**: {trigger_details}
- **Input**: {input_details}
- **Output**: {output_details}
- **Processing**:
  1. {processing_step_1}
  2. {processing_step_2}
  3. {processing_step_3}
  ...
- **Max Execution Time**: {time_limit}
- **Scaling**: {scaling_behavior}
```

### 7. Generate Summary Report

Provide a comprehensive summary of what was created:

```
🎉 Azure Function Generated: {FunctionName}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Trigger Type: {trigger}
Input: {input_description}
Output: {output_description}
Description: {description}

📁 Files Created:
✅ src/{FunctionName}/__init__.py ({line_count} lines)
✅ src/{FunctionName}/function.json
✅ tests/unit/test_{snake_case}.py
{if_model_created}✅ src/shared/models.py (updated with {ModelName})

📋 Next Steps:
1. Review generated code for business logic accuracy
2. Implement helper functions (main function currently {X} lines)
3. Add specific field validation to Pydantic model (if applicable)
4. Run tests: pytest tests/unit/test_{snake_case}.py -v
5. Run quality check: /skill:quality-check --mode pre-commit
6. Update queue configuration if needed
7. Add detailed processing steps to ARCHITECTURE.md

🔍 Code Review Checklist:
- [ ] Main function ≤25 lines (extract helpers if needed)
- [ ] All external calls have try/except error handling
- [ ] Type hints complete (mypy strict compliance)
- [ ] Docstrings follow Google style format
- [ ] Tests cover happy path + error scenarios
- [ ] Correlation ID in all log messages
- [ ] Pydantic models use strict mode (extra='forbid')
- [ ] Import structure correct (from shared.* not from src.shared.*)

💡 Helpful Commands:
# Run tests
pytest tests/unit/test_{snake_case}.py -v --cov={FunctionName}

# Check formatting
black src/{FunctionName} tests/unit/test_{snake_case}.py

# Type check
mypy src/{FunctionName}/__init__.py --strict

# Run quality gates
/skill:quality-check --mode pre-commit
```

## Examples

**Example 1: Queue-triggered processing function**
```
/skill:azure-function \
  --name ProcessRefund \
  --trigger queue \
  --input-queue refund-requests \
  --output-queue refund-processed \
  --description "Process refund requests and validate against transaction history"
```

**Example 2: Timer-triggered report function**
```
/skill:azure-function \
  --name DailyReport \
  --trigger timer \
  --schedule "0 0 9 * * *" \
  --description "Generate daily invoice processing summary and send to management"
```

**Example 3: HTTP API endpoint**
```
/skill:azure-function \
  --name UpdateVendor \
  --trigger http \
  --http-methods POST,PUT \
  --description "Update vendor information in VendorMaster table with validation"
```

## Code Quality Standards Applied

All generated code follows these project standards:

- ✅ Functions ≤25 lines (business logic in helpers)
- ✅ Import structure: `from shared.*` (Azure Functions compatible)
- ✅ ULID for transaction/correlation IDs
- ✅ Pydantic validation in strict mode (extra='forbid')
- ✅ Comprehensive error handling (specific exceptions)
- ✅ Structured logging with correlation IDs
- ✅ Full type hints (mypy strict mode compliance)
- ✅ Google-style docstrings
- ✅ Unit tests targeting 96% coverage
- ✅ pytest fixtures for test data

## Notes

- Generated code is a **starting point** - customize business logic as needed
- If main function exceeds 25 lines, **extract helper functions immediately**
- Run quality checks before committing: `/skill:quality-check --mode pre-commit`
- Integration tests should be added separately (not auto-generated)
- Update CLAUDE.md if you discover new patterns or standards
- Consider adding to CI/CD pipeline after testing locally
