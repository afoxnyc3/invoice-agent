# Deduplication Analyzer Skill

Analyzes deduplication effectiveness across the invoice processing pipeline.

## Purpose
- Detect duplicate invoice processing
- Identify where duplicates enter the system
- Calculate deduplication rate and effectiveness
- Generate actionable recommendations

## Usage
Invoke this skill when you need to:
- Investigate duplicate processing issues
- Verify deduplication logic is working
- Analyze webhook vs fallback duplicate rates
- Generate dedup effectiveness reports

## Actions

### 1. Query InvoiceTransactions for Duplicates
```bash
# Get duplicate OriginalMessageId entries
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "
    customEvents
    | where timestamp > ago(7d)
    | where name == 'InvoiceTransaction'
    | extend OriginalMessageId = tostring(customDimensions.OriginalMessageId)
    | summarize Count=count(), FirstSeen=min(timestamp), LastSeen=max(timestamp) by OriginalMessageId
    | where Count > 1
    | order by Count desc
  "
```

### 2. Check Application Insights for Dedup Messages
```bash
# Find "Skipping duplicate" log messages
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "
    traces
    | where timestamp > ago(7d)
    | where message contains 'duplicate' or message contains 'already processed'
    | project timestamp, severityLevel, message, operation_Name
    | order by timestamp desc
  "
```

### 3. Analyze Deduplication Points
Check where deduplication happens in the pipeline:
- **ExtractEnrich:** Check if it validates original_message_id
- **PostToAP:** Review _check_already_processed() function
- **Queue Messages:** Check for duplicate message IDs

### 4. Calculate Dedup Effectiveness
```bash
# Calculate dedup rate
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "
    customEvents
    | where timestamp > ago(7d)
    | where name == 'InvoiceTransaction'
    | summarize
        TotalProcessed=count(),
        Duplicates=countif(customDimensions.Status == 'duplicate_skipped')
    | extend DedupRate = (Duplicates * 100.0) / TotalProcessed
    | project TotalProcessed, Duplicates, DedupRate
  "
```

### 5. Identify Duplicate Sources
Determine if duplicates come from webhook failures or fallback path:
```bash
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "
    traces
    | where timestamp > ago(7d)
    | where operation_Name in ('MailWebhook', 'MailIngest')
    | extend OriginalMessageId = tostring(customDimensions.OriginalMessageId)
    | summarize Sources=make_set(operation_Name) by OriginalMessageId
    | where array_length(Sources) > 1
    | project OriginalMessageId, Sources
  "
```

## Output Format
Generate report with:
1. **Duplicate Count:** Total duplicates found in last 7 days
2. **Dedup Rate:** Percentage of emails that were duplicates
3. **Dedup Points:** Where in pipeline duplicates are caught
4. **Sources:** Whether duplicates from webhook/fallback
5. **Recommendations:** Suggested improvements

## Example Report
```
Deduplication Analysis Report
Date: 2025-11-24
Period: Last 7 days

Summary:
- Total Emails Processed: 245
- Duplicates Detected: 12 (4.9%)
- Dedup Success Rate: 100% (all caught at PostToAP)

Findings:
✅ PostToAP deduplication is working (12/12 caught)
⚠️ ExtractEnrich does NOT check for duplicates (inefficient)
⚠️ 12 emails went through vendor lookup unnecessarily

Sources:
- Webhook path: 233 emails (95%)
- Fallback path: 12 emails (5%)
- Duplicates: 12 emails (from both paths)

Recommendations:
1. Add deduplication to ExtractEnrich (save vendor lookups)
2. Current PostToAP dedup is sufficient for correctness
3. Monitor duplicate rate - alert if >10%
```
