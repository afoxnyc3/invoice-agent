# Integration Tests

Comprehensive integration test suite for the Invoice Agent project. Tests validate end-to-end workflows, queue processing, performance, and vendor management.

## Prerequisites

### Azurite (Azure Storage Emulator)

Integration tests require Azurite to emulate Azure Storage (Queues, Blobs, Tables) locally.

**Install and run Azurite:**

```bash
# Option 1: Docker (recommended)
docker run -d -p 10000:10000 -p 10001:10001 -p 10002:10002 \
  --name azurite \
  mcr.microsoft.com/azure-storage/azurite

# Option 2: npm
npm install -g azurite
azurite --silent --location /tmp/azurite --debug /tmp/azurite-debug.log
```

**Verify Azurite is running:**

```bash
# Should connect without error
az storage blob list --connection-string "UseDevelopmentStorage=true" --container-name test 2>/dev/null || echo "Azurite running"
```

## Running Integration Tests

### Run all integration tests

```bash
# With Azurite running
pytest tests/integration -v
```

### Run specific test modules

```bash
# End-to-end tests only
pytest tests/integration/test_end_to_end.py -v

# Queue retry tests only
pytest tests/integration/test_queue_retry.py -v

# Performance tests only
pytest tests/integration/test_performance.py -v

# Vendor management tests only
pytest tests/integration/test_vendor_management.py -v
```

### Run by marker

```bash
# Run only e2e tests
pytest -m e2e -v

# Run only integration tests
pytest -m integration -v

# Run only slow tests
pytest -m slow -v

# Exclude slow tests
pytest -m "not slow" -v
```

### Skip integration tests

```bash
# Run only unit tests (skip integration)
pytest -m "not integration" -v
```

## Test Coverage

### End-to-End Tests (`test_end_to_end.py`)

- **Happy Path**: Complete flow from email → Teams notification for known vendor
- **Unknown Vendor**: Email from vendor not in VendorMaster
- **Missing Attachment**: Email without PDF attachment
- **Malformed Email**: Invalid email format handling

### Queue & Retry Tests (`test_queue_retry.py`)

- **Message Visibility Timeout**: Queue message retry mechanism
- **Transient Failure Retry**: Automatic retry on temporary errors
- **Poison Queue**: Failed messages moved to poison queue after max retries
- **Successful Retry**: Processing succeeds after transient error
- **Graph API Throttling**: Retry logic for 429 responses
- **Concurrent Processing**: Multiple messages processed simultaneously

### Performance Tests (`test_performance.py`)

- **50 Concurrent Invoices**: System handles 50 invoices within 60 seconds
- **Single Invoice Latency**: End-to-end processing <10 seconds
- **Queue Throughput**: Message send/receive performance
- **Blob Throughput**: Upload/download performance
- **Table Throughput**: Insert/query performance
- **Memory Stability**: No memory leaks under load

### Vendor Management Tests (`test_vendor_management.py`)

- **Add New Vendor**: HTTP POST creates vendor in VendorMaster
- **Update Vendor**: Upsert existing vendor
- **Missing Required Fields**: Validation error handling
- **Invalid GL Code**: 4-digit GL code validation
- **Domain Normalization**: Vendor domain lowercase with underscores
- **Batch Vendor Addition**: Multiple vendors in sequence
- **Malformed JSON**: Error handling for bad requests
- **Query by Department**: Table query functionality
- **Active Flag**: Soft delete with Active flag

## Test Structure

```
tests/integration/
├── __init__.py                 # Package initialization
├── conftest.py                 # Shared fixtures
├── test_end_to_end.py          # E2E workflow tests
├── test_queue_retry.py         # Retry logic tests
├── test_performance.py         # Performance tests
├── test_vendor_management.py   # AddVendor HTTP tests
├── fixtures/
│   ├── sample_emails.json      # Test email templates
│   ├── sample_vendors.csv      # Test vendor data
│   └── sample_pdfs/            # Test PDF attachments
└── utils/
    ├── storage_helper.py       # Azure Storage utilities
    ├── mock_graph_api.py       # Mock Graph API client
    └── assertions.py           # Custom test assertions
```

