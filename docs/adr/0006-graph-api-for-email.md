# ADR-0006: Graph API for Email Operations

**Date:** 2024-11-09
**Status:** Accepted

## Context

Need to read incoming emails and send enriched emails to AP. Options were Graph API, SMTP/IMAP, or Exchange Web Services.

## Decision

Use Microsoft Graph API for all email operations (read and send).

## Rationale

- Single API for both operations
- Native Azure AD integration
- Better than SMTP/IMAP for modern M365
- Supports modern authentication
- Rich email metadata access

## Consequences

- ✅ Unified authentication
- ✅ Rich email metadata
- ⚠️ Rate limiting considerations
- ⚠️ Requires app registration

## Related

- [ADR-0021: Event-Driven Webhooks](0021-event-driven-webhooks.md)
- [ADR-0010: Managed Identity for All Auth](0010-managed-identity-auth.md)
- See `shared/graph_client.py` for implementation
