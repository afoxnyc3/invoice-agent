# Deployment Guide

This guide covers the complete setup and deployment process for the Invoice Agent Azure Functions application using GitHub Actions.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Azure Setup](#azure-setup)
- [GitHub Secrets Configuration](#github-secrets-configuration)
- [Environment Protection Rules](#environment-protection-rules)
- [First Deployment](#first-deployment)
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

### 2. Grant Service Principal User Access Administrator Role

For RBAC module deployment, the service principal needs additional permissions:

```bash
# Get the service principal Object ID
SP_OBJECT_ID=$(az ad sp list --display-name "sp-invoice-agent-github-prod" --query "[0].id" -o tsv)

# Assign User Access Administrator role (scoped to resource group)
az role assignment create \
  --assignee-object-id $SP_OBJECT_ID \
  --assignee-principal-type ServicePrincipal \
  --role "User Access Administrator" \
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
- Staging: `https://func-invoice-agent-prod-staging.azurewebsites.net`
- Production: `https://func-invoice-agent-prod.azurewebsites.net`

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
az keyvault secret set --vault-name $KV_NAME --name "GraphTenantId" --value "$GRAPH_TENANT_ID"
az keyvault secret set --vault-name $KV_NAME --name "GraphClientId" --value "$GRAPH_CLIENT_ID"
az keyvault secret set --vault-name $KV_NAME --name "GraphClientSecret" --value "$GRAPH_CLIENT_SECRET"
az keyvault secret set --vault-name $KV_NAME --name "TeamsWebhookUrl" --value "$TEAMS_WEBHOOK_URL"
az keyvault secret set --vault-name $KV_NAME --name "ApEmailAddress" --value "$AP_EMAIL_ADDRESS"
```

**Note:** The Bicep template automatically configures Function App settings to reference Key Vault.

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
2. Wait for staging deployment to complete
3. Review staging deployment results
4. When **deploy-production** job reaches "Waiting for approval":
   - Click **Review deployments**
   - Review changes
   - Click **Approve and deploy** (or Reject)

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
- **Staging smoke tests**: All passing
- **Production health checks**: All passing
- **Slot swap duration**: <60 seconds
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

#### Staging Deployment Fails

**Problem:** Deployment to staging slot fails

**Solution:**
1. Verify `AZURE_CREDENTIALS` secret is correct
2. Ensure service principal has Contributor role
3. Check resource group exists: `az group show -n rg-invoice-agent-prod`
4. Review Azure deployment logs in portal

#### Smoke Tests Fail

**Problem:** Staging smoke tests fail after deployment

**Solution:**
1. Check Function App logs in Azure Portal
2. Verify app settings are configured correctly
3. Ensure managed identity has access to Storage and Key Vault
4. Wait 60 seconds and re-run tests (cold start issue)

#### Production Swap Fails

**Problem:** Slot swap to production fails

**Solution:**
1. Check Function App health in Azure Portal
2. Verify no sticky settings prevent swap
3. Manually swap via Azure Portal as test
4. Check Application Insights for errors
5. See [ROLLBACK_PROCEDURE.md](./ROLLBACK_PROCEDURE.md) for recovery

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

1. **Always test in staging first** - Never deploy directly to production
2. **Monitor post-deployment** - Check metrics for 15 minutes after deployment
3. **Incremental changes** - Deploy small, testable changes
4. **Tag releases** - Pipeline automatically tags production deployments
5. **Rotate credentials** - Update service principals every 90 days
6. **Document changes** - Update commit messages with deployment notes
7. **Use feature branches** - Merge to main only after PR review
8. **Run smoke tests locally** - Test infrastructure changes before pushing

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
