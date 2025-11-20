# Invoice Agent Automation Scripts

Comprehensive automation scripts for testing, monitoring, and troubleshooting the Invoice Agent system.

## Table of Contents

- [Overview](#overview)
- [Scripts](#scripts)
  - [health-check.sh](#health-checksh)
  - [collect-logs.sh](#collect-logssh)
  - [validate-deployment.sh](#validate-deploymentsh)
  - [performance-test.sh](#performance-testsh)
- [Prerequisites](#prerequisites)
- [Usage Examples](#usage-examples)
- [Integration with CI/CD](#integration-with-cicd)
- [Troubleshooting](#troubleshooting)

---

## Overview

These automation scripts provide turnkey solutions for common operational tasks:

- **Health Checking:** Validate system health across all components
- **Log Collection:** Gather comprehensive logs for troubleshooting
- **Deployment Validation:** Verify deployments before production traffic
- **Performance Testing:** Measure system performance under load

All scripts are designed to:
- Run non-destructively (read-only by default)
- Provide clear, actionable output
- Exit with appropriate status codes for automation
- Generate detailed reports for auditing

---

## Scripts

### health-check.sh

**Purpose:** Comprehensive health check across all Invoice Agent components

**Features:**
- Validates Azure authentication
- Checks resource group and all resources
- Verifies Function App state and function count
- Validates application settings
- Checks storage account (tables, queues, blobs)
- Monitors queue depths and poison queues
- Verifies VendorMaster data
- Checks Application Insights connectivity
- Validates recent function executions

**Usage:**

```bash
# Check production environment
./health-check.sh --environment prod

# Check with verbose output
./health-check.sh --environment prod --verbose

# Default (production)
./health-check.sh
```

**Exit Codes:**
- `0` - All checks passed (healthy)
- `1` - Warnings present (degraded)
- `2` - Failures present (unhealthy)

**Output:**

```
╔═══════════════════════════════════════════════════════════════╗
║       Invoice Agent Health Check - PROD Environment          ║
╚═══════════════════════════════════════════════════════════════╝
Timestamp: 2025-11-19 14:30:00 UTC

═══════════════════════════════════════════════════════════════
 1. Azure Authentication
═══════════════════════════════════════════════════════════════
✅ PASS: Azure CLI authenticated as user@company.com

═══════════════════════════════════════════════════════════════
 2. Resource Group
═══════════════════════════════════════════════════════════════
✅ PASS: Resource group exists: rg-invoice-agent-prod
✅ PASS: Expected resources present (minimum 4)

[... more checks ...]

═══════════════════════════════════════════════════════════════
 Health Check Summary
═══════════════════════════════════════════════════════════════

  ✅ Passed:  25
  ⚠️  Warnings: 0
  ❌ Failed:  0

Overall Status: HEALTHY
```

**Automated Usage:**

```bash
# Run health check and alert on failure
./health-check.sh --environment prod
if [ $? -ne 0 ]; then
    echo "Health check failed" | mail -s "ALERT: Invoice Agent Unhealthy" ops@company.com
fi

# Schedule with cron (every 15 minutes)
*/15 * * * * /path/to/health-check.sh --environment prod >> /var/log/invoice-agent-health.log 2>&1
```

---

### collect-logs.sh

**Purpose:** Collect comprehensive logs and telemetry for troubleshooting

**Features:**
- Gathers system information
- Collects Application Insights logs (requests, exceptions, traces, dependencies)
- Analyzes errors and generates summaries
- Captures queue status and poison queue messages
- Exports table storage data
- Collects performance metrics
- Creates compressed archive for easy sharing

**Usage:**

```bash
# Collect last 24 hours of logs (default)
./collect-logs.sh --environment prod

# Collect last 48 hours
./collect-logs.sh --hours 48 --environment prod

# Custom output directory
./collect-logs.sh --output-dir /tmp/my-logs

# Skip poison queue collection (faster)
./collect-logs.sh --no-poison-queues

# Skip error analysis (faster)
./collect-logs.sh --no-analysis
```

**Output Structure:**

```
/tmp/invoice-agent-logs-20251119-143000/
├── 00-system-info.txt           # System and resource info
├── 01-requests.txt              # All requests from App Insights
├── 02-exceptions.txt            # All exceptions
├── 03-traces.txt                # Structured logs
├── 04-dependencies.txt          # External call logs
├── 05-custom-events.txt         # Business events
├── 10-error-summary.txt         # Error analysis
├── 11-top-errors.txt            # Most common errors
├── 12-unknown-vendors.txt       # Unknown vendor list
├── 20-queue-status.txt          # Queue depths
├── 21-poison-raw-mail.json      # Poison queue messages (if any)
├── 30-recent-transactions.txt   # Recent InvoiceTransactions
├── 31-vendor-master.txt         # Vendor list
├── 40-performance-metrics.txt   # Performance stats
└── 50-app-settings.txt          # App settings (sanitized)
```

**Compressed Archive:**

```
/tmp/invoice-agent-logs-prod-20251119-143000.tar.gz
```

**Example:**

```bash
# Collect logs and email to support
./collect-logs.sh --environment prod
TARBALL=$(ls -t /tmp/invoice-agent-logs-prod-*.tar.gz | head -1)
echo "Logs attached" | mail -s "Invoice Agent Logs" -a "$TARBALL" support@company.com
```

---

### validate-deployment.sh

**Purpose:** Validate deployment after slot swap or new release

**Features:**
- Waits for Function App to be ready
- Verifies function count (5 expected)
- Tests HTTP endpoints
- Validates application settings
- Tests function execution (smoke test)
- Checks Application Insights connectivity
- Verifies storage connectivity
- Checks for immediate errors
- Validates timer trigger configuration

**Usage:**

```bash
# Validate production deployment
./validate-deployment.sh --environment prod

# Validate staging slot before swap
./validate-deployment.sh --environment prod --slot staging

# Custom timeout (default: 300 seconds)
./validate-deployment.sh --timeout 600
```

**Exit Codes:**
- `0` - Deployment validated (ready for traffic)
- `1` - Deployment validation failed (issues detected)

**Output:**

```
╔═══════════════════════════════════════════════════════════════╗
║          Invoice Agent Deployment Validation                 ║
╚═══════════════════════════════════════════════════════════════╝

Environment: prod
Slot: staging
Validation started: 2025-11-19 14:30:00

1. Waiting for Function App to be ready...
  ✅ Function App is running

2. Verifying deployed functions...
  ✅ All 5 functions deployed (MailIngest, ExtractEnrich, PostToAP, Notify, AddVendor)

[... more checks ...]

═══════════════════════════════════════════════════════════════
 Deployment Validation Summary
═══════════════════════════════════════════════════════════════

  ✅ Checks Passed:  10
  ❌ Checks Failed:  0

✅ DEPLOYMENT VALIDATION PASSED

The deployment is healthy and ready for traffic.

╔═══════════════════════════════════════════════════════════════╗
║                 Ready to Swap to Production                  ║
╚═══════════════════════════════════════════════════════════════╝

To swap staging to production, run:

  az functionapp deployment slot swap \
    --name func-invoice-agent-prod \
    --resource-group rg-invoice-agent-prod \
    --slot staging \
    --target-slot production
```

**CI/CD Integration:**

```yaml
# GitHub Actions example
- name: Validate Staging Deployment
  run: |
    ./scripts/automation/validate-deployment.sh --environment prod --slot staging
    if [ $? -ne 0 ]; then
      echo "::error::Deployment validation failed"
      exit 1
    fi

- name: Swap to Production
  run: |
    az functionapp deployment slot swap \
      --name func-invoice-agent-prod \
      --resource-group rg-invoice-agent-prod \
      --slot staging \
      --target-slot production

- name: Validate Production
  run: |
    sleep 30  # Wait for swap to complete
    ./scripts/automation/validate-deployment.sh --environment prod
```

---

### performance-test.sh

**Purpose:** Measure system performance under load

**Features:**
- Generates concurrent test load
- Monitors real-time processing
- Collects detailed performance metrics
- Calculates throughput and latency
- Analyzes error rates
- Generates performance report
- Validates against SLO targets

**Usage:**

```bash
# Test with 10 concurrent invoices (default)
./performance-test.sh --environment prod

# Test with custom concurrency
./performance-test.sh --concurrent 50

# Test dev environment
./performance-test.sh --environment dev --concurrent 5
```

**Exit Codes:**
- `0` - Performance test passed (meets SLO targets)
- `1` - Performance test failed (does not meet targets)

**SLO Targets:**
- Average latency: <60 seconds per invoice
- Error rate: <1%
- Throughput: >0.1 invoices/second

**Output:**

```
╔═══════════════════════════════════════════════════════════════╗
║         Invoice Agent Performance Testing                    ║
╚═══════════════════════════════════════════════════════════════╝

Environment: prod
Concurrent invoices: 10
Output directory: /tmp/invoice-agent-perf-20251119-143000

Test started: 2025-11-19T14:30:00Z

1. Capturing baseline metrics...
   Queue depths (before):
     raw-mail: 0 messages
     to-post: 0 messages
     notify: 0 messages
   Transactions (before): 47

2. Generating test load (10 concurrent invoices)...
   Sent test invoice 1 (01TEST1732032600001)
   Sent test invoice 2 (01TEST1732032600002)
   [...]
   ✅ All 10 test invoices queued

3. Monitoring processing...
   [0 s] Queues: raw=10, post=0, notify=0 | Transactions: 0/10
   [10 s] Queues: raw=5, post=3, notify=2 | Transactions: 2/10
   [20 s] Queues: raw=0, post=1, notify=4 | Transactions: 5/10
   [30 s] Queues: raw=0, post=0, notify=0 | Transactions: 10/10

   ✅ All invoices processed!

Processing completed in 35 seconds

[... performance metrics ...]

╔═══════════════════════════════════════════════════════════════╗
║           Performance Test Complete                          ║
╚═══════════════════════════════════════════════════════════════╝

Summary:
  Total Time: 35 seconds
  Throughput: 0.29 invoices/second
  Avg Latency: 3.5 seconds
  Error Rate: 0.00%

Full report: /tmp/invoice-agent-perf-20251119-143000/performance-report.txt

✅ Performance test PASSED
```

**Report Contents:**

```
Invoice Agent Performance Test Report
======================================

Test Configuration:
  Environment: prod
  Concurrent Invoices: 10
  Start Time: 2025-11-19T14:30:00Z
  Test Duration: 35 seconds

Results:
  Throughput: 0.29 invoices/second
  Average Latency: 3.5 seconds per invoice
  Total Processed: 10 invoices
  Error Count: 0
  Error Rate: 0.00%

Performance Metrics by Function:
---------------------------------
operation_Name     Count  AvgDuration  P50Duration  P95Duration  SuccessRate
-----------------  -----  -----------  -----------  -----------  -----------
MailIngest         10     2.1          2.0          2.5          100.00
ExtractEnrich      10     1.8          1.7          2.2          100.00
PostToAP           10     8.5          8.2          9.5          100.00
Notify             10     1.2          1.1          1.5          100.00

Assessment:
  ✅ Latency: PASS (<60s target)
  ✅ Error Rate: PASS (<1% target)
  ✅ Throughput: PASS (>0.1 invoices/sec)
```

---

## Prerequisites

### Required Tools

```bash
# Azure CLI (minimum version 2.50.0)
az --version

# jq (JSON processor)
jq --version

# curl
curl --version

# bc (calculator, for performance-test.sh)
bc --version
```

### Installation

```bash
# macOS (Homebrew)
brew install azure-cli jq bc

# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y azure-cli jq bc

# RHEL/CentOS
sudo yum install -y azure-cli jq bc
```

### Azure Authentication

```bash
# Login to Azure
az login

# Set subscription
az account set --subscription "YOUR_SUBSCRIPTION_ID"

# Verify
az account show
```

### Environment Variables

```bash
# Optional: Set default environment
export INVOICE_AGENT_ENV="prod"

# Scripts will use this if --environment not specified
```

---

## Usage Examples

### Daily Operations

**Morning Health Check:**

```bash
# Check system health at start of day
./health-check.sh --environment prod --verbose | tee /var/log/morning-health-check.log

# If issues found, collect logs
if [ $? -ne 0 ]; then
    ./collect-logs.sh --environment prod
fi
```

**Pre-Deployment Validation:**

```bash
# Validate staging before swap
./validate-deployment.sh --environment prod --slot staging

# If passed, swap to production
if [ $? -eq 0 ]; then
    az functionapp deployment slot swap \
      --name func-invoice-agent-prod \
      --resource-group rg-invoice-agent-prod \
      --slot staging \
      --target-slot production

    # Validate production
    sleep 30
    ./validate-deployment.sh --environment prod
fi
```

**Weekly Performance Baseline:**

```bash
# Run performance test weekly to establish baseline
./performance-test.sh --concurrent 10 --environment prod

# Archive results
cp /tmp/invoice-agent-perf-*/performance-report.txt \
   /var/log/weekly-performance/perf-$(date +%Y%m%d).txt
```

### Incident Response

**Issue Reported - Gather All Information:**

```bash
# 1. Quick health check
./health-check.sh --environment prod

# 2. Collect comprehensive logs
./collect-logs.sh --hours 48 --environment prod

# 3. Package and send to engineer
LOGS=$(ls -t /tmp/invoice-agent-logs-prod-*.tar.gz | head -1)
echo "Incident logs attached" | mail -s "Invoice Agent Incident" -a "$LOGS" oncall@company.com
```

**Performance Degradation Investigation:**

```bash
# Collect logs with extended history
./collect-logs.sh --hours 72 --environment prod

# Run performance test to compare current vs. baseline
./performance-test.sh --concurrent 10 --environment prod

# Compare results with historical baseline
diff /var/log/weekly-performance/perf-latest.txt \
     /tmp/invoice-agent-perf-*/performance-report.txt
```

---

## Integration with CI/CD

### GitHub Actions Workflow

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Login to Azure
        uses: azure/login@v1
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Deploy to Staging
        run: |
          func azure functionapp publish func-invoice-agent-prod --slot staging

      - name: Validate Staging Deployment
        run: |
          chmod +x scripts/automation/validate-deployment.sh
          scripts/automation/validate-deployment.sh --environment prod --slot staging

      - name: Run Performance Test on Staging
        run: |
          chmod +x scripts/automation/performance-test.sh
          scripts/automation/performance-test.sh --concurrent 5 --environment prod
        continue-on-error: true  # Don't block deployment on perf test

      - name: Swap to Production
        run: |
          az functionapp deployment slot swap \
            --name func-invoice-agent-prod \
            --resource-group rg-invoice-agent-prod \
            --slot staging \
            --target-slot production

      - name: Validate Production Deployment
        run: |
          sleep 30
          scripts/automation/validate-deployment.sh --environment prod

      - name: Health Check
        run: |
          chmod +x scripts/automation/health-check.sh
          scripts/automation/health-check.sh --environment prod
```

### Scheduled Health Checks (Cron)

```bash
# Add to crontab
crontab -e

# Run health check every 15 minutes
*/15 * * * * /path/to/scripts/automation/health-check.sh --environment prod >> /var/log/invoice-agent-health.log 2>&1

# Collect logs daily at midnight
0 0 * * * /path/to/scripts/automation/collect-logs.sh --hours 24 --environment prod --output-dir /var/log/daily-logs

# Weekly performance test (Sundays at 2am)
0 2 * * 0 /path/to/scripts/automation/performance-test.sh --concurrent 10 --environment prod >> /var/log/weekly-perf.log 2>&1
```

---

## Troubleshooting

### Script Fails with "az: command not found"

**Problem:** Azure CLI not installed or not in PATH

**Solution:**

```bash
# Install Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Or use package manager
brew install azure-cli  # macOS
```

### Script Fails with "Not authenticated to Azure"

**Problem:** Not logged into Azure CLI

**Solution:**

```bash
az login

# If using service principal
az login --service-principal \
  --username $AZURE_CLIENT_ID \
  --password $AZURE_CLIENT_SECRET \
  --tenant $AZURE_TENANT_ID
```

### Health Check Shows "Resource group not found"

**Problem:** Incorrect resource group name or environment

**Solution:**

```bash
# Verify resource group exists
az group list --output table

# Use correct environment parameter
./health-check.sh --environment dev  # Not prod
```

### Collect Logs Script Returns Empty Files

**Problem:** No telemetry in Application Insights

**Solution:**

```bash
# Check if Application Insights is receiving data
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --analytics-query "requests | where timestamp > ago(1h) | count"

# If zero, check Function App connection string
az functionapp config appsettings list \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  | grep APPLICATIONINSIGHTS_CONNECTION_STRING
```

### Performance Test Fails with "Messages not processed"

**Problem:** Functions not running or error in processing

**Solution:**

```bash
# Check Function App state
az functionapp show \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "state"

# Check for errors in Application Insights
./collect-logs.sh --hours 1

# Review 02-exceptions.txt for errors
```

### Validate Deployment Script Times Out

**Problem:** Function App taking too long to start

**Solution:**

```bash
# Increase timeout
./validate-deployment.sh --timeout 600  # 10 minutes

# Check deployment status
az functionapp deployment list-publishing-profiles \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod
```

---

## Best Practices

1. **Run health checks regularly** (every 15 minutes via cron)
2. **Validate all deployments** before swapping to production
3. **Collect logs proactively** during incidents
4. **Baseline performance weekly** to detect degradation trends
5. **Archive logs and reports** for historical analysis
6. **Automate in CI/CD** for consistent quality gates
7. **Review exit codes** in automation scripts
8. **Use verbose mode** during troubleshooting
9. **Keep scripts updated** as system evolves
10. **Document custom modifications** in this README

---

## Support

For questions or issues with automation scripts:
- **Documentation:** See `/Users/alex/dev/invoice-agent/docs/RUNBOOK.md`
- **Troubleshooting Guide:** `/Users/alex/dev/invoice-agent/docs/operations/TROUBLESHOOTING_GUIDE.md`
- **Monitoring Guide:** `/Users/alex/dev/invoice-agent/docs/monitoring/MONITORING_GUIDE.md`
- **Team Contact:** DevOps team (devops@company.com)

---

**Last Updated:** 2025-11-19
**Version:** 1.0.0
**Maintainer:** DevOps Team
