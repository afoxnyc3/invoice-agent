# Deduplication Test Builder Skill

Generates comprehensive test cases for deduplication scenarios across the pipeline.

## Purpose
- Create test fixtures with duplicate original_message_id
- Generate unit tests for ExtractEnrich dedup (new feature)
- Generate unit tests for PostToAP dedup (existing feature)
- Create integration tests for end-to-end dedup

## Usage
Invoke when you need to:
- Add deduplication test coverage
- Test duplicate detection logic
- Verify dedup works across webhook and fallback paths
- Test edge cases (simultaneous processing, race conditions)

## Test Scenarios to Generate

### 1. ExtractEnrich Deduplication Tests
**File:** `tests/unit/test_extract_enrich_dedup.py`

**Test Cases:**
- `test_extract_enrich_skips_duplicate_message_id` - First email processed, second skipped
- `test_extract_enrich_different_message_ids_both_processed` - Different IDs, both go through
- `test_extract_enrich_duplicate_logs_warning` - Duplicate detected, warning logged
- `test_extract_enrich_duplicate_not_queued` - Duplicate not added to to-post queue

### 2. PostToAP Deduplication Tests (Enhancement)
**File:** `tests/unit/test_post_to_ap_dedup.py`

**Test Cases:**
- `test_post_to_ap_check_already_processed_true` - Duplicate found in InvoiceTransactions
- `test_post_to_ap_check_already_processed_false` - No duplicate found
- `test_post_to_ap_skip_duplicate_no_email_sent` - Duplicate skipped, no Graph API call
- `test_post_to_ap_duplicate_different_status` - Handle different transaction statuses

### 3. Integration Tests
**File:** `tests/integration/test_deduplication_e2e.py`

**Test Cases:**
- `test_webhook_and_fallback_same_email` - Email processed by webhook, then fallback runs
- `test_duplicate_detection_prevents_double_posting` - Verify AP doesn't receive twice
- `test_duplicate_metrics_logged` - Custom metrics emitted for monitoring

## Test Fixture Template

### RawMail with Duplicate Message ID
```python
@pytest.fixture
def duplicate_raw_mail_messages():
    """Two queue messages with same original_message_id"""
    message_id = "AAMkAGNmOTU5YzI5LTk2ZjUtNDg2Ny1hYzk5LWFkMDc5YzM5MjEzNgBGAAAAAACjKM"

    message1 = {
        "id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
        "sender": "billing@adobe.com",
        "subject": "Invoice #12345",
        "blob_url": "https://storage/invoice1.pdf",
        "received_at": "2025-11-24T10:00:00Z",
        "original_message_id": message_id  # SAME ID
    }

    message2 = {
        "id": "01JCK3Q7H8ZVXN3BARC9GWAEZN",  # Different ULID
        "sender": "billing@adobe.com",
        "subject": "Invoice #12345",
        "blob_url": "https://storage/invoice1.pdf",
        "received_at": "2025-11-24T11:00:00Z",
        "original_message_id": message_id  # SAME ID (duplicate!)
    }

    return [message1, message2]
```

### Mock InvoiceTransactions with Existing Entry
```python
@pytest.fixture
def mock_invoice_transactions_with_duplicate(mocker):
    """Mock table client that returns existing transaction"""
    mock_table = mocker.Mock()

    # Simulate existing transaction found
    existing_entity = {
        "PartitionKey": "202511",
        "RowKey": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
        "OriginalMessageId": "AAMkAGNmOTU5YzI5...",
        "Status": "processed",
        "VendorName": "Adobe Inc",
        "ProcessedAt": "2025-11-24T10:05:00Z"
    }

    mock_table.query_entities.return_value = [existing_entity]
    return mock_table
```

## Test Implementation Template

### ExtractEnrich Dedup Test Example
```python
def test_extract_enrich_skips_duplicate_message_id(
    mocker,
    duplicate_raw_mail_messages,
    mock_invoice_transactions_with_duplicate
):
    """Test that ExtractEnrich skips emails with duplicate original_message_id"""

    # Arrange
    message1, message2 = duplicate_raw_mail_messages

    mock_table = mock_invoice_transactions_with_duplicate
    mocker.patch('shared.table_client.get_table_client', return_value=mock_table)

    mock_logger = mocker.patch('logging.Logger.warning')
    mock_queue_output = mocker.Mock()

    # Act - Process first message (should succeed)
    from ExtractEnrich import main
    main(message1, mock_queue_output)

    # Act - Process second message (should skip)
    main(message2, mock_queue_output)

    # Assert
    assert mock_queue_output.set.call_count == 1  # Only first message queued
    mock_logger.assert_called_once_with(
        "Skipping duplicate email - already processed",
        extra={"original_message_id": message2["original_message_id"]}
    )
```

## Execution Steps

1. **Generate test files** in `tests/unit/` and `tests/integration/`
2. **Create fixtures** for duplicate scenarios
3. **Implement test cases** using pytest patterns from existing tests
4. **Run tests** with `pytest tests/unit/test_*dedup*.py -v`
5. **Verify coverage** with `pytest --cov=functions --cov=shared --cov-report=html`
6. **Update CI/CD** to include dedup tests in quality gates

## Success Criteria
- All dedup test cases passing
- Coverage ≥95% for dedup logic
- Integration test validates end-to-end dedup
- Tests run in <10 seconds
