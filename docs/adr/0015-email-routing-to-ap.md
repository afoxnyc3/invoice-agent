# ADR-0015: Email Routing over Direct API

**Date:** 2024-11-09
**Status:** Accepted

## Context

Need to submit enriched invoices to AP system. Options were direct NetSuite API integration or email routing to AP mailbox.

## Decision

Send enriched email to AP mailbox rather than direct API integration.

## Rationale

- Maintains current workflow (AP already monitors mailbox)
- No NetSuite API integration needed
- Finance team can verify emails before processing
- Quick implementation

## Consequences

- ✅ Familiar process for AP team
- ✅ Human verification possible
- ⚠️ Not fully automated end-to-end
- ⚠️ Email delivery dependencies

## Related

- [ADR-0011: NetSuite Handles Approvals](0011-netsuite-handles-approvals.md)
- See `PostToAP/` function for implementation
