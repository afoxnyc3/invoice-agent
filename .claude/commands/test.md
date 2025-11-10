# /test - Test Runner

Run comprehensive tests for all Azure Functions with coverage reporting.

## Actions

1. **Run unit tests**
   - Test each function in isolation
   - Mock external dependencies
   - Verify business logic
   - Check error handling

2. **Run integration tests**
   - Test queue message flow
   - Verify data persistence
   - Test with Azurite emulator
   - Validate end-to-end flow

3. **Check code coverage**
   - Ensure 60% minimum coverage
   - Generate HTML coverage report
   - Identify untested code paths
   - Suggest additional tests

4. **Validate schemas**
   - Check queue message formats
   - Validate Pydantic models
   - Test data serialization
   - Verify API contracts

5. **Run security checks**
   - No hardcoded secrets
   - Input validation present
   - No SQL injection risks
   - Secure API calls

## Test Execution

When user types `/test`:

```bash
# Activate virtual environment
cd src
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install test dependencies
pip install pytest pytest-cov pytest-mock pytest-azurite

# Start Azurite for integration tests (Docker)
docker run -d -p 10000:10000 -p 10001:10001 -p 10002:10002 \
  --name azurite mcr.microsoft.com/azure-storage/azurite

# Run unit tests with coverage
pytest tests/unit \
  --cov=functions \
  --cov=shared \
  --cov-report=html \
  --cov-report=term \
  --cov-fail-under=60 \
  -v

# Run integration tests
pytest tests/integration -m integration

# Run security checks
bandit -r functions/ shared/

# Check for type errors
mypy functions/ shared/ --strict

# Validate queue message schemas
python scripts/validate_schemas.py
```

## Test Output Example

```
============================= test session starts ==============================
platform darwin -- Python 3.11.0, pytest-7.4.0

tests/unit/test_mail_ingest.py::TestMailIngest::test_process_unread_emails PASSED
tests/unit/test_mail_ingest.py::TestMailIngest::test_handle_graph_api_error PASSED
tests/unit/test_mail_ingest.py::TestMailIngest::test_skip_emails_without_attachments PASSED
tests/unit/test_extract_enrich.py::TestExtractEnrich::test_enrich_known_vendor PASSED
tests/unit/test_extract_enrich.py::TestExtractEnrich::test_handle_unknown_vendor PASSED
tests/unit/test_post_to_ap.py::TestPostToAP::test_send_enriched_to_ap PASSED
tests/unit/test_notify.py::TestNotify::test_send_success_notification PASSED
tests/unit/test_notify.py::TestNotify::test_handle_webhook_failure PASSED

tests/integration/test_end_to_end.py::TestEndToEnd::test_full_invoice_flow PASSED

================================ Coverage Report ================================
Name                          Stmts   Miss  Cover
-------------------------------------------------
functions/MailIngest/__init__     24      3    88%
functions/ExtractEnrich/__init__  23      2    91%
functions/PostToAP/__init__       25      4    84%
functions/Notify/__init__         20      2    90%
shared/graph.py                   45      8    82%
shared/storage.py                 38      6    84%
shared/models.py                  25      0   100%
-------------------------------------------------
TOTAL                            200     25    87%

✅ All tests passed (9 passed in 3.42s)
✅ Coverage: 87% (exceeds 60% minimum)
✅ No security issues found
✅ Type checking passed
✅ Queue schemas valid

📊 Test Report:
- Unit tests: 8/8 passed
- Integration tests: 1/1 passed
- Coverage: 87%
- Security scan: Clean
- Type check: No errors

HTML coverage report generated at: htmlcov/index.html
```

## Test Categories

### Unit Tests
```python
# tests/unit/test_mail_ingest.py
- test_process_unread_emails()
- test_handle_graph_api_error()
- test_skip_emails_without_attachments()
- test_handle_malformed_email()
- test_retry_on_throttling()
```

### Integration Tests
```python
# tests/integration/test_end_to_end.py
- test_full_invoice_flow()
- test_unknown_vendor_flow()
- test_error_recovery()
- test_queue_retry_logic()
```

### Performance Tests
```python
# tests/performance/test_load.py
- test_process_50_concurrent_emails()
- test_vendor_lookup_performance()
- test_queue_throughput()
```

## Coverage Requirements

### Minimum Coverage by Component
- Functions: 80% minimum
- Shared utilities: 70% minimum
- Models: 90% minimum
- Overall: 60% minimum (MVP)

### Critical Paths (Must Test)
- Email ingestion happy path
- Vendor lookup and enrichment
- Unknown vendor handling
- Error notification flow
- Transaction logging

## Test Data Fixtures

```python
# tests/fixtures/test_data.py
SAMPLE_EMAIL = {
    "id": "msg123",
    "sender": {"emailAddress": {"address": "billing@adobe.com"}},
    "subject": "Invoice #12345",
    "hasAttachments": True,
    "attachments": [{"name": "invoice.pdf", "contentBytes": "base64..."}]
}

SAMPLE_VENDOR = {
    "vendor_name": "Adobe Inc",
    "expense_dept": "IT",
    "gl_code": "6100",
    "allocation_schedule_number": "MONTHLY",
    "billing_party": "Company HQ"
}

UNKNOWN_VENDOR_EMAIL = {
    "sender": {"emailAddress": {"address": "newvendor@unknown.com"}},
    "subject": "Invoice for services"
}
```

## Continuous Testing

```yaml
# Run tests on every commit
pre-commit:
  - pytest tests/unit --cov-fail-under=60
  - mypy functions/ shared/
  - bandit -r functions/ shared/
```

## Troubleshooting

### Common Issues
1. **Import errors** → Check virtual environment activated
2. **Azurite connection failed** → Start Docker container
3. **Coverage too low** → Add tests for error paths
4. **Type errors** → Add type hints to functions
5. **Mock failures** → Check mock configuration

### Debug Commands
```bash
# Run specific test
pytest tests/unit/test_mail_ingest.py::test_process_unread_emails -v

# Run with debugging
pytest --pdb

# Show test output
pytest -s

# Run only failed tests
pytest --lf
```

## Success Criteria
- All unit tests pass
- Integration tests complete
- 60%+ code coverage
- No security vulnerabilities
- Type checking passes
- Queue schemas valid