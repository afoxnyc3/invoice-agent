#!/bin/bash
# Log Collection Script for Invoice Agent
# Collects comprehensive logs for troubleshooting and analysis
# Usage: ./collect-logs.sh [--hours 24] [--environment prod] [--output-dir /tmp/logs]

set -euo pipefail

# Default values
HOURS_AGO=24
ENVIRONMENT="prod"
OUTPUT_DIR="/tmp/invoice-agent-logs-$(date +%Y%m%d-%H%M%S)"
INCLUDE_POISON_QUEUES=true
ANALYZE_ERRORS=true

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --hours)
            HOURS_AGO="$2"
            shift 2
            ;;
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --no-poison-queues)
            INCLUDE_POISON_QUEUES=false
            shift
            ;;
        --no-analysis)
            ANALYZE_ERRORS=false
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--hours N] [--environment ENV] [--output-dir DIR] [--no-poison-queues] [--no-analysis]"
            exit 1
            ;;
    esac
done

# Set resource names
RESOURCE_GROUP="rg-invoice-agent-${ENVIRONMENT}"
FUNCTION_APP="func-invoice-agent-${ENVIRONMENT}"
STORAGE_ACCOUNT="stinvoiceagent${ENVIRONMENT}"
APP_INSIGHTS="ai-invoice-agent-${ENVIRONMENT}"

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║           Invoice Agent Log Collection Tool                  ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "Environment: $ENVIRONMENT"
echo "Time range: Last $HOURS_AGO hours"
echo "Output directory: $OUTPUT_DIR"
echo ""

# ============================================================================
# 1. SYSTEM INFORMATION
# ============================================================================
echo "1. Collecting system information..."

cat > "$OUTPUT_DIR/00-system-info.txt" <<EOF
Invoice Agent Log Collection Report
====================================
Collection Time: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
Environment: $ENVIRONMENT
Time Range: Last $HOURS_AGO hours
Collected By: $(az account show --query "user.name" -o tsv)

Resource Details:
- Resource Group: $RESOURCE_GROUP
- Function App: $FUNCTION_APP
- Storage Account: $STORAGE_ACCOUNT
- Application Insights: $APP_INSIGHTS

EOF

echo "   ✓ System info saved"

# ============================================================================
# 2. RESOURCE STATUS
# ============================================================================
echo "2. Collecting resource status..."

{
    echo ""
    echo "Resource Status"
    echo "==============="
    echo ""
    echo "Function App State:"
    az functionapp show --name "$FUNCTION_APP" --resource-group "$RESOURCE_GROUP" \
      --query "{Name:name, State:state, DefaultHostName:defaultHostName, LastModified:lastModifiedTimeUtc}" \
      -o table
    echo ""
    echo "Function List:"
    az functionapp function list --name "$FUNCTION_APP" --resource-group "$RESOURCE_GROUP" \
      --query "[].{Name:name, InvokeUrl:invokeUrlTemplate}" -o table
    echo ""
} >> "$OUTPUT_DIR/00-system-info.txt"

echo "   ✓ Resource status saved"

# ============================================================================
# 3. APPLICATION INSIGHTS LOGS
# ============================================================================
echo "3. Collecting Application Insights logs..."

# 3.1 All requests
az monitor app-insights query \
  --app "$APP_INSIGHTS" \
  --resource-group "$RESOURCE_GROUP" \
  --analytics-query "
    requests
    | where timestamp > ago(${HOURS_AGO}h)
    | project timestamp, operation_Name, success, duration, resultCode, customDimensions.transaction_id
    | order by timestamp desc
  " \
  --output table > "$OUTPUT_DIR/01-requests.txt"

echo "   ✓ Requests log saved (01-requests.txt)"

# 3.2 Exceptions
az monitor app-insights query \
  --app "$APP_INSIGHTS" \
  --resource-group "$RESOURCE_GROUP" \
  --analytics-query "
    exceptions
    | where timestamp > ago(${HOURS_AGO}h)
    | project timestamp, operation_Name, type, outerMessage, problemId, customDimensions.transaction_id
    | order by timestamp desc
  " \
  --output table > "$OUTPUT_DIR/02-exceptions.txt"

