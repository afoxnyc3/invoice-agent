# ADR-0021: Event-Driven Webhooks over Timer Polling

**Date:** 2024-11-20
**Status:** Accepted
**Supersedes:** [ADR-0012](0012-timer-trigger-polling.md)

## Context

Timer triggers proved unreliable on Consumption plan (AlwaysOn not available). The app would go idle and miss scheduled executions. Latency requirements also changed to <10 seconds.

## Decision

Migrate from timer-based polling to Microsoft Graph Change Notifications (webhooks) for email ingestion.

## Rationale

- **Real-time processing**: <10 seconds vs 5 minutes
- **Cost reduction**: 70% savings (~$0.60/month vs $2.00/month)
- **Reliability**: Webhooks don't depend on app being awake
- **Efficiency**: No unnecessary polling when no emails
- **Scalability**: Event-driven architecture handles thousands of emails/day
- **Industry best practice**: Standard approach for email/notification systems

## Implementation

- **MailWebhook**: HTTP endpoint receives Graph API change notifications
- **SubscriptionManager**: Timer function (every 6 days) renews subscriptions
- **MailIngest**: Retained as hourly fallback/safety net
- **GraphSubscriptions**: New table for subscription state management
- **New environment variables**: GRAPH_CLIENT_STATE, MAIL_WEBHOOK_URL

## Architecture Change

```
BEFORE: Timer(5 min) → Poll → Process (5 min latency, $2.00/month)
AFTER:  Email → Graph → HTTP POST → Queue → Process (<10s latency, $0.60/month)
```

## Consequences

- ✅ Real-time processing (<10s latency vs 5 min)
- ✅ 70% cost savings (1,500 vs 8,640 executions/month)
- ✅ No cold starts from unnecessary polling
- ✅ Scalable to thousands of emails/day
- ⚠️ Public HTTPS endpoint required (secured via client state validation)
- ⚠️ Webhook subscription must be renewed every 7 days (automated)
- ⚠️ More complex setup (subscription registration + secret management)

## Rollback Plan

1. Re-enable MailIngest timer: `0 */5 * * * *` (every 5 minutes)
2. Delete Graph subscription via SubscriptionManager or manually
3. Disable MailWebhook function

## Related

- **Supersedes:** [ADR-0012: Timer Trigger over Event-Based](0012-timer-trigger-polling.md)
- [docs/reports/WEBHOOK_MIGRATION_REPORT.md](../reports/WEBHOOK_MIGRATION_REPORT.md)
- [Microsoft Graph Change Notifications](https://learn.microsoft.com/en-us/graph/webhooks)
