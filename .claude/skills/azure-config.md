# Azure Configuration & Secrets Skill

Manage Azure Key Vault secrets and Function App settings across environments with validation and safety checks.

## Purpose

Automate Azure configuration tasks:
- Add/update Key Vault secrets
- Sync Function App settings between staging and production
- Configure Key Vault references in app settings
- Generate secure secrets (client states, API keys)
- Restart Function Apps and verify settings loaded
- **Critical:** Handle staging slot configuration sync (deployment lesson learned)

## Parameters

- `--action`: Operation to perform (required)
  - `add-secret`: Add/update a Key Vault secret
  - `sync-staging`: Sync production settings to staging slot
  - `generate-secret`: Generate secure random secret
  - `verify-settings`: Verify Function App can access all settings
  - `restart`: Restart Function App to load new settings
- `--name`: Secret or setting name (required for add-secret)
- `--value`: Secret value (optional, will prompt securely if not provided)
- `--env`: Environment (dev/prod) (required)
- `--dry-run`: Show what would be done without executing

## Instructions

### Action: add-secret

Add or update a Key Vault secret and configure Function App to reference it.

**Steps:**
1. Validate environment and resource names
2. Check if secret already exists (show current value masked)
3. Add/update secret in Key Vault
4. Configure Function App setting to reference Key Vault
5. Restart Function App
6. Verify secret is accessible

**Example commands:**
```bash
# Set variables based on environment
ENV="dev"  # or "prod"
SECRET_NAME="graph-client-state"
SECRET_VALUE="<value from user or generate>"
RG="rg-invoice-agent-${ENV}"
VAULT="kv-invoice-agent-${ENV}"
FUNC_APP="func-invoice-agent-${ENV}"

# Add secret to Key Vault
az keyvault secret set \
  --vault-name "$VAULT" \
  --name "$SECRET_NAME" \
  --value "$SECRET_VALUE"

# Get secret URI
SECRET_URI=$(az keyvault secret show \
  --vault-name "$VAULT" \
  --name "$SECRET_NAME" \
  --query id -o tsv)

# Configure Function App to reference secret
# Convert kebab-case to SCREAMING_SNAKE_CASE for env var
ENV_VAR_NAME=$(echo "$SECRET_NAME" | tr '[:lower:]' '[:upper:]' | tr '-' '_')

az functionapp config appsettings set \
  --name "$FUNC_APP" \
  --resource-group "$RG" \
  --settings "${ENV_VAR_NAME}=@Microsoft.KeyVault(SecretUri=${SECRET_URI})"

# Restart Function App
az functionapp restart \
  --name "$FUNC_APP" \
  --resource-group "$RG"

# Wait for restart
sleep 15

# Verify setting loaded
az functionapp config appsettings list \
  --name "$FUNC_APP" \
  --resource-group "$RG" \
  --query "[?name=='${ENV_VAR_NAME}'].{Name:name, Value:value}" -o table
```

### Action: sync-staging

**CRITICAL DEPLOYMENT OPERATION** - Sync production app settings to staging slot.

This solves the deployment lesson: "Staging slot does NOT auto-sync app settings from production."

**Steps:**
1. Get all production Function App settings
2. Filter out slot-specific settings (AzureWebJobsStorage, etc.)
3. Apply settings to staging slot
4. Restart staging slot
5. Verify settings loaded correctly

**Example commands:**
```bash
ENV="prod"
RG="rg-invoice-agent-${ENV}"
FUNC_APP="func-invoice-agent-${ENV}"
SETTINGS_FILE="/tmp/prod-settings-${ENV}.json"

# Get production settings
az functionapp config appsettings list \
  --name "$FUNC_APP" \
  --resource-group "$RG" \
  --output json > "$SETTINGS_FILE"

# Apply to staging slot
az functionapp config appsettings set \
  --name "$FUNC_APP" \
  --resource-group "$RG" \
  --slot staging \
  --settings @"$SETTINGS_FILE"

# Restart staging slot
az functionapp restart \
  --name "$FUNC_APP" \
  --resource-group "$RG" \
  --slot staging

# Verify (wait for restart)
sleep 15
echo "Verifying staging slot settings..."
az functionapp config appsettings list \
  --name "$FUNC_APP" \
  --resource-group "$RG" \
  --slot staging \
  --query "[].{Name:name, HasValue:value!=null}" -o table
```