echo "   ✓ Exceptions log saved (02-exceptions.txt)"

# 3.3 Traces (structured logs)
az monitor app-insights query \
  --app "$APP_INSIGHTS" \
  --resource-group "$RESOURCE_GROUP" \
  --analytics-query "
    traces
    | where timestamp > ago(${HOURS_AGO}h)
    | project timestamp, severityLevel, operation_Name, message, customDimensions
    | order by timestamp desc
  " \
  --output table > "$OUTPUT_DIR/03-traces.txt"

echo "   ✓ Traces log saved (03-traces.txt)"

# 3.4 Dependencies (external calls)
az monitor app-insights query \
  --app "$APP_INSIGHTS" \
  --resource-group "$RESOURCE_GROUP" \
  --analytics-query "
    dependencies
    | where timestamp > ago(${HOURS_AGO}h)
    | project timestamp, operation_Name, type, target, name, duration, success
    | order by timestamp desc
  " \
  --output table > "$OUTPUT_DIR/04-dependencies.txt"

echo "   ✓ Dependencies log saved (04-dependencies.txt)"

# 3.5 Custom Events
az monitor app-insights query \
  --app "$APP_INSIGHTS" \
  --resource-group "$RESOURCE_GROUP" \
  --analytics-query "
    customEvents
    | where timestamp > ago(${HOURS_AGO}h)
    | project timestamp, name, customDimensions
    | order by timestamp desc
  " \
  --output table > "$OUTPUT_DIR/05-custom-events.txt" 2>/dev/null || echo "No custom events" > "$OUTPUT_DIR/05-custom-events.txt"

echo "   ✓ Custom events saved (05-custom-events.txt)"

# ============================================================================
# 4. ERROR ANALYSIS
# ============================================================================
if [ "$ANALYZE_ERRORS" = true ]; then
    echo "4. Analyzing errors..."

    # Error summary by function
    az monitor app-insights query \
      --app "$APP_INSIGHTS" \
      --resource-group "$RESOURCE_GROUP" \
      --analytics-query "
        requests
        | where timestamp > ago(${HOURS_AGO}h)
        | where success == false
        | summarize ErrorCount = count() by operation_Name, resultCode
        | order by ErrorCount desc
      " \
      --output table > "$OUTPUT_DIR/10-error-summary.txt"

    echo "   ✓ Error summary saved (10-error-summary.txt)"

    # Top error messages
    az monitor app-insights query \
      --app "$APP_INSIGHTS" \
      --resource-group "$RESOURCE_GROUP" \
      --analytics-query "
        exceptions
        | where timestamp > ago(${HOURS_AGO}h)
        | summarize Count = count(), SampleMessage = any(outerMessage) by type, problemId
        | order by Count desc
        | take 20
      " \
      --output table > "$OUTPUT_DIR/11-top-errors.txt"

    echo "   ✓ Top errors saved (11-top-errors.txt)"

    # Unknown vendors
    az monitor app-insights query \
      --app "$APP_INSIGHTS" \
      --resource-group "$RESOURCE_GROUP" \
      --analytics-query "
        traces
        | where timestamp > ago(${HOURS_AGO}h)
        | where message contains 'Unknown vendor' or message contains 'vendor not found'
        | extend VendorDomain = extract(@'vendor[:\s]+([a-zA-Z0-9.-]+)', 1, message)
        | summarize Count = count() by VendorDomain
        | order by Count desc
      " \
      --output table > "$OUTPUT_DIR/12-unknown-vendors.txt" 2>/dev/null || echo "No unknown vendors" > "$OUTPUT_DIR/12-unknown-vendors.txt"

    echo "   ✓ Unknown vendors saved (12-unknown-vendors.txt)"
fi

# ============================================================================
# 5. QUEUE STATUS
# ============================================================================
echo "5. Collecting queue status..."

