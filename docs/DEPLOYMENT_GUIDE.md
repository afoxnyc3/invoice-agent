# Deployment Guide

This guide covers the complete setup and deployment process for the Invoice Agent Azure Functions application using GitHub Actions.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Azure Setup](#azure-setup)
- [GitHub Secrets Configuration](#github-secrets-configuration)
- [Environment Protection Rules](#environment-protection-rules)
- [First Deployment](#first-deployment)
- [Deployment Flow](#deployment-flow)
- [Rollback Procedure](#rollback-procedure)
- [Monitoring Deployments](#monitoring-deployments)
- [Troubleshooting](#troubleshooting)

## Prerequisites

Before deploying, ensure you have:

1. **Azure Subscription** with appropriate permissions:
   - Contributor role on the resource group
   - User Access Administrator (for RBAC assignments)

2. **Azure CLI** installed locally:
   ```bash
   az --version
   az login
   ```

3. **GitHub Repository** with admin access to configure secrets and environments

4. **Azure Resources**:
   - Resource groups created:
     - `rg-invoice-agent-dev` (for development)
     - `rg-invoice-agent-prod` (for production)

## Azure Setup

### 1. Create Service Principal for GitHub Actions

Create a service principal that GitHub Actions will use to deploy to Azure:

```bash
# For production deployments
az ad sp create-for-rbac \
  --name "sp-invoice-agent-github-prod" \
  --role contributor \
  --scopes /subscriptions/{subscription-id}/resourceGroups/rg-invoice-agent-prod \
  --sdk-auth

# For development deployments (optional)
az ad sp create-for-rbac \
  --name "sp-invoice-agent-github-dev" \
  --role contributor \
  --scopes /subscriptions/{subscription-id}/resourceGroups/rg-invoice-agent-dev \
  --sdk-auth
```

**Important:** Save the JSON output! You'll need it for GitHub secrets. It looks like:

```json
{
  "clientId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "clientSecret": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "subscriptionId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "tenantId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "activeDirectoryEndpointUrl": "https://login.microsoftonline.com",
  "resourceManagerEndpointUrl": "https://management.azure.com/",
  "activeDirectoryGraphResourceId": "https://graph.windows.net/",
  "sqlManagementEndpointUrl": "https://management.core.windows.net:8443/",
  "galleryEndpointUrl": "https://gallery.azure.com/",
  "managementEndpointUrl": "https://management.core.windows.net/"
}
```

### 2. Grant Service Principal Additional Roles

For RBAC module deployment and blob URL deployments, the service principal needs additional permissions:

```bash
# Get the service principal Object ID
SP_OBJECT_ID=$(az ad sp list --display-name "sp-invoice-agent-github-prod" --query "[0].id" -o tsv)

# Assign User Access Administrator role (for RBAC deployments)
az role assignment create \
  --assignee-object-id $SP_OBJECT_ID \
  --assignee-principal-type ServicePrincipal \
  --role "User Access Administrator" \
  --scope /subscriptions/{subscription-id}/resourceGroups/rg-invoice-agent-prod

# Assign Storage Blob Data Contributor role (for blob URL deployment)
az role assignment create \
  --assignee-object-id $SP_OBJECT_ID \
  --assignee-principal-type ServicePrincipal \
  --role "Storage Blob Data Contributor" \
  --scope /subscriptions/{subscription-id}/resourceGroups/rg-invoice-agent-prod
```

### 3. Create Azure Function App Admin Key

After the first infrastructure deployment, retrieve the admin key:

```bash
# Get the Function App name
FUNC_NAME=$(az functionapp list \
  --resource-group rg-invoice-agent-prod \
  --query "[?contains(name, 'invoice-agent')].name" -o tsv)

# Get the master (admin) key
az functionapp keys list \
  --name $FUNC_NAME \
  --resource-group rg-invoice-agent-prod \
  --query "masterKey" -o tsv
```

## GitHub Secrets Configuration

Navigate to your GitHub repository: **Settings > Secrets and variables > Actions**

### Repository Secrets

Add the following secrets:

| Secret Name | Description | How to Get |
|------------|-------------|------------|
| `AZURE_CREDENTIALS` | Service principal JSON for production | Output from `az ad sp create-for-rbac` command (production) |
| `AZURE_CREDENTIALS_DEV` | Service principal JSON for dev | Output from `az ad sp create-for-rbac` command (dev) |
| `FUNCTIONS_ADMIN_KEY` | Function App master key | Output from `az functionapp keys list` |
| `GRAPH_TENANT_ID` | Microsoft 365 tenant ID | Azure Portal > Microsoft Entra ID > Overview |
| `GRAPH_CLIENT_ID` | Graph API app registration client ID | Azure Portal > App registrations > invoice-agent-app |
| `GRAPH_CLIENT_SECRET` | Graph API app registration secret | Azure Portal > App registrations > invoice-agent-app > Certificates & secrets |
| `TEAMS_WEBHOOK_URL` | Teams incoming webhook URL | Teams channel > Connectors > Incoming Webhook |
| `AP_EMAIL_ADDRESS` | Accounts payable email address | Your organization's AP email (e.g., ap@company.com) |

### Adding Secrets

1. Click **New repository secret**
2. Enter the **Name** (exactly as shown above)
3. Paste the **Secret value**
4. Click **Add secret**

**Security Notes:**
- Never commit secrets to the repository
- Rotate service principal credentials every 90 days
- Use Key Vault references in production (configured by Bicep)
- Limit service principal scope to specific resource groups

## Environment Protection Rules

GitHub Environments provide manual approval gates and environment-specific secrets.

### 1. Create Environments

Navigate to: **Settings > Environments**

Create three environments:
- `development` (optional manual approval)
- `staging` (no approval required)
- `production` (REQUIRED manual approval)

### 2. Configure Production Environment Protection

For the **production** environment:

1. Click on **production** environment
2. Enable **Required reviewers**:
   - Add team members who can approve deployments
   - Minimum 1 reviewer required
3. Enable **Wait timer** (optional):
   - Set to 5 minutes to allow pre-deployment checks
4. **Deployment branches**:
   - Select "Selected branches"
   - Add rule: `main` (only main branch can deploy to production)

### 3. Environment URLs

Environment URLs are configured in the workflow for easy access:
- Development: `https://func-invoice-agent-dev.azurewebsites.net`
- Production: `https://func-invoice-agent-prod.azurewebsites.net`

> **Note:** We no longer use the staging slot for deployments. The staging slot exists for manual testing only. See [ADR-0034](./adr/0034-blob-url-deployment.md) for details.

## First Deployment

### Step 1: Deploy Infrastructure

Before running the CI/CD pipeline, manually deploy the infrastructure:

```bash
# Login to Azure
az login

# Deploy dev infrastructure
az deployment group create \
  --resource-group rg-invoice-agent-dev \
  --template-file infrastructure/bicep/main.bicep \
  --parameters infrastructure/parameters/dev.json

# Deploy prod infrastructure (including staging slot)
az deployment group create \
  --resource-group rg-invoice-agent-prod \
  --template-file infrastructure/bicep/main.bicep \
  --parameters infrastructure/parameters/prod.json
```

### Step 2: Configure Application Settings

After infrastructure deployment, add sensitive settings to Key Vault:

```bash
# Get Key Vault name
KV_NAME=$(az keyvault list \
  --resource-group rg-invoice-agent-prod \
  --query "[0].name" -o tsv)

# Add secrets to Key Vault
az keyvault secret set --vault-name $KV_NAME --name "graph-tenant-id" --value "$GRAPH_TENANT_ID"
az keyvault secret set --vault-name $KV_NAME --name "graph-client-id" --value "$GRAPH_CLIENT_ID"
az keyvault secret set --vault-name $KV_NAME --name "graph-client-secret" --value "$GRAPH_CLIENT_SECRET"
az keyvault secret set --vault-name $KV_NAME --name "teams-webhook-url" --value "$TEAMS_WEBHOOK_URL"
az keyvault secret set --vault-name $KV_NAME --name "ap-email-address" --value "$AP_EMAIL_ADDRESS"
az keyvault secret set --vault-name $KV_NAME --name "invoice-mailbox" --value "$INVOICE_MAILBOX"

# Azure OpenAI for PDF vendor extraction (required for 95%+ accuracy)
az keyvault secret set --vault-name $KV_NAME --name "azure-openai-endpoint" --value "$AZURE_OPENAI_ENDPOINT"
az keyvault secret set --vault-name $KV_NAME --name "azure-openai-api-key" --value "$AZURE_OPENAI_API_KEY"
```

**Note:** The Bicep template automatically configures Function App settings to reference Key Vault. Secret names use kebab-case (e.g., `graph-tenant-id`) to match the Key Vault references in `functionapp.bicep`.

### Step 3: Seed Vendor Data

Initialize the VendorMaster table:

```bash
# From repository root
python infrastructure/scripts/seed_vendors.py --env prod
```

### Step 4: Trigger First Pipeline Run

Push to main branch to trigger the pipeline:

```bash
git checkout main
git pull
git push origin main
```

Or manually trigger the workflow:
1. Go to **Actions** tab
2. Select **CI/CD Pipeline**
3. Click **Run workflow**
4. Select branch: `main`
5. Click **Run workflow**

### Step 5: Approve Production Deployment

1. Monitor the workflow run in the **Actions** tab
2. Wait for tests and build to complete
3. When **deploy-production** job reaches "Waiting for approval":
   - Click **Review deployments**
   - Review changes
   - Click **Approve and deploy** (or Reject)
4. Monitor deployment progress (upload, restart, health check)

## Deployment Flow

As of December 2025, we use **direct blob URL deployment** instead of slot swaps. See [ADR-0034](./adr/0034-blob-url-deployment.md) for details.

### How It Works

```
Test → Build → Upload to Blob → Generate SAS → Update App Setting → Restart → Health Check → Tag
```

1. **Test**: Run unit tests, linting, security scans
2. **Build**: Create deployment package (`function-app.zip`)
3. **Upload to Blob**: Store package in `function-releases` container with git SHA
4. **Generate SAS**: Create 1-year read-only SAS URL
5. **Update App Setting**: Set `WEBSITE_RUN_FROM_PACKAGE` to the SAS URL
6. **Restart**: Restart function app to load new package
7. **Health Check**: Verify `/api/health` returns 200 and 9 functions are loaded
8. **Tag**: Create git tag `prod-YYYYMMDD-HHMMSS`

### Why Not Slot Swap?

The previous staging + slot swap approach had reliability issues on Linux Consumption plan:
- `WEBSITE_RUN_FROM_PACKAGE=1` relies on metadata that doesn't transfer correctly during slot swap
- Functions would fail to load after swap (404 errors, "0 functions loaded")
- This is a known limitation of the platform

### Deployment Packages

All deployment packages are stored in blob storage:

```bash
# List deployed packages
az storage blob list \
  --container-name function-releases \
  --account-name stinvoiceagentprod \
  --auth-mode login \
  --query "[].{name:name, created:properties.creationTime}" \
  -o table
```

## Rollback Procedure

To rollback to a previous deployment:

### 1. Identify Previous Package

```bash
# List available packages (most recent first)
az storage blob list \
  --container-name function-releases \
  --account-name stinvoiceagentprod \
  --auth-mode login \
  --query "sort_by([].{name:name, created:properties.creationTime}, &created) | reverse(@)" \
  -o table
```

### 2. Generate SAS URL for Previous Package

```bash
# Replace PACKAGE_NAME with the target package
PACKAGE_NAME="function-app-abc123def456.zip"

EXPIRY=$(date -u -d "+1 year" +%Y-%m-%dT%H:%MZ)

SAS_URL=$(az storage blob generate-sas \
  --container-name function-releases \
  --name "${PACKAGE_NAME}" \
  --permissions r \
  --expiry "${EXPIRY}" \
  --account-name stinvoiceagentprod \
  --auth-mode login \
  --full-uri \
  -o tsv)

echo "SAS URL: ${SAS_URL}"
```

### 3. Deploy Previous Package

```bash
# Update app setting
az functionapp config appsettings set \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --settings "WEBSITE_RUN_FROM_PACKAGE=${SAS_URL}" \
  --output none

# Restart function app
az functionapp restart \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod

# Wait and verify health
sleep 45

curl -s "https://func-invoice-agent-prod.azurewebsites.net/api/health?code=$(az functionapp keys list --name func-invoice-agent-prod --resource-group rg-invoice-agent-prod --query 'functionKeys.default' -o tsv)"
```

### Rollback Timing

- **Identify package**: ~30 seconds
- **Generate SAS**: ~10 seconds
- **Update setting + restart**: ~60 seconds
- **Total**: ~2 minutes

## Monitoring Deployments

### GitHub Actions Dashboard

View deployment status:
1. Navigate to **Actions** tab
2. Click on a workflow run
3. Expand jobs to see detailed logs

### Azure Portal Monitoring

Monitor Function App health:
1. Navigate to Function App in Azure Portal
2. **Overview** > View metrics (requests, errors, response time)
3. **Deployment slots** > Compare staging vs production
4. **Log stream** > Real-time logs
5. **Application Insights** > Detailed telemetry

### Key Metrics to Monitor

- **Deployment success rate**: Target 95%+
- **Production health checks**: All passing
- **Deployment duration**: ~90 seconds (restart + health check)
- **Cold start time**: 2-4 seconds
- **Error rate post-deployment**: <1%

### View Deployment History

```bash
# List recent deployments to staging
az functionapp deployment list \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --slot staging

# List recent deployments to production
az functionapp deployment list \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod
```

## Troubleshooting

### Pipeline Failures

#### Test Job Fails

**Problem:** Tests fail or coverage is below 60%

**Solution:**
1. Review test output in GitHub Actions logs
2. Run tests locally: `pytest`
3. Fix failing tests or add missing coverage
4. Push fixes to trigger new pipeline run

#### Build Job Fails

**Problem:** Function app packaging fails

**Solution:**
1. Check that `src/requirements.txt` is valid
2. Verify Python 3.11 compatibility of dependencies
3. Test locally: `cd src && pip install -r requirements.txt`

#### Production Deployment Fails

**Problem:** Deployment to production fails

**Solution:**
1. Verify `AZURE_CREDENTIALS_PROD` secret is correct
2. Ensure service principal has Contributor + Storage Blob Data Contributor roles
3. Check resource group exists: `az group show -n rg-invoice-agent-prod`
4. Verify `function-releases` container exists in storage account
5. Review Azure deployment logs in portal

#### Health Check Fails After Deployment

**Problem:** Health endpoint returns non-200 after deployment

**Solution:**
1. Wait additional 30-60 seconds (cold start)
2. Check Function App logs in Azure Portal
3. Verify app settings are configured correctly
4. Ensure managed identity has access to Storage and Key Vault
5. Check if 9 functions are loaded: `az functionapp function list --name func-invoice-agent-prod --resource-group rg-invoice-agent-prod`
6. See [Rollback Procedure](#rollback-procedure) if urgent

#### Functions Not Loading (0 functions)

**Problem:** Azure shows "0 functions loaded" after deployment

**Solution:**
1. Verify `WEBSITE_RUN_FROM_PACKAGE` contains valid blob URL (not `=1`)
2. Check SAS URL hasn't expired
3. Verify package exists in blob storage
4. Restart function app and wait 60 seconds
5. If persistent, manually deploy using rollback procedure with known-good package

### Authentication Issues

#### Service Principal Expired

**Problem:** Azure login fails with authentication error

**Solution:**
```bash
# Create new service principal
az ad sp create-for-rbac \
  --name "sp-invoice-agent-github-prod" \
  --role contributor \
  --scopes /subscriptions/{subscription-id}/resourceGroups/rg-invoice-agent-prod \
  --sdk-auth

# Update AZURE_CREDENTIALS secret in GitHub
```

#### Key Vault Access Denied

**Problem:** Function App cannot read Key Vault secrets

**Solution:**
```bash
# Get Function App managed identity
FUNC_IDENTITY=$(az functionapp identity show \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query principalId -o tsv)

# Grant Key Vault access
az keyvault set-policy \
  --name $KV_NAME \
  --object-id $FUNC_IDENTITY \
  --secret-permissions get list
```

### Performance Issues

#### Slow Deployments

**Problem:** Deployments take >10 minutes

**Solution:**
1. Enable build caching in GitHub Actions (already configured)
2. Reduce pip installation time with `--cache-dir`
3. Consider using Azure DevOps (faster Azure integration)

#### Cold Start Times High

**Problem:** Functions take >5 seconds to start

**Solution:**
1. Review function dependencies (remove unused imports)
2. Consider Premium plan (always warm)
3. Enable pre-warmed instances in consumption plan

## Best Practices

1. **Monitor post-deployment** - Check metrics for 15 minutes after deployment
2. **Incremental changes** - Deploy small, testable changes
3. **Tag releases** - Pipeline automatically tags production deployments
4. **Rotate credentials** - Update service principals every 90 days
5. **Document changes** - Update commit messages with deployment notes
6. **Use feature branches** - Merge to main only after PR review
7. **Run tests locally** - Test changes before pushing
8. **Keep rollback packages** - Don't delete recent packages from blob storage

## Additional Resources

- [Azure Functions Deployment](https://learn.microsoft.com/azure/azure-functions/functions-deployment-technologies)
- [GitHub Actions for Azure](https://github.com/Azure/actions)
- [Bicep Documentation](https://learn.microsoft.com/azure/azure-resource-manager/bicep/)
- [Rollback Procedures](./ROLLBACK_PROCEDURE.md)
- [Project README](../README.md)

## Support

For deployment issues:
1. Check pipeline logs in GitHub Actions
2. Review Azure deployment history in portal
3. Check Application Insights for runtime errors
4. Consult [ROLLBACK_PROCEDURE.md](./ROLLBACK_PROCEDURE.md) for recovery steps
5. Contact DevOps team for escalation
