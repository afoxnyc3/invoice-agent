# 0032. Circuit Breaker Pattern

**Date:** 2024-12-05
**Status:** Accepted

## Context

The Invoice Agent system depends on multiple external services that can fail or become slow:
- **Microsoft Graph API** for email operations (read, send, mark as read)
- **Azure OpenAI** for intelligent PDF vendor extraction
- **Azure Blob Storage** for PDF downloads during processing

When these services experience outages or performance degradation, our system can suffer from:
- **Resource exhaustion**: Functions retry endlessly, consuming memory and execution time
- **Cascade failures**: Slow responses block queue processing, creating backlog
- **Poor user experience**: Long timeouts (5 minutes) before failure detection
- **Wasted costs**: Consumption plan charges for failed retry attempts

Traditional retry logic with exponential backoff helps with transient errors but doesn't protect against sustained outages. We need a mechanism to detect repeated failures and fail fast.

## Decision

Implement circuit breaker pattern using the **pybreaker** library to protect all external service calls.

Circuit breakers will:
1. Track consecutive failures for each external dependency
2. "Open" after a threshold of failures, failing fast without calling the service
3. Enter "half-open" state after a timeout to test if service has recovered
4. "Close" when service is healthy again

**Configuration:**
- **Graph API**: `fail_max=5`, `reset_timeout=60s` (conservative for critical email operations)
- **Azure OpenAI**: `fail_max=3`, `reset_timeout=30s` (aggressive, since failures are often systemic)
- **Azure Storage**: `fail_max=5`, `reset_timeout=45s` (moderate for file operations)

**Implementation Location:** `/src/shared/circuit_breaker.py`

**Decorator Pattern:**
```python
@with_circuit_breaker(graph_breaker)
def call_graph_api():
    # Graph API call here
```

## Rationale

- **Prevents cascade failures**: When Graph API is down, open circuit stops retries immediately
- **Faster failure detection**: Fail in <1s instead of 5-minute timeout
- **Resource efficiency**: No wasted retries during sustained outages
- **Cost reduction**: Fewer failed executions on Consumption plan
- **Graceful degradation**: Optional fallback functions for non-critical operations
- **Industry standard**: Circuit breaker is proven pattern from Netflix Hystrix, Spring Cloud
- **Simple integration**: Decorator pattern requires minimal code changes
- **Observable**: Circuit state tracked and exposed via health endpoint

**Why pybreaker:**
- Lightweight pure-Python library (no dependencies)
- Simple decorator-based API
- Configurable thresholds and timeouts
- Thread-safe for concurrent Function App instances
- Battle-tested in production systems

## Consequences

### Positive

- ✅ **Improved resilience**: System survives external service outages without cascade failure
- ✅ **Faster failure detection**: Sub-second failure response when circuit is open
- ✅ **Cost savings**: Reduced wasted execution time on failed retries
- ✅ **Better monitoring**: Circuit state provides clear signal of dependency health
- ✅ **Graceful degradation**: Optional fallbacks for non-critical operations (e.g., PDF extraction)
- ✅ **Simple integration**: Decorator pattern keeps business logic clean

### Negative

- ⚠️ **Additional complexity**: New failure mode to understand and monitor
- ⚠️ **Tuning required**: Thresholds must be calibrated based on actual traffic patterns
- ⚠️ **False positives**: Circuit may open during temporary bursts of errors
- ⚠️ **State management**: Circuit state is per-instance (not shared across scaled Function App instances)
- ⚠️ **Dependency**: Adds pybreaker library to requirements.txt

**Mitigations:**
- Start with conservative thresholds (5 failures) and tune based on production metrics
- Monitor circuit state in Application Insights to detect false positives
- Document threshold rationale and tuning guidelines
- Circuit state resets automatically after timeout, limiting blast radius
- Per-instance state is acceptable given Consumption plan's ephemeral nature

## Related

- [ADR-0001](0001-serverless-azure-functions.md) - Serverless Azure Functions (establishes external dependencies)
- [ADR-0006](0006-graph-api-for-email.md) - Graph API for Email Operations (key protected dependency)
- [ADR-0022](0022-pdf-vendor-extraction.md) - PDF Vendor Extraction (establishes OpenAI dependency)
- Implementation: `/src/shared/circuit_breaker.py`
- Tests: `/tests/unit/shared/test_circuit_breaker.py`