{
    echo "Queue Depths at $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
    echo "=================================================="
    echo ""

    for queue in raw-mail to-post notify; do
        count=$(az storage queue metadata show \
          --name "$queue" \
          --account-name "$STORAGE_ACCOUNT" \
          --query "approximateMessagesCount" -o tsv 2>/dev/null || echo "ERR")
        printf "%-20s : %s messages\n" "$queue" "$count"
    done

    echo ""
    echo "Poison Queues:"
    echo "--------------"

    for queue in raw-mail-poison to-post-poison notify-poison; do
        count=$(az storage queue metadata show \
          --name "$queue" \
          --account-name "$STORAGE_ACCOUNT" \
          --query "approximateMessagesCount" -o tsv 2>/dev/null || echo "ERR")
        printf "%-20s : %s messages\n" "$queue" "$count"
    done
} > "$OUTPUT_DIR/20-queue-status.txt"

echo "   ✓ Queue status saved (20-queue-status.txt)"

# ============================================================================
# 6. POISON QUEUE MESSAGES
# ============================================================================
if [ "$INCLUDE_POISON_QUEUES" = true ]; then
    echo "6. Collecting poison queue messages..."

    for queue in raw-mail-poison to-post-poison notify-poison; do
        count=$(az storage queue metadata show \
          --name "$queue" \
          --account-name "$STORAGE_ACCOUNT" \
          --query "approximateMessagesCount" -o tsv 2>/dev/null || echo "0")

        if [ "$count" -gt 0 ]; then
            echo "   Processing $queue ($count messages)..."

            # Get first 10 messages
            az storage message get \
              --queue-name "$queue" \
              --account-name "$STORAGE_ACCOUNT" \
              --num-messages 10 \
              --output json > "$OUTPUT_DIR/21-poison-${queue}.json" 2>/dev/null || echo "[]" > "$OUTPUT_DIR/21-poison-${queue}.json"

            echo "   ✓ Poison queue $queue saved (21-poison-${queue}.json)"
        else
            echo "   ✓ Poison queue $queue is empty"
        fi
    done
fi

# ============================================================================
# 7. TABLE STORAGE DATA
# ============================================================================
echo "7. Collecting table storage data..."

# 7.1 Recent transactions
az storage entity query \
  --table-name InvoiceTransactions \
  --account-name "$STORAGE_ACCOUNT" \
  --filter "PartitionKey eq '$(date +%Y%m)'" \
  --select "RowKey,VendorName,Status,SenderEmail,ProcessedAt" \
  --output table > "$OUTPUT_DIR/30-recent-transactions.txt" 2>/dev/null || echo "No recent transactions" > "$OUTPUT_DIR/30-recent-transactions.txt"

echo "   ✓ Recent transactions saved (30-recent-transactions.txt)"

# 7.2 Vendor count
VENDOR_COUNT=$(az storage entity query \
  --table-name VendorMaster \
  --account-name "$STORAGE_ACCOUNT" \
  --filter "PartitionKey eq 'Vendor' and Active eq true" \
  --select "RowKey" \
  --query "length(items)" -o tsv 2>/dev/null || echo "0")

{
    echo "Vendor Master Status"
    echo "===================="
    echo ""
    echo "Active Vendors: $VENDOR_COUNT"
    echo ""
    echo "Vendor List:"
    echo "------------"
    az storage entity query \
      --table-name VendorMaster \
      --account-name "$STORAGE_ACCOUNT" \
      --filter "PartitionKey eq 'Vendor' and Active eq true" \
      --select "VendorName,GLCode,ExpenseDept,AllocationSchedule" \
      --output table
} > "$OUTPUT_DIR/31-vendor-master.txt" 2>/dev/null || echo "Cannot read VendorMaster" > "$OUTPUT_DIR/31-vendor-master.txt"

echo "   ✓ Vendor master saved (31-vendor-master.txt)"

# ============================================================================
# 8. PERFORMANCE METRICS
# ============================================================================
echo "8. Collecting performance metrics..."

