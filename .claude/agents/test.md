# Test Agent

## Purpose
Generate comprehensive test suites for all Azure Functions with fixtures and mocks.

## Capabilities
- Create unit tests with pytest
- Mock external dependencies (Graph API, Storage)
- Generate test fixtures
- Implement integration tests
- Ensure 60% code coverage minimum

## Test Structure
```
tests/
├── unit/
│   ├── test_mail_ingest.py
│   ├── test_extract_enrich.py
│   ├── test_post_to_ap.py
│   └── test_notify.py
├── integration/
│   ├── test_end_to_end.py
│   └── test_queue_flow.py
├── fixtures/
│   ├── emails.json
│   ├── vendors.json
│   └── messages.json
└── conftest.py
```

## Unit Test Templates

### Test MailIngest Function
```python
import pytest
from unittest.mock import Mock, patch, MagicMock
import json
from datetime import datetime
from functions.MailIngest import main
from shared.models import RawMailMessage

class TestMailIngest:
    """Test cases for MailIngest function."""

    @patch('functions.MailIngest.GraphClient')
    @patch('functions.MailIngest.QueueClient')
    def test_process_unread_emails(self, mock_queue, mock_graph):
        """Test successful email processing."""
        # Arrange
        mock_graph_instance = mock_graph.return_value
        mock_graph_instance.get_unread_emails.return_value = [
            {
                "id": "msg123",
                "sender": {"emailAddress": {"address": "billing@adobe.com"}},
                "subject": "Invoice #12345",
                "hasAttachments": True,
                "attachments": [{"name": "invoice.pdf", "contentBytes": "base64data"}]
            }
        ]

        mock_queue_instance = mock_queue.return_value

        # Act
        timer = Mock()
        main(timer)

        # Assert
        mock_graph_instance.get_unread_emails.assert_called_once()
        mock_queue_instance.send_message.assert_called_once()

        # Verify message format
        sent_message = json.loads(
            mock_queue_instance.send_message.call_args[0][0]
        )
        assert sent_message["sender"] == "billing@adobe.com"
        assert sent_message["subject"] == "Invoice #12345"
        assert "blob_url" in sent_message

    @patch('functions.MailIngest.GraphClient')
    def test_handle_graph_api_error(self, mock_graph):
        """Test Graph API error handling."""
        # Arrange
        mock_graph.return_value.get_unread_emails.side_effect = Exception("API Error")

        # Act & Assert
        timer = Mock()
        with pytest.raises(Exception, match="API Error"):
            main(timer)

    @patch('functions.MailIngest.GraphClient')
    def test_skip_emails_without_attachments(self, mock_graph):
        """Test that emails without attachments are skipped."""
        # Arrange
        mock_graph.return_value.get_unread_emails.return_value = [
            {
                "id": "msg123",
                "sender": {"emailAddress": {"address": "info@example.com"}},
                "subject": "Newsletter",
                "hasAttachments": False
            }
        ]

        # Act
        timer = Mock()
        result = main(timer)

        # Assert
        # Verify no queue message sent
        assert result is None
```

### Test ExtractEnrich Function
```python
class TestExtractEnrich:
    """Test cases for ExtractEnrich function."""

    @patch('functions.ExtractEnrich.VendorMasterRepository')
    @patch('functions.ExtractEnrich.QueueClient')
    def test_enrich_known_vendor(self, mock_queue, mock_repo):
        """Test enrichment with known vendor."""
        # Arrange
        mock_repo_instance = mock_repo.return_value
        mock_repo_instance.find_by_email_domain.return_value = VendorMaster(
            vendor_name="Adobe Inc",
            expense_dept="IT",
            gl_code="6100",
            allocation_schedule_number="MONTHLY",
            billing_party="Chelsea Piers NY"
        )

        queue_message = json.dumps({
            "id": "123",
            "sender": "billing@adobe.com",
            "subject": "Invoice",
            "blob_url": "https://storage/invoice.pdf"
        })

        # Act
        main(queue_message)

        # Assert
        mock_repo_instance.find_by_email_domain.assert_called_with("billing@adobe.com")

        # Verify enriched message
        sent_message = json.loads(
            mock_queue.return_value.send_message.call_args[0][0]
        )
        assert sent_message["vendor_name"] == "Adobe Inc"
        assert sent_message["gl_code"] == "6100"
        assert sent_message["status"] == "enriched"

    @patch('functions.ExtractEnrich.VendorMasterRepository')
    def test_handle_unknown_vendor(self, mock_repo):
        """Test handling of unknown vendor."""
        # Arrange
        mock_repo.return_value.find_by_email_domain.return_value = None

        queue_message = json.dumps({
            "id": "123",
            "sender": "unknown@newvendor.com",
            "subject": "Invoice",
            "blob_url": "https://storage/invoice.pdf"
        })

        # Act
        result = main(queue_message)

        # Assert
        # Verify unknown vendor handling
        assert "unknown" in result.lower()
```