### Action: generate-secret

Generate a cryptographically secure secret for use in configurations.

**Steps:**
1. Generate random secret using openssl
2. Display secret (masked except for confirmation)
3. Optionally add to Key Vault immediately if --name provided

**Example:**
```bash
# Generate 32-character base64 secret
SECRET=$(openssl rand -base64 32)
echo "Generated secret (first 8 chars): ${SECRET:0:8}..."
echo "Generated secret (last 8 chars): ...${SECRET: -8}"
echo ""
echo "Full secret (copy this):"
echo "$SECRET"

# If --name provided, offer to add to Key Vault
if [ -n "$NAME" ]; then
  echo ""
  echo "Add this secret to Key Vault as '$NAME'? (requires --env)"
fi
```

### Action: verify-settings

Verify Function App can access all required settings (no "undefined" values).

**Steps:**
1. List all Function App settings
2. Check for Key Vault reference format
3. Check for "undefined" or null values
4. Test Key Vault access permissions

**Example:**
```bash
ENV="dev"
RG="rg-invoice-agent-${ENV}"
FUNC_APP="func-invoice-agent-${ENV}"
VAULT="kv-invoice-agent-${ENV}"

# Check for undefined or null settings
echo "Checking for undefined/null settings..."
az functionapp config appsettings list \
  --name "$FUNC_APP" \
  --resource-group "$RG" \
  --query "[?contains(value, 'undefined') || value==null].{Name:name, Value:value}" -o table

# List all Key Vault references
echo ""
echo "Key Vault references:"
az functionapp config appsettings list \
  --name "$FUNC_APP" \
  --resource-group "$RG" \
  --query "[?contains(value, '@Microsoft.KeyVault')].{Name:name, Reference:value}" -o table

# Verify Key Vault access
echo ""
echo "Verifying Key Vault access..."
az keyvault secret list --vault-name "$VAULT" --query "[].name" -o tsv
```

### Action: restart

Restart Function App (and optionally staging slot) to load new settings.

**Steps:**
1. Restart specified Function App/slot
2. Wait for restart (15 seconds)
3. Check health via recent logs

**Example:**
```bash
ENV="dev"
RG="rg-invoice-agent-${ENV}"
FUNC_APP="func-invoice-agent-${ENV}"

# Restart production
az functionapp restart \
  --name "$FUNC_APP" \
  --resource-group "$RG"

echo "Restarting Function App..."
sleep 15
echo "✅ Restart complete"

# Check recent logs for errors
az monitor app-insights query \
  --app "ai-invoice-agent-${ENV}" \
  --resource-group "$RG" \
  --analytics-query "traces | where timestamp > ago(2m) | where severityLevel >= 3 | project timestamp, message" \
  --query "tables[0].rows" -o table
```

## Output Format

```
🔧 Azure Configuration: {action}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Environment: {env}
Resource Group: rg-invoice-agent-{env}
Key Vault: kv-invoice-agent-{env}
Function App: func-invoice-agent-{env}

{action-specific output}

✅ Configuration completed successfully
```

## Safety Checks

- Always require --env parameter (no default)
- Confirm destructive operations (overwrites, restarts)
- Mask secret values in output (show first/last 8 chars only)
- Validate resource names exist before operations
- For sync-staging: confirm production is stable before syncing

## Common Use Cases

**1. Initial webhook setup:**
```
/skill:azure-config --action generate-secret
/skill:azure-config --action add-secret --name graph-client-state --env dev
```

**2. Pre-deployment staging sync:**
```
/skill:azure-config --action sync-staging --env prod
```

**3. New secret configuration:**
```
/skill:azure-config --action add-secret --name api-key --env prod
/skill:azure-config --action verify-settings --env prod
```

**4. Troubleshooting "undefined" errors:**
```
/skill:azure-config --action verify-settings --env dev
/skill:azure-config --action restart --env dev
```

## Notes

- Secrets are stored in Key Vault and referenced by Function App
- Staging slot must be manually synced after production changes
- Always restart Function App after settings changes
- Use --dry-run to preview operations before executing
