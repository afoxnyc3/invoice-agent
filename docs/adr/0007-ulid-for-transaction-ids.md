# ADR-0007: ULID for Transaction IDs

**Date:** 2024-11-09
**Status:** Accepted

## Context

Need unique, sortable transaction identifiers for audit trail and log correlation. Options were GUID, timestamp-based IDs, or ULID.

## Decision

Use ULID (Universally Unique Lexicographically Sortable Identifier) for all transaction IDs.

## Rationale

- Sortable by creation time
- Globally unique
- URL-safe
- Includes timestamp information
- Better than GUID for log analysis

## Consequences

- ✅ Natural time ordering
- ✅ No ID collisions
- ✅ Human-readable in logs
- ⚠️ Additional dependency (`ulid-py`)

## Related

- [ADR-0028: Message ID Deduplication](0028-message-id-deduplication.md)
- See `shared/ulid_generator.py` for implementation