### Test PostToAP Function
```python
class TestPostToAP:
    """Test cases for PostToAP function."""

    @patch('functions.PostToAP.GraphClient')
    @patch('functions.PostToAP.InvoiceTransactionRepository')
    def test_send_enriched_to_ap(self, mock_repo, mock_graph):
        """Test sending enriched invoice to AP."""
        # Arrange
        queue_message = json.dumps({
            "id": "123",
            "vendor_name": "Adobe Inc",
            "gl_code": "6100",
            "expense_dept": "IT",
            "blob_url": "https://storage/invoice.pdf",
            "status": "enriched"
        })

        # Act
        main(queue_message)

        # Assert
        mock_graph.return_value.send_email.assert_called_once()

        # Verify email format
        call_args = mock_graph.return_value.send_email.call_args
        assert "Adobe Inc" in call_args[0][1]  # Subject
        assert "6100" in call_args[0][1]  # GL Code in subject

        # Verify transaction logged
        mock_repo.return_value.create_transaction.assert_called_once()
```

### Test Notify Function
```python
class TestNotify:
    """Test cases for Notify function."""

    @patch('requests.post')
    def test_send_success_notification(self, mock_post):
        """Test sending success notification to Teams."""
        # Arrange
        queue_message = json.dumps({
            "type": "success",
            "message": "Processed: Adobe Inc - GL 6100",
            "details": {
                "vendor": "Adobe Inc",
                "gl_code": "6100",
                "transaction_id": "123"
            }
        })

        mock_post.return_value.status_code = 200

        # Act
        main(queue_message)

        # Assert
        mock_post.assert_called_once()

        # Verify Teams message format
        call_args = mock_post.call_args
        teams_message = call_args[1]["json"]
        assert "✅" in teams_message["text"]
        assert "Adobe Inc" in teams_message["text"]

    @patch('requests.post')
    def test_handle_webhook_failure(self, mock_post):
        """Test handling of Teams webhook failure."""
        # Arrange
        mock_post.side_effect = Exception("Connection error")

        queue_message = json.dumps({
            "type": "error",
            "message": "Failed to process"
        })

        # Act & Assert
        # Should not raise - notifications are non-critical
        main(queue_message)
```

## Integration Tests

```python
# tests/integration/test_end_to_end.py
import pytest
from azure.storage.queue import QueueClient
import json
import time

class TestEndToEnd:
    """End-to-end integration tests."""

    @pytest.mark.integration
    def test_full_invoice_flow(self, storage_emulator):
        """Test complete flow from email to notification."""
        # Arrange
        raw_mail_queue = QueueClient.from_connection_string(
            storage_emulator.connection_string,
            "raw-mail"
        )

        test_message = {
            "id": "test123",
            "sender": "billing@adobe.com",
            "subject": "Invoice #12345",
            "blob_url": "https://storage/test.pdf"
        }

        # Act
        raw_mail_queue.send_message(json.dumps(test_message))

        # Wait for processing
        time.sleep(10)

        # Assert
        # Check transaction was logged
        transactions = get_transactions_by_id("test123")
        assert len(transactions) == 1
        assert transactions[0]["status"] == "processed"
        assert transactions[0]["gl_code"] == "6100"
```

## Test Fixtures

```python
# tests/conftest.py
import pytest
from unittest.mock import Mock
import json

@pytest.fixture
def mock_graph_client():
    """Mock Graph API client."""
    client = Mock()
    client.get_unread_emails.return_value = []
    client.send_email.return_value = {"id": "sent123"}
    client.mark_as_read.return_value = True
    return client

@pytest.fixture
def sample_vendor():
    """Sample vendor data."""
    return {
        "vendor_name": "Adobe Inc",
        "expense_dept": "IT",
        "gl_code": "6100",
        "allocation_schedule_number": "MONTHLY",
        "billing_party": "Chelsea Piers NY"
    }

@pytest.fixture
def sample_email():
    """Sample email data."""
    return {
        "id": "msg123",
        "sender": {"emailAddress": {"address": "billing@adobe.com"}},
        "subject": "Invoice #12345 - November 2024",
        "hasAttachments": True,
        "attachments": [
            {
                "name": "invoice.pdf",
                "contentBytes": "base64encodeddata",
                "size": 102400
            }
        ]
    }

@pytest.fixture
def storage_emulator():
    """Azurite storage emulator for integration tests."""
    # Start Azurite in Docker or use existing instance
    return Mock(connection_string="UseDevelopmentStorage=true")
```

## Coverage Configuration

```ini
# pytest.ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    --cov=functions
    --cov=shared
    --cov-report=html
    --cov-report=term
    --cov-fail-under=60

[coverage:run]
omit =
    tests/*
    */conftest.py
    */__init__.py
```

## Test Commands

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=functions --cov-report=html

# Run only unit tests
pytest tests/unit

# Run integration tests
pytest tests/integration -m integration

# Run specific test file
pytest tests/unit/test_mail_ingest.py

# Run with verbose output
pytest -v

# Run and stop on first failure
pytest -x
```

## Success Criteria
- All functions have unit tests
- External dependencies are mocked
- 60% code coverage achieved
- Integration tests pass
- Error scenarios tested
- Fixtures reduce duplication