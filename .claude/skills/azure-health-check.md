# Azure Functions Health Check

Check Azure Function App runtime status, configuration, and recent execution health.

## Objective
Perform comprehensive health diagnostics on the invoice-agent Azure Function App to identify configuration issues, permission problems, and runtime failures.

## Parameters
- `env` (optional): Environment to check (dev/prod). Defaults to prod.
- `function_name` (optional): Specific function to inspect. If not provided, checks all functions.

## Instructions

### 1. Function App Runtime Status

Check if the function app is running and accessible:

```bash
# Get function app details
az functionapp show \
  --name func-invoice-agent-{env} \
  --resource-group rg-invoice-agent-{env} \
  --query '{state:state, kind:kind, httpsOnly:httpsOnly, location:location}' \
  --output table

# Check function runtime status
az functionapp list-runtimes --os linux --query "[?starts_with(runtime, 'python')]" --output table
```

Report:
- ✅ State should be "Running"
- ✅ httpsOnly should be true
- ⚠️ If stopped, provide restart command

---

### 2. Application Settings Validation

Retrieve and validate all app settings, especially Key Vault references:

```bash
# Get all app settings
az functionapp config appsettings list \
  --name func-invoice-agent-{env} \
  --resource-group rg-invoice-agent-{env} \
  --output json > /tmp/appsettings.json

# Display settings (filtered for security)
cat /tmp/appsettings.json | jq -r '.[] | select(.name | startswith("WEBSITE_") | not) | "\(.name) = \(.value)"'
```

Validate each setting:
- **Key Vault References**: Must use format `@Microsoft.KeyVault(SecretUri=https://...)`
- **Required Settings**: Check for:
  - `AzureWebJobsStorage`
  - `FUNCTIONS_WORKER_RUNTIME` (should be "python")
  - `MICROSOFT_GRAPH_*` settings
  - `STORAGE_*` settings
  - `TABLE_*` settings
  - `TEAMS_WEBHOOK_URL`

Report any:
- ❌ Malformed Key Vault references
- ❌ Missing required settings
- ⚠️ Settings with placeholder values

---

### 3. Managed Identity Permissions

Verify the function app's Managed Identity has proper access:

```bash
# Get the function app's Managed Identity principal ID
PRINCIPAL_ID=$(az functionapp identity show \
  --name func-invoice-agent-{env} \
  --resource-group rg-invoice-agent-{env} \
  --query principalId -o tsv)

echo "Managed Identity Principal ID: $PRINCIPAL_ID"

# Check role assignments
az role assignment list \
  --assignee $PRINCIPAL_ID \
  --all \
  --query '[].{Role:roleDefinitionName, Scope:scope}' \
  --output table
```

Expected permissions:
- ✅ **Storage Blob Data Contributor** on storage account
- ✅ **Storage Queue Data Contributor** on storage account
- ✅ **Storage Table Data Contributor** on storage account
- ⚠️ Check for Graph API permissions separately

---

### 4. Key Vault Access Validation

Test if the function app can access Key Vault secrets:

```bash
# Get Key Vault name
KV_NAME=$(az keyvault list \
  --resource-group rg-invoice-agent-{env} \
  --query '[0].name' -o tsv)

# Check access policies for the Managed Identity
az keyvault show \
  --name $KV_NAME \
  --query "properties.accessPolicies[?objectId=='$PRINCIPAL_ID'].{Secrets:permissions.secrets, Keys:permissions.keys}" \
  --output table
```

Expected:
- ✅ Managed Identity should have "get" and "list" permissions for secrets
- ❌ If missing, provide this fix:
  ```bash
  az keyvault set-policy \
    --name $KV_NAME \
    --object-id $PRINCIPAL_ID \
    --secret-permissions get list
  ```

---

### 5. Function Deployment Status

List all deployed functions and their status:

```bash
# List all functions
az functionapp function list \
  --name func-invoice-agent-{env} \
  --resource-group rg-invoice-agent-{env} \
  --query '[].{Name:name, Language:language, Config:configHref}' \
  --output table
```

Expected functions (7 total):
- MailWebhook (HTTP trigger)
- MailIngest (Timer trigger)
- ExtractEnrich (Queue trigger)
- PostToAP (Queue trigger)
- Notify (Queue trigger)
- AddVendor (Queue trigger)
- SubscriptionManager (Timer trigger)

Report:
- ✅ All 7 functions deployed
- ❌ Missing functions
- ⚠️ Unexpected functions

---

### 6. Recent Invocation Statistics

Get recent execution metrics:

```bash
# This requires Application Insights - check if configured
APP_INSIGHTS_KEY=$(az functionapp config appsettings list \
  --name func-invoice-agent-{env} \
  --resource-group rg-invoice-agent-{env} \
  --query "[?name=='APPINSIGHTS_INSTRUMENTATIONKEY'].value" -o tsv)

if [ -z "$APP_INSIGHTS_KEY" ]; then
  echo "⚠️ Application Insights not configured - cannot get execution metrics"
else
  echo "✅ Application Insights configured"
  # Get app insights resource
  az monitor app-insights component show \
    --app func-invoice-agent-{env} \
    --resource-group rg-invoice-agent-{env} \
    --query '{Name:name, AppId:appId, Location:location}' \
    --output table
fi
```

---

### 7. Host Configuration Review

Check host.json settings:

```bash
# Download function app content to inspect host.json
# Note: This may require deployment credentials
az functionapp deployment source show \
  --name func-invoice-agent-{env} \
  --resource-group rg-invoice-agent-{env} \
  --output table
```

If host.json is accessible locally, review:
- `extensions.queues.maxPollingInterval`: Should be 2000 (2 seconds)
- `extensions.queues.batchSize`: Recommended 16
- `logging.logLevel`: Should include Application Insights

---

### 8. Health Summary Report

After running all checks, provide a structured summary:

```
=== AZURE FUNCTIONS HEALTH CHECK REPORT ===
Environment: {env}
Function App: func-invoice-agent-{env}
Timestamp: {current_time}

RUNTIME STATUS:
  ✅/❌ Function app state: Running/Stopped
  ✅/❌ HTTPS only: Enabled/Disabled

CONFIGURATION:
  ✅/❌ All required app settings present
  ✅/❌ Key Vault references valid
  ⚠️ Issues found: {list any problems}

PERMISSIONS:
  ✅/❌ Managed Identity configured
  ✅/❌ Storage account access: {roles}
  ✅/❌ Key Vault access: {permissions}

DEPLOYMENT:
  ✅/❌ All 7 functions deployed
  Missing: {list if any}

MONITORING:
  ✅/❌ Application Insights configured
  Recent executions: {count or "unable to retrieve"}

IMMEDIATE ACTIONS REQUIRED:
  1. {First critical fix}
  2. {Second critical fix}
  ...

RECOMMENDED NEXT STEPS:
  - {Suggestion 1}
  - {Suggestion 2}
```

---

## Output Format

Provide:
1. **Executive Summary**: One-sentence health status
2. **Critical Issues**: List of blocking problems (red flags)
3. **Warnings**: Non-blocking issues that should be addressed
4. **All Clear Items**: What's working correctly
5. **Remediation Commands**: Copy-paste Azure CLI commands to fix issues

## Success Criteria

Health check is complete when you've verified:
- [ ] Function app is running
- [ ] All 7 functions are deployed
- [ ] App settings are valid (especially Key Vault refs)
- [ ] Managed Identity has required permissions
- [ ] Key Vault access is working
- [ ] Application Insights is configured (if applicable)
