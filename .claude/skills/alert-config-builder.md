# Alert Configuration Builder Skill

Creates Azure Monitor alert rules for duplicate invoice processing detection.

## Purpose
- Generate KQL queries for duplicate detection
- Create alert rule JSON for Azure Monitor
- Configure action groups for notifications
- Deploy alerts via Azure CLI

## Usage
Invoke when you need to:
- Set up monitoring alerts for duplicates
- Configure email/Teams notifications
- Adjust alert thresholds
- Test alert triggering

## Alert Definitions

### Alert 1: Duplicate Processing Detected
**Severity:** Warning (Sev 2)
**Threshold:** >5 duplicates in 1 hour
**Frequency:** Check every 15 minutes

**KQL Query:**
```kql
customEvents
| where timestamp > ago(1h)
| where name == "InvoiceTransaction"
| extend OriginalMessageId = tostring(customDimensions.OriginalMessageId)
| summarize ProcessingCount = count() by OriginalMessageId
| where ProcessingCount > 1
| summarize DuplicateCount = sum(ProcessingCount - 1)
| where DuplicateCount > 5
```

### Alert 2: High Duplicate Rate
**Severity:** Error (Sev 1)
**Threshold:** Duplicate rate >10% in 6 hours
**Frequency:** Check every 30 minutes

**KQL Query:**
```kql
customEvents
| where timestamp > ago(6h)
| where name == "InvoiceTransaction"
| summarize
    Total = count(),
    Duplicates = countif(tostring(customDimensions.Status) == "duplicate_skipped")
| extend DuplicateRate = (Duplicates * 100.0) / Total
| where DuplicateRate > 10
```

## Action Steps

### 1. Create Action Group
```bash
# Create action group for email notifications
az monitor action-group create \
  --name "ag-invoice-agent-duplicates" \
  --resource-group "rg-invoice-agent-prod" \
  --short-name "InvDupes" \
  --email-receiver name="DevTeam" email="dev-team@example.com"
```

### 2. Create Scheduled Query Alert Rule
```bash
# Create alert for duplicate processing
az monitor scheduled-query create \
  --name "Duplicate Invoice Processing Detected" \
  --resource-group "rg-invoice-agent-prod" \
  --scopes "/subscriptions/{sub}/resourceGroups/rg-invoice-agent-prod/providers/microsoft.insights/components/ai-invoice-agent-prod" \
  --condition "count > 5" \
  --condition-query "customEvents | where timestamp > ago(1h) | where name == 'InvoiceTransaction' | extend OriginalMessageId = tostring(customDimensions.OriginalMessageId) | summarize ProcessingCount = count() by OriginalMessageId | where ProcessingCount > 1 | summarize DuplicateCount = sum(ProcessingCount - 1)" \
  --description "Alerts when more than 5 duplicate invoices are processed within 1 hour" \
  --evaluation-frequency "15m" \
  --window-size "1h" \
  --severity 2 \
  --action-groups "/subscriptions/{sub}/resourceGroups/rg-invoice-agent-prod/providers/microsoft.insights/actionGroups/ag-invoice-agent-duplicates"
```

### 3. Test Alert (Simulate Duplicate)
```bash
# Query to verify alert condition would trigger
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "
    customEvents
    | where timestamp > ago(1h)
    | where name == 'InvoiceTransaction'
    | extend OriginalMessageId = tostring(customDimensions.OriginalMessageId)
    | summarize ProcessingCount = count() by OriginalMessageId
    | where ProcessingCount > 1
    | summarize DuplicateCount = sum(ProcessingCount - 1)
    | project DuplicateCount, AlertWouldTrigger = iff(DuplicateCount > 5, 'YES', 'NO')
  "
```

### 4. Create Dashboard Tile
Add tile to Application Insights workbook showing duplicate metrics:
```json
{
  "type": "Extension/Microsoft_OperationsManagementSuite_Workspace/PartType/LogsDashboardPart",
  "settings": {
    "content": {
      "Query": "customEvents | where timestamp > ago(7d) | where name == 'InvoiceTransaction' | extend OriginalMessageId = tostring(customDimensions.OriginalMessageId) | summarize ProcessingCount = count() by OriginalMessageId | where ProcessingCount > 1 | summarize DuplicateCount = count()",
      "Title": "Duplicate Invoices (Last 7 Days)"
    }
  }
}
```

## Alert Response Procedure

When alert fires:
1. **Acknowledge** - Respond to alert within 30 minutes
2. **Investigate** - Run `deduplication-analyzer` skill to identify source
3. **Assess Impact** - Check if AP received duplicate emails
4. **Remediate** - If duplicates reached AP, notify AP team
5. **Root Cause** - Determine if webhook failure or other issue
6. **Document** - Add incident to troubleshooting guide

## Validation Commands

```bash
# List all configured alerts
az monitor scheduled-query list \
  --resource-group "rg-invoice-agent-prod" \
  --output table

# Check alert status
az monitor scheduled-query show \
  --name "Duplicate Invoice Processing Detected" \
  --resource-group "rg-invoice-agent-prod"

# View alert history
az monitor activity-log list \
  --resource-group "rg-invoice-agent-prod" \
  --offset 7d \
  --query "[?contains(authorization.action, 'Microsoft.Insights/scheduledQueryRules')]"
```

## Success Criteria
- Alert deploys without errors
- Test query returns expected results
- Action group emails received
- Alert fires when threshold exceeded
- Response procedure documented
