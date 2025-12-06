# 0033. Schema Versioning Strategy

**Date:** 2024-12-05
**Status:** Accepted

## Context

Queue messages flow between Azure Functions in a loosely-coupled pipeline:
- **MailWebhookProcessor** → `raw-mail` queue → **ExtractEnrich**
- **ExtractEnrich** → `to-post` queue → **PostToAP**
- **PostToAP** → `notify` queue → **Notify**

During deployments using the slot swap pattern, there is a brief window where:
1. **Old version** (production slot) is still processing messages
2. **New version** (staging slot) is validating and warming up
3. **In-flight messages** in queues may have been created by old version
4. **Schema changes** in Pydantic models could break message processing

**Current Problem:**
- **RawMail**, **EnrichedInvoice**, **NotificationMessage** models have no version field
- Adding new optional fields is safe (Pydantic ignores unknown fields in strict mode)
- Adding new required fields breaks old messages already in queues
- Changing field types or validation rules causes validation errors
- No way to detect schema version of in-flight messages

**Real-World Scenario:**
```
T0: Deploy new ExtractEnrich with required field "invoice_amount"
T1: MailWebhookProcessor (old version) queues message without "invoice_amount"
T2: ExtractEnrich (new version) dequeues message → ValidationError: Field required
T3: Message retries 3 times, moves to poison queue
```

This breaks processing until all in-flight messages are drained or manually reprocessed.

## Decision

Add a `schema_version` field to all Pydantic queue message models with:
- **Type**: String (semantic version format: "1.0", "1.1", "2.0")
- **Default**: "1.0" (current baseline)
- **Location**: All models in `/src/shared/models.py` (RawMail, EnrichedInvoice, NotificationMessage)
- **Validation**: Version-aware processing with backward compatibility

**Example:**
```python
class RawMail(BaseModel):
    schema_version: str = Field(default="1.0", description="Message schema version")
    id: str = Field(...)
    sender: EmailStr = Field(...)
    # ... other fields
```

**Processing Pattern:**
```python
def process_message(message: dict):
    version = message.get("schema_version", "1.0")  # Default to 1.0 for old messages

    if version == "1.0":
        # Process with original schema
        parsed = RawMail(**message)
    elif version == "1.1":
        # Process with new optional fields
        parsed = RawMailV1_1(**message)
    else:
        raise ValueError(f"Unsupported schema version: {version}")
```

## Rationale

- **Non-breaking deployments**: New code can detect and handle old message versions
- **Gradual rollout**: Schema changes can be deployed incrementally without breaking in-flight messages
- **Explicit compatibility**: Version field makes schema evolution deliberate and documented
- **Debugging aid**: Logs and error messages can show which schema version failed
- **Future-proof**: Enables major schema changes (v2.0) with clean migration path
- **Industry standard**: Message versioning is common practice in event-driven systems (Kafka, RabbitMQ)

**Why semantic versioning:**
- **Major version (1.0 → 2.0)**: Breaking changes, incompatible schema
- **Minor version (1.0 → 1.1)**: New optional fields, backward compatible
- **Default "1.0"**: All existing messages without version field are treated as v1.0

**Why string over int:**
- More expressive: "1.1" vs 11
- Matches semantic versioning convention
- Easy to parse and compare: `version.startswith("1.")`

## Consequences

### Positive

- ✅ **Non-breaking deployments**: Old messages processed during slot swap don't fail validation
- ✅ **Schema evolution**: Can add optional fields in minor versions without breaking changes
- ✅ **Clear migration path**: Major version changes (v2.0) can coexist during transition
- ✅ **Better debugging**: Error logs show which schema version failed validation
- ✅ **Test coverage**: Can test backward compatibility with old message fixtures
- ✅ **No coordination required**: Functions can be deployed independently without message draining

### Negative

- ⚠️ **Increased complexity**: Must maintain version-aware parsing logic for multiple schema versions
- ⚠️ **Code duplication**: Multiple model versions may coexist during transition periods
- ⚠️ **Testing burden**: Must test all supported schema versions (1.0, 1.1, etc.)
- ⚠️ **Version sprawl**: Old versions must be maintained until all in-flight messages drained
- ⚠️ **Documentation overhead**: Schema changes must document version increments

**Mitigations:**
- Start with single version "1.0" for all current messages (no immediate complexity)
- Only increment version when schema actually changes (not on every deployment)
- Deprecate old versions after 7 days (queue TTL ensures no old messages remain)
- Use automated tests to validate backward compatibility
- Document version history in model docstrings

**Deprecation Policy:**
- **Minor versions**: Maintain for 30 days (2 sprint cycles)
- **Major versions**: Maintain for 90 days (6 sprint cycles)
- **Sunset procedure**: Log warnings when old versions processed, remove after retention period

## Related

- [ADR-0020](0020-blue-green-deployments.md) - Blue-Green Deployments (establishes slot swap pattern)
- [ADR-0023](0023-slot-swap-resilience.md) - Slot Swap Resilience (motivates version compatibility)
- [ADR-0003](0003-storage-queues-over-service-bus.md) - Storage Queues (establishes queue-based decoupling)
- Implementation: `/src/shared/models.py` (RawMail, EnrichedInvoice, NotificationMessage)
- Tests: `/tests/unit/shared/test_models.py` (add version compatibility tests)