az monitor app-insights query \
  --app "$APP_INSIGHTS" \
  --resource-group "$RESOURCE_GROUP" \
  --analytics-query "
    requests
    | where timestamp > ago(${HOURS_AGO}h)
    | summarize
        Count = count(),
        AvgDuration = round(avg(duration)/1000, 2),
        P50Duration = round(percentile(duration, 50)/1000, 2),
        P95Duration = round(percentile(duration, 95)/1000, 2),
        P99Duration = round(percentile(duration, 99)/1000, 2),
        SuccessRate = round(countif(success == true) * 100.0 / count(), 2)
      by operation_Name
    | order by Count desc
  " \
  --output table > "$OUTPUT_DIR/40-performance-metrics.txt"

echo "   ✓ Performance metrics saved (40-performance-metrics.txt)"

# ============================================================================
# 9. APPLICATION SETTINGS (SANITIZED)
# ============================================================================
echo "9. Collecting application settings (sanitized)..."

{
    echo "Application Settings (Values Redacted)"
    echo "======================================"
    echo ""
    az functionapp config appsettings list \
      --name "$FUNCTION_APP" \
      --resource-group "$RESOURCE_GROUP" \
      --query "[].{Name:name, IsSet: value != null}" \
      -o table
} > "$OUTPUT_DIR/50-app-settings.txt"

echo "   ✓ App settings saved (50-app-settings.txt)"

# ============================================================================
# 10. GENERATE SUMMARY REPORT
# ============================================================================
echo "10. Generating summary report..."

{
    echo ""
    echo "LOG COLLECTION SUMMARY"
    echo "======================"
    echo ""
    echo "Files collected:"
    ls -lh "$OUTPUT_DIR" | tail -n +2 | awk '{printf "  - %-40s %10s\n", $9, $5}'
    echo ""
    echo "Total size: $(du -sh "$OUTPUT_DIR" | awk '{print $1}')"
} >> "$OUTPUT_DIR/00-system-info.txt"

# ============================================================================
# CREATE TARBALL
# ============================================================================
echo ""
echo "Creating compressed archive..."

TARBALL="/tmp/invoice-agent-logs-${ENVIRONMENT}-$(date +%Y%m%d-%H%M%S).tar.gz"
tar -czf "$TARBALL" -C "$(dirname "$OUTPUT_DIR")" "$(basename "$OUTPUT_DIR")"

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║                  Log Collection Complete                     ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "Logs collected in: $OUTPUT_DIR"
echo "Compressed archive: $TARBALL"
echo ""
echo "Archive size: $(du -sh "$TARBALL" | awk '{print $1}')"
echo ""
echo "To extract:"
echo "  tar -xzf $TARBALL"
echo ""
echo "To view logs:"
echo "  cd $OUTPUT_DIR"
echo "  less 00-system-info.txt"
echo ""

# Generate quick analysis summary
echo "═══════════════════════════════════════════════════════════════"
echo "Quick Analysis"
echo "═══════════════════════════════════════════════════════════════"

# Count total requests
TOTAL_REQUESTS=$(grep -c "^[0-9]" "$OUTPUT_DIR/01-requests.txt" 2>/dev/null || echo "0")
echo "Total requests: $TOTAL_REQUESTS"

# Count exceptions
TOTAL_EXCEPTIONS=$(grep -c "^[0-9]" "$OUTPUT_DIR/02-exceptions.txt" 2>/dev/null || echo "0")
echo "Total exceptions: $TOTAL_EXCEPTIONS"

# Check poison queues
POISON_MSGS=$(grep "poison" "$OUTPUT_DIR/20-queue-status.txt" | awk '{sum += $3} END {print sum}')
if [ -n "$POISON_MSGS" ] && [ "$POISON_MSGS" -gt 0 ]; then
    echo "⚠️  WARNING: $POISON_MSGS messages in poison queues"
else
    echo "✅ No poison queue messages"
fi

echo ""
echo "Log collection completed at: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
echo ""