## Fixtures

### Storage Fixtures

- `storage_helper`: Helper for Azure Storage operations (auto-cleanup)
- `test_queues`: Creates test queues (raw-mail, to-post, notify)
- `test_tables`: Creates test tables (VendorMaster, InvoiceTransactions)
- `test_blobs`: Creates test blob container (invoices)

### Data Fixtures

- `sample_vendors`: Pre-loads 5 vendors into VendorMaster
- `sample_emails`: Email templates (known vendor, unknown vendor, etc.)
- `sample_pdf`: Sample PDF file for attachment testing
- `transaction_id`: Unique ULID for each test

### Mock Fixtures

- `mock_graph_client`: Mock Microsoft Graph API client
- `mock_environment`: Mock environment variables
- `mock_teams_webhook`: Mock Teams webhook requests

## Performance Targets

| Metric | Target | Test |
|--------|--------|------|
| Single invoice latency | <10 seconds | `test_single_invoice_latency` |
| 50 concurrent invoices | <60 seconds | `test_concurrent_processing_50_invoices` |
| Queue send throughput | >10 msg/sec | `test_queue_throughput` |
| Queue receive throughput | >10 msg/sec | `test_queue_throughput` |
| Blob upload throughput | >1 blob/sec | `test_blob_storage_throughput` |
| Blob download throughput | >1 blob/sec | `test_blob_storage_throughput` |
| Table insert throughput | >5 entities/sec | `test_table_storage_throughput` |
| Memory growth | <50% after 100 iterations | `test_memory_usage_stability` |

## Troubleshooting

### Azurite not available

```
ERROR: Azurite not available: [Errno 61] Connection refused
```

**Solution:** Start Azurite before running tests.

```bash
docker start azurite
# or
azurite
```

### Port conflicts

```
ERROR: Address already in use
```

**Solution:** Stop conflicting services or use different ports.

```bash
# Find process using port 10000
lsof -i :10000

# Kill process or stop Azurite and restart
docker stop azurite
docker start azurite
```

### Tests timing out

**Solution:** Increase pytest timeout or check Azurite performance.

```bash
# Run with timeout disabled
pytest --timeout=0 tests/integration
```

### Connection string issues

**Solution:** Ensure environment uses Azurite connection string.

```python
# Should be set automatically by mock_environment fixture
AzureWebJobsStorage=UseDevelopmentStorage=true
```

## Writing New Integration Tests

### Template

```python
import pytest
from tests.integration.utils.assertions import assert_raw_mail_valid

@pytest.mark.integration
def test_my_new_integration_test(
    storage_helper,
    test_queues,
    test_tables,
    mock_environment,
):
    """Test description."""
    # Setup
    # ...

    # Execute
    # ...

    # Assert
    # ...
```

### Best Practices

1. **Use fixtures for setup/teardown**: Avoid manual resource management
2. **Mock external APIs**: Use `mock_graph_client`, `mock_teams_webhook`
3. **Clean assertions**: Use custom assertion helpers from `utils/assertions.py`
4. **Mark appropriately**: Use `@pytest.mark.integration`, `@pytest.mark.slow`, etc.
5. **Test isolation**: Each test should be independent
6. **Performance targets**: Document expected latency/throughput

## CI/CD Integration

Integration tests run in CI/CD pipeline with Azurite container:

```yaml
# .github/workflows/ci-cd.yml
services:
  azurite:
    image: mcr.microsoft.com/azure-storage/azurite
    ports:
      - 10000:10000
      - 10001:10001
      - 10002:10002

- name: Run integration tests
  run: pytest tests/integration -v --cov-report=xml
```

## Additional Resources

- [Azurite Documentation](https://github.com/Azure/Azurite)
- [pytest Documentation](https://docs.pytest.org/)
- [Azure Storage Python SDK](https://github.com/Azure/azure-sdk-for-python/tree/main/sdk/storage)
