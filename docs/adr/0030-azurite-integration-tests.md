# ADR-0030: Azurite for Integration Tests

**Date:** 2024-11
**Status:** Accepted

## Context

Integration tests need to verify Azure Storage operations (queues, tables, blobs). Options were mocking all storage calls or using Azure Storage emulator.

## Decision

Use Azurite (Azure Storage emulator) in CI pipeline for realistic integration tests.

## Rationale

- More realistic than mocking
- Free (no Azure costs)
- Fast (local operations)
- Same API as production Azure Storage
- Official Microsoft tool

## Implementation

```yaml
# .github/workflows/ci-cd.yml
services:
  azurite:
    image: mcr.microsoft.com/azure-storage/azurite
    ports:
      - 10000:10000  # Blob
      - 10001:10001  # Queue
      - 10002:10002  # Table
```

## Test Configuration

```python
# tests/conftest.py
AZURITE_CONNECTION_STRING = (
    "DefaultEndpointsProtocol=http;"
    "AccountName=devstoreaccount1;"
    "AccountKey=...;"
    "BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"
)
```

## Consequences

- ✅ Realistic integration tests
- ✅ No Azure costs for testing
- ✅ Fast test execution
- ⚠️ Docker required in CI
- ⚠️ Some Azure features not emulated

## Related

- [ADR-0024: 85% Test Coverage Enforcement](0024-test-coverage-enforcement.md)
- See `.github/workflows/ci-cd.yml` for Docker setup
- See `tests/integration/` for integration tests
