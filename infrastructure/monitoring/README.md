# Invoice Agent Monitoring Infrastructure

This directory contains monitoring and alerting infrastructure for the Invoice Agent production system.

## Contents

- **alerts.bicep** - Bicep template for alert rules and action groups
- **alerts.parameters.json** - Parameter file for alert deployment
- **dashboard.json** - Azure Dashboard definition (JSON)
- **invoice-agent-workbook.json** - Azure Monitor Workbook (detailed analytics)
- **deploy-monitoring.sh** - Deployment script for monitoring infrastructure
- **deploy_workbook.sh** - Script to deploy the workbook (in /scripts/)
- **README.md** - This file

## Quick Start

### 1. Deploy Alert Rules

Deploy all monitoring alerts to production:

```bash
./deploy-monitoring.sh --environment prod --email ops-team@company.com
```

With Teams webhook:

```bash
./deploy-monitoring.sh \
  --environment prod \
  --email ops-team@company.com \
  --teams-webhook "https://outlook.office.com/webhook/YOUR_WEBHOOK_URL"
```

With SMS alerts (optional):

```bash
./deploy-monitoring.sh \
  --environment prod \
  --email ops-team@company.com \
  --enable-sms \
  --sms-phone "+15551234567"
```

### 2. Deploy Dashboard

```bash
./deploy-monitoring.sh --environment prod --deploy-dashboard
```

### 3. Verify Deployment

Check deployed alerts in Azure Portal:
```
Azure Portal > Resource Groups > rg-invoice-agent-prod > Alerts
```

## Alert Rules Configured

### Metric Alerts
1. **High Error Rate** (P1) - Error rate >1% over 5 minutes
2. **High Queue Depth** (P2) - >100 messages in queue for >10 minutes
3. **Low Availability** (P0) - Function App availability <95%
4. **Storage Throttling** (P1) - Storage latency >1 second

### Log Analytics Alerts
5. **Function Execution Failures** (P1) - Any function failure
6. **Processing Latency** (P2) - >5 requests taking >60s in 15 minutes
7. **Poison Queue Messages** (P0) - Messages in dead-letter queue
8. **High Unknown Vendor Rate** (P2) - >10 unknown vendors in 1 hour

## Alert Severities

| Severity | Priority | Response Time | Description |
|----------|----------|---------------|-------------|
| P0 | Critical | Immediate | System down, data loss risk |
| P1 | High | <15 min | Degraded service, high error rates |
| P2 | Medium | <1 hour | Performance issues, warnings |

## Action Groups

Alerts are sent to action groups with these notification channels:
- **Email** - Configured email addresses
- **Teams Webhook** - Teams channel webhook (optional)
- **SMS** - Phone number for critical alerts (optional)

## Dashboard

The Azure Dashboard (`dashboard.json`) includes:
- Real-time performance metrics (request rate, latency)
- Error rate trends
- Queue depths visualization
- Vendor match rate chart
- Function health status
- Top 10 errors (last 24h)
- Top 10 unknown vendors

### Deploying Dashboard

Option 1: Using deployment script
```bash
./deploy-monitoring.sh --environment prod --deploy-dashboard
```

Option 2: Manual deployment via Azure CLI
```bash
# Replace {subscription-id} in dashboard.json first
az portal dashboard create \
  --name "dashboard-invoice-agent-prod" \
  --resource-group rg-invoice-agent-prod \
  --input-path dashboard.json \
  --location eastus
```

Option 3: Import via Azure Portal
1. Go to Azure Portal > Dashboards
2. Click "Upload"
3. Select `dashboard.json`
4. Save dashboard

## Workbook (Recommended)

The Azure Monitor Workbook (`invoice-agent-workbook.json`) provides more detailed analytics with interactive visualizations:

### Workbook Sections

| Section | Metrics |
|---------|---------|
| **Processing Overview** | Total processed, vendor match rate, avg processing time, error rate |
| **Function Performance** | Executions by function, avg/P95 duration, failure rates |
| **Queue Health** | Throughput by queue, poison queue messages |
| **Webhook vs Fallback** | Real-time webhook vs timer-based processing comparison |
| **Vendor Analytics** | Top 10 vendors, unknown vendors needing attention |
| **Recent Errors** | Exceptions and failed requests table |

### Deploying Workbook

```bash
# Deploy to production
../scripts/deploy_workbook.sh --env prod

# Deploy to dev
../scripts/deploy_workbook.sh --env dev
```

### Viewing the Workbook

After deployment:
1. Go to Azure Portal
2. Navigate to: Application Insights > ai-invoice-agent-prod > Workbooks
3. Open "Invoice Agent Operations"

