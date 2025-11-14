# Disaster Recovery Guide

**Last Updated:** November 13, 2025

Complete disaster recovery procedures for Invoice Agent. This guide covers backup strategies, RTO/RPO, failover procedures, and recovery steps.

## Table of Contents
- [Recovery Objectives](#recovery-objectives)
- [Backup Strategy](#backup-strategy)
- [Testing DR Procedures](#testing-dr-procedures)
- [Regional Outage Recovery](#regional-outage-recovery)
- [Data Corruption Recovery](#data-corruption-recovery)
- [Service Failure Recovery](#service-failure-recovery)
- [Incident Response](#incident-response)

---

## Recovery Objectives

### RTO & RPO by Scenario

| Scenario | RTO | RPO | Severity |
|----------|-----|-----|----------|
| Single function failure | 5 min | 0 min | Low |
| Storage account unavailable | 30 min | 1 hour | Medium |
| Regional outage | 2 hours | 1 hour | High |
| Data corruption | 1 hour | 1 hour | Critical |
| Complete system loss | 4 hours | 24 hours | Critical |

**Key Definitions:**
- **RTO (Recovery Time Objective):** Time to restore service
- **RPO (Recovery Point Objective):** Maximum acceptable data loss

### Current Infrastructure

**Primary Region:** East US
**Backup Region:** None (manual failover only)
**Backup Storage:** Azure Backup

**Critical Assets:**
- VendorMaster table (vendor data)
- InvoiceTransactions table (audit log)
- Invoice blobs (PDF files)
- Function app code (GitHub)

---

## Backup Strategy

### VendorMaster Table Backup

**Frequency:** Daily at 2:00 AM UTC
**Retention:** 30 days minimum
**Location:** Backup storage account (`stinvoiceagentprod-backup`)

**Manual Backup:**
```bash
# Export VendorMaster table to CSV
az storage table download \
  --account-name stinvoiceagentprod \
  --name VendorMaster \
  --output table > vendor_backup_$(date +%Y%m%d_%H%M%S).csv

# Upload to backup storage
az storage blob upload \
  --account-name stinvoiceagentprodbackup \
  --container-name table-backups \
  --name "vendor_backup_$(date +%Y%m%d_%H%M%S).csv" \
  --file vendor_backup_*.csv
```

**Automated Backup (Script):**
```bash
#!/bin/bash
# Run daily via Azure Automation or cron

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="vendor_backup_${TIMESTAMP}.csv"

# Export table
az storage table download \
  --account-name stinvoiceagentprod \
  --name VendorMaster \
  --output table > "$BACKUP_FILE"

# Upload to backup storage
az storage blob upload \
  --account-name stinvoiceagentprodbackup \
  --container-name table-backups \
  --name "$BACKUP_FILE" \
  --file "$BACKUP_FILE"

# Clean up old backups (>30 days)
az storage blob delete-batch \
  --account-name stinvoiceagentprodbackup \
  --source table-backups \
  --daysago 30
```

### InvoiceTransactions Archive

**Frequency:** Daily at 3:00 AM UTC
**Retention:** 1 year
**Strategy:** Move old records to archive table

**Archive Procedure:**
```bash
#!/bin/bash
# Move invoices older than 30 days to archive

CUTOFF_DATE=$(date -d '30 days ago' +%Y%m%d)

# Query for old records (PartitionKey=YYYYMM format)
for partition in $(seq -w 0 $((CUTOFF_DATE - 202501))); do
  az storage entity delete-batch \
    --account-name stinvoiceagentprod \
    --table-name InvoiceTransactions \
    --partition-key "202${partition}" \
    --batch-size 100

  # Copy to archive before deleting
  az storage entity query \
    --account-name stinvoiceagentprod \
    --table-name InvoiceTransactions \
    --partition-key "202${partition}" \
    --select "*" \
    --output json | az storage entity insert-batch \
      --account-name stinvoiceagentprodarchive \
      --table-name InvoiceTransactions \
      --batch-operations
done
```

### Invoice Blob Backup

**Frequency:** Nightly via Azure Backup
**Retention:** 30 days
**Replication:** Geo-redundant storage (GRS)

**Verify Backup:**
```bash
# Check blob backup job status
az backup job list \
  --vault-name vault-invoice-agent \
  --resource-group rg-invoice-agent-prod \
  --status InProgress

# List recent backups
az backup container list \
  --vault-name vault-invoice-agent \
  --resource-group rg-invoice-agent-prod \
  --backupManagementType AzureStorage
```

### Code Backup (GitHub)

**Strategy:** GitHub is the source of truth
**Retention:** Infinite
**Procedure:**
```bash
# Clone for local archive (if GitHub unavailable)
git clone --mirror https://github.com/your-org/invoice-agent.git

# Upload to secure storage
az storage blob upload \
  --account-name stinvoiceagentprodbackup \
  --container-name code-backup \
  --name "invoice-agent.git.bundle" \
  --file invoice-agent.git.bundle
```

---

## Testing DR Procedures

### Monthly Backup Verification (30 minutes)

**Day:** First Monday of month, 10:00 AM
**Owner:** DevOps engineer

**Checklist:**
```bash
# 1. Verify latest VendorMaster backup exists
LATEST_BACKUP=$(az storage blob list \
  --account-name stinvoiceagentprodbackup \
  --container-name table-backups \
  --query "max_by(@, &properties.lastModified)" | jq -r '.name')

echo "Latest backup: $LATEST_BACKUP"
# Expected: File from within last 24 hours

# 2. Verify backup is readable
az storage blob download \
  --account-name stinvoiceagentprodbackup \
  --container-name table-backups \
  --name "$LATEST_BACKUP" \
  --file test_backup.csv

# Verify content
head test_backup.csv
# Should show CSV headers and vendor records

# 3. Verify invoice blob backup
az backup container show \
  --vault-name vault-invoice-agent \
  --name stinvoiceagentprod \
  --resource-group rg-invoice-agent-prod

# Expected: Shows successful backup point

# 4. Clean up test file
rm test_backup.csv
```

### Quarterly Recovery Drill (2 hours)

**Procedure:** Practice full recovery in dev environment

```bash
# 1. Create test recovery environment
az resource group create \
  --name rg-invoice-agent-dr-test \
  --location eastus

# 2. Restore VendorMaster from backup
BACKUP_FILE="vendor_backup_20251113_020000.csv"

az storage blob download \
  --account-name stinvoiceagentprodbackup \
  --container-name table-backups \
  --name "$BACKUP_FILE" \
  --file backup.csv

# 3. Create new table in test environment
az storage table create \
  --account-name stinvoiceagentdev \
  --name VendorMasterRestore

# 4. Restore data from CSV
python3 infrastructure/scripts/restore_vendors.py \
  --file backup.csv \
  --account stinvoiceagentdev \
  --table VendorMasterRestore

# 5. Verify restore
az storage entity query \
  --account-name stinvoiceagentdev \
  --table-name VendorMasterRestore \
  --select "RowKey,VendorName" | wc -l

# Expected: Same count as production

# 6. Test with functions in dev
# Deploy functions to dev, verify they work with restored data

# 7. Document results
echo "DR Test $(date): SUCCESS - Restored X vendors" >> dr_test_log.txt

# 8. Clean up test resources
az resource group delete \
  --name rg-invoice-agent-dr-test \
  --yes
```

---

## Regional Outage Recovery

**Scenario:** East US region becomes unavailable (5% probability/year)

**Detection:**
```bash
# Azure will alert automatically to #invoice-agent-incidents

# Verify outage
az functionapp show \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod

# If 503/unreachable: Regional outage confirmed
```

### Recovery Steps (RTO: 2 hours)

**Step 1: Activate Failover** (30 minutes)

Since we don't have pre-deployed standby, we'll rebuild in secondary region:

```bash
SECONDARY_REGION="westus2"

# 1. Create resource group in secondary region
az resource group create \
  --name rg-invoice-agent-failover \
  --location $SECONDARY_REGION

# 2. Deploy infrastructure from Bicep
az deployment group create \
  --resource-group rg-invoice-agent-failover \
  --template-file infrastructure/bicep/main.bicep \
  --parameters environment=failover region=$SECONDARY_REGION

# 3. Deploy functions
cd src
func azure functionapp publish func-invoice-agent-failover \
  --python \
  --remote-build

# 4. Restore vendor data
BACKUP_FILE="vendor_backup_latest.csv"
az storage blob download \
  --account-name stinvoiceagentprodbackup \
  --container-name table-backups \
  --name "$BACKUP_FILE" \
  --file backup.csv

# Restore to failover environment
python3 ../infrastructure/scripts/restore_vendors.py \
  --file backup.csv \
  --account stinvoiceagentfailover \
  --table VendorMaster
```

**Step 2: Restore Data** (30 minutes)

```bash
# 1. Restore queued messages (if not lost)
# Messages in queue are replicated, should be available

# 2. Restore invoice blobs (if not lost)
# GRS replication should have data

# 3. Verify critical data
az storage entity query \
  --account-name stinvoiceagentfailover \
  --table-name VendorMaster \
  --select "RowKey" | wc -l
# Should match production count
```

**Step 3: Validate Failover** (30 minutes)

```bash
# 1. Test API endpoint
FAILOVER_URL=$(az functionapp show \
  --name func-invoice-agent-failover \
  --resource-group rg-invoice-agent-failover \
  --query "hostNames[0]" -o tsv)

curl -X POST https://$FAILOVER_URL/api/AddVendor \
  -H "Content-Type: application/json" \
  -d '{
    "vendor_name": "Test Failover",
    "vendor_domain": "failover-test.com",
    "expense_dept": "IT",
    "gl_code": "9999",
    "allocation_schedule": "MONTHLY",
    "billing_party": "Test"
  }'

# Expected: 201 Created

# 2. Monitor failover environment
az functionapp log tail \
  --name func-invoice-agent-failover \
  --resource-group rg-invoice-agent-failover

# Watch for normal operation
```

**Step 4: Switch Traffic** (5 minutes)

```bash
# 1. Update DNS/load balancer (if applicable)
# Point invoice-agent.company.com to failover region

# 2. Update any hardcoded URLs in clients
# If mailbox routing uses specific endpoint

# 3. Notify stakeholders
# Slack: We're running in failover region (westus2)
# ETA to return to primary: 1-2 hours
```

**Step 5: Failback to Primary** (30 minutes)

Once primary region recovered:

```bash
# 1. Verify primary region is healthy
az functionapp show \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "state"  # Should be "Running"

# 2. Sync any data written during failover
# Export from failover environment
az storage entity query \
  --account-name stinvoiceagentfailover \
  --table-name InvoiceTransactions \
  --filter "UpdatedAt gt datetime'2025-11-13T14:30:00Z'" \
  --select "*" > failover_updates.json

# 3. Import to primary
# Careful not to overwrite newer data in primary

# 4. Switch traffic back
# Update DNS to point to primary region

# 5. Monitor primary
az functionapp log tail \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod

# 6. Decommission failover
az resource group delete \
  --name rg-invoice-agent-failover \
  --yes
```

---

## Data Corruption Recovery

**Scenario:** VendorMaster table corrupted (bad data, missing records)

**Detection:**
```bash
# Unknown vendor rate suddenly spikes (>50%)
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "
    customEvents
    | where name == 'VendorNotFound'
    | where timestamp > ago(1h)
    | summarize count()
  "

# If >100 in 1 hour: Investigate corruption
```

**Recovery:** (RTO: 1 hour)

```bash
# 1. Stop processing immediately
az functionapp stop \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod

# Prevents writing more bad data

# 2. Identify corruption
az storage entity query \
  --account-name stinvoiceagentprod \
  --table-name VendorMaster \
  --select "RowKey,VendorName,GLCode" | head -20

# Look for: empty fields, invalid GL codes, etc.

# 3. Restore from backup
BACKUP_FILE="vendor_backup_20251113_020000.csv"

# Delete corrupted table
az storage table delete \
  --account-name stinvoiceagentprod \
  --name VendorMaster

# Recreate table
az storage table create \
  --account-name stinvoiceagentprod \
  --name VendorMaster

# Restore from backup
python3 infrastructure/scripts/restore_vendors.py \
  --file backup.csv \
  --account stinvoiceagentprod \
  --table VendorMaster

# 4. Verify restore
az storage entity query \
  --account-name stinvoiceagentprod \
  --table-name VendorMaster \
  --select "RowKey,VendorName,GLCode" | wc -l

# Count should match backup

# 5. Investigate cause
# Check logs for what caused corruption
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "
    requests
    | where name == 'AddVendor'
    | where timestamp > ago(1h)
    | where success == false
  "

# 6. Restart functions
az functionapp start \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod

# 7. Monitor for issues
az functionapp log tail \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --timeout 300  # Monitor for 5 minutes
```

---

## Service Failure Recovery

### Function App Crashes

**Symptom:** All functions returning 500, app logs empty

```bash
# 1. Check app status
az functionapp show \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "state"

# If "Stopped" or "Unknown": Restart
az functionapp start \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod

# 2. Monitor recovery
az functionapp log tail \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --timeout 60

# 3. If restart doesn't fix, redeploy
func azure functionapp publish func-invoice-agent-prod \
  --slot staging \
  --python \
  --remote-build

# Then swap
az functionapp deployment slot swap \
  --name func-invoice-agent-prod \
  --slot staging \
  --resource-group rg-invoice-agent-prod
```

### Storage Account Unavailable

**Symptom:** 403 Forbidden on all storage operations

```bash
# 1. Check storage account status
az storage account show \
  --name stinvoiceagentprod \
  --query "provisioningState"

# 2. Verify connection string
az storage account show-connection-string \
  --name stinvoiceagentprod

# 3. If corrupted, failover to GRS copy
# (Pre-configured with Azure Backup)

# 4. Restore from backup storage
az storage account copy \
  --source-account stinvoiceagentprodbackup \
  --destination-account stinvoiceagentprod

# 5. Update function app settings
NEW_CONN=$(az storage account show-connection-string \
  --name stinvoiceagentprod -o tsv)

az functionapp config appsettings set \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --settings AzureWebJobsStorage="$NEW_CONN"
```

---

## Incident Response

### Incident Communication Template

**Slack Message (Immediately):**
```
🚨 INCIDENT: Invoice Agent Degraded

Status: Active Investigation
Severity: [CRITICAL|HIGH|MEDIUM|LOW]
Impact: [Services affected]
ETA: [Estimated recovery time]
Lead: [Name]

Details:
- What: [What happened]
- When: [When discovered]
- Impact: [How many invoices affected]

Updates: Check thread for updates every 15 minutes
```

### Post-Incident Review (Within 24 hours)

**Checklist:**
- [ ] Incident resolved successfully
- [ ] Root cause identified
- [ ] Fix implemented to prevent recurrence
- [ ] Documentation updated
- [ ] Team debriefing scheduled
- [ ] Follow-up items assigned

**Review Template:**
```markdown
# Incident: [Title]

**Timeline:**
- 14:30 UTC: Issue detected
- 14:35 UTC: On-call engaged
- 14:50 UTC: Root cause identified (storage timeout)
- 15:10 UTC: Failover activated
- 15:20 UTC: Service restored

**Root Cause:**
Storage account hit throughput limit due to spike in ExtractEnrich queries

**Impact:**
- 45 minutes downtime
- ~150 invoices queued but not lost
- No data corruption

**Fix:**
- Increased storage account throughput limits
- Added caching to reduce queries (prevent recurrence)

**Prevention:**
- Add alert for storage throttling
- Implement circuit breaker pattern
- Load test for 500 invoices/day scenario

**Action Items:**
- [ ] Implement caching (Engineer X, due Nov 20)
- [ ] Add alert for storage (Engineer Y, due Nov 15)
- [ ] Load test (QA, due Dec 1)
```

---

## Runbook Quick Reference

### Complete Data Loss Recovery

```bash
# Worst case: Everything lost, recover from backups only

# 1. Create new resource group
az resource group create --name rg-invoice-agent-recover --location eastus

# 2. Deploy infrastructure
az deployment group create \
  --resource-group rg-invoice-agent-recover \
  --template-file infrastructure/bicep/main.bicep

# 3. Restore vendor data
python infrastructure/scripts/restore_vendors.py \
  --file vendor_backup_20251113.csv \
  --account stinvoiceagentrecover

# 4. Deploy function code
func azure functionapp publish func-invoice-agent-recover --python

# 5. Restore invoice blobs (from Azure Backup)
# Or reprocess from email if backups unavailable

# 6. Validate
curl https://func-invoice-agent-recover.azurewebsites.net/api/AddVendor

# 7. Switch to recovery environment
# Update DNS, mailbox routing, etc.
```

**Time to Complete:** 4 hours
**Data Loss:** 24 hours of invoices (if no email backup)

---

## Checklist

**For Operations Team:**
- [ ] Backup procedure documented and tested
- [ ] Recovery runbooks available and current
- [ ] On-call team trained on recovery
- [ ] DR contacts established and published
- [ ] Disaster recovery plan reviewed quarterly
- [ ] Annual DR test scheduled

---

**See Also:**
- [Rollback Procedure](ROLLBACK_PROCEDURE.md) - Rolling back deployments
- [Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md) - Diagnosing issues
- [Operations Playbook](OPERATIONS_PLAYBOOK.md) - Backup verification procedures
