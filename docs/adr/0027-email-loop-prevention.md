# ADR-0027: Email Loop Prevention

**Date:** 2024-11
**Status:** Accepted

## Context

The system sends enriched emails to AP mailboxes. If those AP emails were forwarded back to the invoice mailbox, it could create infinite processing loops, causing runaway costs and duplicate invoices.

## Decision

Check sender against allowed AP emails list before processing. Skip emails from known system addresses.

## Rationale

- Prevents infinite processing loops
- Protects against runaway costs
- Simple allowlist approach
- Explicit configuration is safer than heuristics

## Implementation

- `shared/config.py`: `allowed_ap_emails` configuration
- `shared/email_processor.py`: Check sender before processing
- Environment variable: `ALLOWED_AP_EMAILS` (comma-separated list)

```python
if sender_email.lower() in config.allowed_ap_emails:
    logging.info(f"Skipping email from system address: {sender_email}")
    return
```

## Consequences

- ✅ Prevents infinite loops
- ✅ Protects against cost explosions
- ✅ Simple, explicit configuration
- ⚠️ Must update config when AP addresses change
- ⚠️ Could accidentally skip legitimate emails if misconfigured

## Related

- [ADR-0028: Message ID Deduplication](0028-message-id-deduplication.md)
- See `shared/email_processor.py` for implementation