The workbook has a time range picker (1h, 4h, 12h, 24h, 48h, 7d) for historical analysis.

## Configuration

### Updating Alert Thresholds

Edit `alerts.bicep` and modify threshold values:

```bicep
// Example: Change error rate threshold from 1% to 2%
threshold: 2  // Was: threshold: 1
```

Redeploy:
```bash
./deploy-monitoring.sh --environment prod --update-alerts
```

### Adding Email Recipients

Option 1: Script parameter
```bash
./deploy-monitoring.sh \
  --environment prod \
  --email ops@company.com \
  --email devops@company.com \
  --email oncall@company.com
```

Option 2: Edit `alerts.parameters.json`
```json
"alertEmailAddresses": {
  "value": [
    "ops@company.com",
    "devops@company.com"
  ]
}
```

Then deploy:
```bash
az deployment group create \
  --resource-group rg-invoice-agent-prod \
  --template-file alerts.bicep \
  --parameters alerts.parameters.json
```

### Teams Webhook Setup

1. In Microsoft Teams, go to desired channel
2. Click "..." > Connectors > Incoming Webhook
3. Configure webhook and copy URL
4. Deploy with webhook:

```bash
./deploy-monitoring.sh \
  --environment prod \
  --email ops@company.com \
  --teams-webhook "YOUR_WEBHOOK_URL"
```

## Cost Estimates

Monthly costs for monitoring infrastructure (approximate):

| Service | Component | Cost |
|---------|-----------|------|
| Application Insights | Log ingestion (1GB/day) | $2.30 |
| Application Insights | Retention (90 days) | $0.10 |
| Log Analytics | Log ingestion (1GB/day) | $2.76 |
| Alert Rules | 8 alert rules | $0.10 |
| Action Group | Email notifications | Free |
| Action Group | SMS (100 msgs/month) | $2.00 |
| Dashboard | Azure Portal dashboard | Free |
| **Total** | | **~$7.26/month** |

Note: Actual costs depend on log volume and alert frequency.

## Testing Alerts

### Test Alert Email

Manually trigger an alert to test notifications:

```bash
# Option 1: Cause a test failure (temporary)
az functionapp config appsettings set \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --settings "INVALID_SETTING=true"

# Wait for failure alert, then remove setting
az functionapp config appsettings delete \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --setting-names "INVALID_SETTING"
```

Option 2: Use Azure Monitor test notification
```bash
az monitor action-group test-notifications create \
  --action-group-name ag-invoice-agent-prod-ops \
  --resource-group rg-invoice-agent-prod
```

## Troubleshooting

### Alerts Not Firing

1. Check alert is enabled:
```bash
az monitor metrics alert show \
  --name alert-invoice-agent-prod-high-error-rate \
  --resource-group rg-invoice-agent-prod \
  --query "enabled"
```

2. Verify condition is met:
- Go to Application Insights > Metrics
- Chart the metric used in alert condition
- Confirm threshold is being crossed

3. Check action group:
```bash
az monitor action-group show \
  --name ag-invoice-agent-prod-ops \
  --resource-group rg-invoice-agent-prod
```

### Emails Not Received

1. Check spam/junk folder
2. Verify email address in action group
3. Check email receiver status:
```bash
az monitor action-group show \
  --name ag-invoice-agent-prod-ops \
  --resource-group rg-invoice-agent-prod \
  --query "emailReceivers"
```

### Dashboard Not Showing Data

1. Verify Application Insights is receiving data:
```bash
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "requests | where timestamp > ago(1h) | count"
```

2. Check dashboard queries have correct resource IDs
3. Update `{subscription-id}` placeholder in dashboard.json

## Maintenance

### Monthly Tasks
- Review alert thresholds based on actual system behavior
- Check for alert fatigue (too many false positives)
- Verify contact information is up to date
- Review cost reports

### Quarterly Tasks
- Update monitoring runbook with new scenarios
- Add new log queries based on team needs
- Review SLO targets and adjust if needed

## Related Documentation

- [Monitoring Guide](/Users/alex/dev/invoice-agent/docs/monitoring/MONITORING_GUIDE.md) - Alert response procedures and troubleshooting
- [Log Queries](/Users/alex/dev/invoice-agent/docs/monitoring/LOG_QUERIES.md) - Useful KQL queries for investigation

## Support

For monitoring infrastructure questions:
- **Deployment Issues:** DevOps team
- **Alert Configuration:** SRE team
- **Dashboard Customization:** Data/Analytics team

---

**Last Updated:** 2024-11-13
**Version:** 1.0.0
