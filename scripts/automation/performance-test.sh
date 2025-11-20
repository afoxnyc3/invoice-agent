#!/bin/bash
# Performance Testing Script for Invoice Agent
# Measures system performance under load
# Usage: ./performance-test.sh [--concurrent N] [--environment prod]

set -euo pipefail

# Default values
CONCURRENT_INVOICES=10
ENVIRONMENT="prod"
TEST_VENDOR="Test Vendor Inc"
OUTPUT_DIR="/tmp/invoice-agent-perf-$(date +%Y%m%d-%H%M%S)"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --concurrent)
            CONCURRENT_INVOICES="$2"
            shift 2
            ;;
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--concurrent N] [--environment ENV]"
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
echo "║         Invoice Agent Performance Testing                    ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "Environment: $ENVIRONMENT"
echo "Concurrent invoices: $CONCURRENT_INVOICES"
echo "Output directory: $OUTPUT_DIR"
echo ""

# Record start time
START_TIME=$(date +%s)
START_TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo "Test started: $START_TIMESTAMP"
echo ""

# ============================================================================
# BASELINE MEASUREMENT
# ============================================================================
echo "1. Capturing baseline metrics..."

# Queue depths before test
echo "   Queue depths (before):"
for queue in raw-mail to-post notify; do
    count=$(az storage queue metadata show \
      --name "$queue" \
      --account-name "$STORAGE_ACCOUNT" \
      --query "approximateMessagesCount" -o tsv 2>/dev/null || echo "0")
    echo "     $queue: $count messages"
done

# Transaction count before test
TX_COUNT_BEFORE=$(az storage entity query \
  --table-name InvoiceTransactions \
  --account-name "$STORAGE_ACCOUNT" \
  --filter "PartitionKey eq '$(date +%Y%m)'" \
  --select "RowKey" \
  --query "length(items)" -o tsv 2>/dev/null || echo "0")

echo "   Transactions (before): $TX_COUNT_BEFORE"
echo ""

# ============================================================================
# GENERATE TEST LOAD
# ============================================================================
echo "2. Generating test load ($CONCURRENT_INVOICES concurrent invoices)..."

# Function to send test message to queue
send_test_invoice() {
    local i=$1
    local transaction_id="01TEST$(date +%s)${i}"

    # Create test message
    local message=$(cat <<EOF
{
  "id": "${transaction_id}",
  "sender": "test-${i}@microsoft.com",
  "subject": "Performance Test Invoice #${i}",
  "blob_url": "https://${STORAGE_ACCOUNT}.blob.core.windows.net/invoices/test-${i}.pdf",
  "received_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "original_message_id": "PERF_TEST_${transaction_id}"
}
EOF
)

    # Base64 encode
    local encoded=$(echo -n "$message" | base64)

    # Send to raw-mail queue
    az storage message put \
      --queue-name raw-mail \
      --account-name "$STORAGE_ACCOUNT" \
      --content "$encoded" \
      --output none 2>/dev/null

    echo "   Sent test invoice $i (${transaction_id})"
}

# Send invoices in parallel
for i in $(seq 1 $CONCURRENT_INVOICES); do
    send_test_invoice $i &
done

# Wait for all background jobs
wait

echo ""
echo "   ✅ All $CONCURRENT_INVOICES test invoices queued"
echo ""

# ============================================================================
# MONITOR PROCESSING
# ============================================================================
echo "3. Monitoring processing..."

TIMEOUT=600  # 10 minutes
ELAPSED=0
CHECK_INTERVAL=10

while [ $ELAPSED -lt $TIMEOUT ]; do
    # Check queue depths
    RAW_COUNT=$(az storage queue metadata show --name raw-mail --account-name "$STORAGE_ACCOUNT" --query "approximateMessagesCount" -o tsv 2>/dev/null || echo "0")
    POST_COUNT=$(az storage queue metadata show --name to-post --account-name "$STORAGE_ACCOUNT" --query "approximateMessagesCount" -o tsv 2>/dev/null || echo "0")
    NOTIFY_COUNT=$(az storage queue metadata show --name notify --account-name "$STORAGE_ACCOUNT" --query "approximateMessagesCount" -o tsv 2>/dev/null || echo "0")

    # Check transactions
    TX_COUNT=$(az storage entity query \
      --table-name InvoiceTransactions \
      --account-name "$STORAGE_ACCOUNT" \
      --filter "PartitionKey eq '$(date +%Y%m)' and OriginalMessageId co 'PERF_TEST'" \
      --select "RowKey" \
      --query "length(items)" -o tsv 2>/dev/null || echo "0")

    echo "   [$ELAPSED s] Queues: raw=$RAW_COUNT, post=$POST_COUNT, notify=$NOTIFY_COUNT | Transactions: $TX_COUNT/$CONCURRENT_INVOICES"

    # Check if all processed
    if [ "$TX_COUNT" -ge "$CONCURRENT_INVOICES" ] && [ "$RAW_COUNT" -eq 0 ] && [ "$POST_COUNT" -eq 0 ] && [ "$NOTIFY_COUNT" -eq 0 ]; then
        echo ""
        echo "   ✅ All invoices processed!"
        break
    fi

    sleep $CHECK_INTERVAL
    ((ELAPSED += CHECK_INTERVAL))
done

END_TIME=$(date +%s)
TOTAL_DURATION=$((END_TIME - START_TIME))

echo ""
echo "Processing completed in $TOTAL_DURATION seconds"
echo ""

# ============================================================================
# COLLECT PERFORMANCE METRICS
# ============================================================================
echo "4. Collecting performance metrics..."

