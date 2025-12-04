# ADR-0003: Storage Queues over Service Bus

**Date:** 2024-11-09
**Status:** Accepted

## Context

Need messaging between functions for the invoice processing pipeline. Expected throughput is <100 messages/minute.

## Decision

Use Azure Storage Queues for all inter-function messaging.

## Rationale

- Same storage account (simpler permissions)
- Sufficient for <100 messages/minute
- Built-in Function bindings
- No advanced features needed (topics, sessions)
- 10x cheaper than Service Bus

## Consequences

- ✅ Simple integration
- ✅ Cost-effective
- ⚠️ 64KB message size limit
- ⚠️ No message ordering guarantees

## Related

- [ADR-0002: Table Storage over Cosmos DB](0002-table-storage-over-cosmos.md)
- Queue names: `raw-mail`, `to-post`, `notify`, `webhook-notifications`
