# ADR-0028: Message ID Deduplication

**Date:** 2024-11
**Status:** Accepted

## Context

Both webhook and timer paths could potentially process the same email. Graph API message IDs are unique and stable, making them suitable for deduplication.

## Decision

Use hash of Graph API message ID as RowKey in InvoiceTransactions table. Check for existing transaction before processing.

## Rationale

- Graph message IDs are globally unique
- Table Storage lookup is fast and cheap
- Prevents duplicate invoice processing
- Audit trail of all processed messages
- Works across webhook and timer paths

## Implementation

- `shared/deduplication.py`: Check and record message processing
- InvoiceTransactions table: MessageId stored with transaction
- RowKey: Hash of message ID (valid Table Storage characters)

```python
def is_already_processed(message_id: str) -> bool:
    # Check InvoiceTransactions table for existing entry
    row_key = hash_message_id(message_id)
    return table_client.get_entity(partition_key, row_key) is not None
```

## Consequences

- ✅ Prevents duplicate processing
- ✅ Fast lookup (Table Storage)
- ✅ Audit trail maintained
- ⚠️ Small storage cost for tracking
- ⚠️ Must handle race conditions (at-least-once delivery)

## Related

- [ADR-0027: Email Loop Prevention](0027-email-loop-prevention.md)
- [ADR-0007: ULID for Transaction IDs](0007-ulid-for-transaction-ids.md)
- See `shared/deduplication.py` for implementation