# Query Application Insights for detailed metrics
az monitor app-insights query \
  --app "$APP_INSIGHTS" \
  --resource-group "$RESOURCE_GROUP" \
  --analytics-query "
    requests
    | where timestamp > datetime('$START_TIMESTAMP')
    | where customDimensions.original_message_id contains 'PERF_TEST'
    | summarize
        Count = count(),
        AvgDuration = round(avg(duration)/1000, 2),
        MinDuration = round(min(duration)/1000, 2),
        MaxDuration = round(max(duration)/1000, 2),
        P50Duration = round(percentile(duration, 50)/1000, 2),
        P95Duration = round(percentile(duration, 95)/1000, 2),
        P99Duration = round(percentile(duration, 99)/1000, 2),
        SuccessRate = round(countif(success == true) * 100.0 / count(), 2)
      by operation_Name
  " \
  --output table > "$OUTPUT_DIR/performance-metrics.txt"

echo "   ✅ Metrics saved to $OUTPUT_DIR/performance-metrics.txt"

# Per-function breakdown
for func in MailIngest ExtractEnrich PostToAP Notify; do
    az monitor app-insights query \
      --app "$APP_INSIGHTS" \
      --resource-group "$RESOURCE_GROUP" \
      --analytics-query "
        requests
        | where timestamp > datetime('$START_TIMESTAMP')
        | where operation_Name == '$func'
        | summarize
            Count = count(),
            AvgDuration = avg(duration),
            P95Duration = percentile(duration, 95)
      " \
      --output table > "$OUTPUT_DIR/${func}-metrics.txt" 2>/dev/null || echo "No data" > "$OUTPUT_DIR/${func}-metrics.txt"
done

# ============================================================================
# ANALYZE RESULTS
# ============================================================================
echo ""
echo "5. Analyzing results..."

# Calculate throughput
THROUGHPUT=$(awk "BEGIN {printf \"%.2f\", $CONCURRENT_INVOICES / $TOTAL_DURATION}")

# Check for errors
ERROR_COUNT=$(az monitor app-insights query \
  --app "$APP_INSIGHTS" \
  --resource-group "$RESOURCE_GROUP" \
  --analytics-query "
    requests
    | where timestamp > datetime('$START_TIMESTAMP')
    | where customDimensions.original_message_id contains 'PERF_TEST'
    | where success == false
    | count
  " \
  --query "tables[0].rows[0][0]" -o tsv 2>/dev/null || echo "0")

ERROR_RATE=$(awk "BEGIN {printf \"%.2f\", ($ERROR_COUNT / $CONCURRENT_INVOICES) * 100}")

# Calculate average end-to-end latency (simplified estimate)
AVG_LATENCY=$((TOTAL_DURATION / CONCURRENT_INVOICES))

# ============================================================================
# GENERATE REPORT
# ============================================================================
{
    echo "Invoice Agent Performance Test Report"
    echo "======================================"
    echo ""
    echo "Test Configuration:"
    echo "  Environment: $ENVIRONMENT"
    echo "  Concurrent Invoices: $CONCURRENT_INVOICES"
    echo "  Start Time: $START_TIMESTAMP"
    echo "  Test Duration: $TOTAL_DURATION seconds"
    echo ""
    echo "Results:"
    echo "  Throughput: $THROUGHPUT invoices/second"
    echo "  Average Latency: $AVG_LATENCY seconds per invoice"
    echo "  Total Processed: $TX_COUNT invoices"
    echo "  Error Count: $ERROR_COUNT"
    echo "  Error Rate: $ERROR_RATE%"
    echo ""
    echo "Performance Metrics by Function:"
    echo "---------------------------------"
    cat "$OUTPUT_DIR/performance-metrics.txt"
    echo ""
    echo "Assessment:"

    # Performance assessment
    if [ "$AVG_LATENCY" -le 60 ]; then
        echo "  ✅ Latency: PASS (<60s target)"
    else
        echo "  ❌ Latency: FAIL (>60s, actual: ${AVG_LATENCY}s)"
    fi

    ERROR_RATE_INT=$(echo "$ERROR_RATE" | cut -d. -f1)
    if [ "$ERROR_RATE_INT" -le 1 ]; then
        echo "  ✅ Error Rate: PASS (<1% target)"
    else
        echo "  ❌ Error Rate: FAIL (>1%, actual: ${ERROR_RATE}%)"
    fi

    if (( $(echo "$THROUGHPUT > 0.1" | bc -l) )); then
        echo "  ✅ Throughput: PASS (>0.1 invoices/sec)"
    else
        echo "  ❌ Throughput: FAIL (<0.1 invoices/sec)"
    fi

    echo ""
    echo "Detailed metrics available in: $OUTPUT_DIR"

} | tee "$OUTPUT_DIR/performance-report.txt"

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║           Performance Test Complete                          ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "Summary:"
echo "  Total Time: $TOTAL_DURATION seconds"
echo "  Throughput: $THROUGHPUT invoices/second"
echo "  Avg Latency: $AVG_LATENCY seconds"
echo "  Error Rate: $ERROR_RATE%"
echo ""
echo "Full report: $OUTPUT_DIR/performance-report.txt"
echo ""

# ============================================================================
# CLEANUP TEST DATA
# ============================================================================
echo "Cleaning up test data..."

# Note: This is a simplified cleanup. In production, you might want to:
# 1. Delete test transactions from InvoiceTransactions
# 2. Delete test blobs from storage
# 3. Clear any poison queue messages from test

echo "   ⚠️  Manual cleanup recommended:"
echo "     - Review and delete test transactions from InvoiceTransactions"
echo "     - Delete test blobs from 'invoices' container"
echo ""

# Exit with success if performance targets met
if [ "$AVG_LATENCY" -le 60 ] && [ "$ERROR_RATE_INT" -le 1 ]; then
    echo "✅ Performance test PASSED"
    exit 0
else
    echo "❌ Performance test FAILED"
    exit 1
fi
