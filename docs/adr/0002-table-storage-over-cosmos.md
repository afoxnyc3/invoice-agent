# ADR-0002: Table Storage over Cosmos DB

**Date:** 2024-11-09
**Status:** Accepted

## Context

Need database for vendor lookups and transaction logging. Expected <1000 vendors with simple key-value access patterns.

## Decision

Use Azure Table Storage for VendorMaster and InvoiceTransactions tables.

## Rationale

- Simple key-value lookups only
- <1000 vendors expected
- 100x cheaper than Cosmos DB (~$5/month vs $500/month)
- No complex queries or relationships needed
- Same storage account as blobs/queues

## Consequences

- ✅ Extremely cost-effective
- ✅ Simple to implement and maintain
- ⚠️ Limited query capabilities
- ⚠️ No server-side aggregations

## Related

- [ADR-0003: Storage Queues over Service Bus](0003-storage-queues-over-service-bus.md)
- [docs/ARCHITECTURE.md](../ARCHITECTURE.md) - Table schemas
