# ADR-0011: NetSuite Handles Approvals

**Date:** 2024-11-09
**Status:** Accepted

## Context

Approval workflow requirements for invoice processing. Options were to build custom approval in the system or leverage existing NetSuite workflows.

## Decision

Let NetSuite handle all approval logic. Invoice Agent only routes enriched invoices to AP.

## Rationale

- Existing, tested workflow in NetSuite
- Finance team already familiar with it
- Reduces scope by 50%
- Compliance already handled in NetSuite

## Consequences

- ✅ Faster MVP delivery
- ✅ Less complexity
- ✅ Proven approval process
- ⚠️ Dependency on NetSuite

## Related

- [ADR-0015: Email Routing over Direct API](0015-email-routing-to-ap.md)
- [ADR-0005: Simple Teams Webhooks Only](0005-simple-teams-webhooks.md)
