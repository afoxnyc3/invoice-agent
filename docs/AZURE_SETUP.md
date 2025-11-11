# Azure Setup Guide

This guide walks through the complete setup process for deploying the Invoice Agent to Azure, including App Registration for Graph API access and infrastructure deployment.

## Prerequisites

- Azure subscription with Owner or Contributor role
- Azure CLI installed (`az --version`)
- Bicep CLI installed (included with Azure CLI 2.20.0+)
- Microsoft 365 tenant with Global Administrator access
- Git repository cloned locally

## Table of Contents

1. [Azure AD App Registration (Graph API)](#1-azure-ad-app-registration)
2. [Deploy Infrastructure (Bicep)](#2-deploy-infrastructure)
3. [Configure Key Vault Secrets](#3-configure-key-vault-secrets)
4. [Verify RBAC Assignments](#4-verify-rbac-assignments)
5. [Deploy Function Code](#5-deploy-function-code)
6. [Test End-to-End](#6-test-end-to-end)
7. [Troubleshooting](#troubleshooting)

---

## 1. Azure AD App Registration

The Function App needs an Azure AD App Registration to access Microsoft Graph API for email operations.

### Step 1.1: Create App Registration

```bash
# Login to Azure
az login

# Set your tenant ID (replace with your actual tenant ID)
TENANT_ID=$(az account show --query tenantId -o tsv)
echo "Tenant ID: $TENANT_ID"

# Create app registration
APP_NAME="invoice-agent-api"
APP_ID=$(az ad app create \
  --display-name "$APP_NAME" \
  --sign-in-audience AzureADMyOrg \
  --query appId -o tsv)

echo "Application (Client) ID: $APP_ID"
```

### Step 1.2: Configure API Permissions

The app needs the following **Application** permissions (not Delegated):

```bash
# Add Microsoft Graph API permissions
# Mail.Read - Read mail in all mailboxes
az ad app permission add \
  --id $APP_ID \
  --api 00000003-0000-0000-c000-000000000000 \
  --api-permissions 810c84a8-4a9e-49e6-bf7d-12d183f40d01=Role

# Mail.Send - Send mail as any user
az ad app permission add \
  --id $APP_ID \
  --api 00000003-0000-0000-c000-000000000000 \
  --api-permissions b633e1c5-b582-4048-a93e-9f11b44c7e96=Role
```

### Step 1.3: Grant Admin Consent

**IMPORTANT:** These permissions require admin consent.

```bash
# Grant admin consent (requires Global Administrator role)
az ad app permission admin-consent --id $APP_ID
```

**Alternative: Grant via Portal**
1. Go to Azure Portal → Azure Active Directory → App registrations
2. Find your app registration (invoice-agent-api)
3. Go to API permissions
4. Click "Grant admin consent for [Your Organization]"
5. Confirm the consent

### Step 1.4: Create Client Secret

```bash
# Create client secret (valid for 2 years)
CLIENT_SECRET=$(az ad app credential reset \
  --id $APP_ID \
  --append \
  --years 2 \
  --query password -o tsv)

echo "Client Secret: $CLIENT_SECRET"
echo ""
echo "IMPORTANT: Save these values - you'll need them for Key Vault"
echo "Tenant ID: $TENANT_ID"
echo "Client ID: $APP_ID"
echo "Client Secret: $CLIENT_SECRET"
```

**Security Note:** Store the client secret securely. You won't be able to retrieve it again.

---

## 2. Deploy Infrastructure

Deploy all Azure resources using Bicep templates.

### Step 2.1: Set Deployment Variables

```bash
# Set environment
ENVIRONMENT="dev"  # Options: dev, staging, prod
LOCATION="eastus"
RESOURCE_GROUP="rg-invoice-agent-$ENVIRONMENT"

# Create resource group
az group create \
  --name $RESOURCE_GROUP \
  --location $LOCATION
```

### Step 2.2: Deploy Bicep Template

```bash
# Navigate to infrastructure directory
cd infrastructure/bicep

# Deploy infrastructure
az deployment group create \
  --resource-group $RESOURCE_GROUP \
  --template-file main.bicep \
  --parameters environment=$ENVIRONMENT \
  --parameters location=$LOCATION \
  --verbose
```

The deployment will create:
- ✅ Storage Account (blob, queue, table)
- ✅ Function App with System-assigned Managed Identity
- ✅ Key Vault with access policies
- ✅ Application Insights
- ✅ Log Analytics Workspace
- ✅ RBAC role assignments (Storage + Key Vault)

### Step 2.3: Capture Deployment Outputs

```bash
# Get deployment outputs
FUNCTION_APP_NAME=$(az deployment group show \
  --resource-group $RESOURCE_GROUP \
  --name main \
  --query properties.outputs.functionAppName.value -o tsv)

KEY_VAULT_NAME=$(az deployment group show \
  --resource-group $RESOURCE_GROUP \
  --name main \
  --query properties.outputs.keyVaultName.value -o tsv)

echo "Function App: $FUNCTION_APP_NAME"
echo "Key Vault: $KEY_VAULT_NAME"
```

---

## 3. Configure Key Vault Secrets

Update the Key Vault with actual values for Graph API and other configurations.

### Step 3.1: Set Graph API Credentials

```bash
# Set Graph API secrets (use values from Step 1.4)
az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name graph-tenant-id \
  --value $TENANT_ID

az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name graph-client-id \
  --value $APP_ID

az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name graph-client-secret \
  --value $CLIENT_SECRET
```

### Step 3.2: Set Email Configuration

```bash
# Set AP email address (accounts payable mailbox)
AP_EMAIL="accountspayable@yourdomain.com"
az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name ap-email-address \
  --value $AP_EMAIL

# This is also used as INVOICE_MAILBOX for monitoring
```

### Step 3.3: Set Teams Webhook URL

```bash
# Create Teams incoming webhook
# 1. Go to Teams → Channel → Connectors → Incoming Webhook
# 2. Copy the webhook URL
# 3. Set it here:

TEAMS_WEBHOOK="https://yourorg.webhook.office.com/webhookb2/..."
az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name teams-webhook-url \
  --value $TEAMS_WEBHOOK
```

---

## 4. Verify RBAC Assignments

Verify that the Function App Managed Identity has the correct permissions.

### Step 4.1: Get Principal IDs

```bash
# Get Function App principal ID
PRINCIPAL_ID=$(az functionapp identity show \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query principalId -o tsv)

echo "Function App Principal ID: $PRINCIPAL_ID"
```

### Step 4.2: Verify Storage Roles

```bash
# Check Storage role assignments
STORAGE_ACCOUNT_NAME=$(az deployment group show \
  --resource-group $RESOURCE_GROUP \
  --name main \
  --query properties.outputs.storageAccountName.value -o tsv)

az role assignment list \
  --assignee $PRINCIPAL_ID \
  --scope "/subscriptions/$(az account show --query id -o tsv)/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Storage/storageAccounts/$STORAGE_ACCOUNT_NAME" \
  --output table
```

Expected roles:
- ✅ Storage Blob Data Contributor
- ✅ Storage Queue Data Contributor
- ✅ Storage Table Data Contributor

### Step 4.3: Verify Key Vault Access

```bash
# Check Key Vault access policy
az keyvault show \
  --name $KEY_VAULT_NAME \
  --query "properties.accessPolicies[?objectId=='$PRINCIPAL_ID']" \
  --output json
```

Expected permissions:
- ✅ Secrets: get, list

---

## 5. Deploy Function Code

Deploy the Python function code to the Function App.

### Step 5.1: Install Dependencies

```bash
# Navigate to source directory
cd ../../src

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 5.2: Deploy Functions

```bash
# Deploy to Azure (requires Azure Functions Core Tools)
func azure functionapp publish $FUNCTION_APP_NAME --python

# Verify deployment
az functionapp show \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query "state" -o tsv
```

Expected output: `Running`

### Step 5.3: Restart Function App

```bash
# Restart to pick up Key Vault references
az functionapp restart \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP
```

---

## 6. Test End-to-End

Validate the complete invoice processing pipeline.

### Step 6.1: Verify Function Configuration

```bash
# Check app settings
az functionapp config appsettings list \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --output table | grep -E "GRAPH|INVOICE|TEAMS"
```

All Graph API and email settings should show `@Microsoft.KeyVault(...)` references.

### Step 6.2: Check Function Logs

```bash
# Stream live logs
az functionapp log tail \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP
```

### Step 6.3: Manual Test Email

Send a test invoice email to your AP mailbox with:
- Subject: "Invoice - Adobe Inc"
- Attachment: Sample PDF invoice
- From: vendor@adobe.com

The MailIngest function runs every 5 minutes. Monitor:
1. Function execution logs
2. Blob storage for uploaded attachment
3. Queue messages in raw-mail queue
4. Teams channel for notifications

### Step 6.4: Verify Processing

```bash
# Check queue depths (should be zero after processing)
az storage queue list \
  --account-name $STORAGE_ACCOUNT_NAME \
  --auth-mode login

# Check InvoiceTransactions table
az storage entity query \
  --table-name InvoiceTransactions \
  --account-name $STORAGE_ACCOUNT_NAME \
  --auth-mode login
```

---

## 7. Seed Vendor Data

Load initial vendor data into the VendorMaster table.

### Step 7.1: Prepare Vendor Data

Edit `data/vendors.csv` with your vendor information:

```csv
vendor_domain,vendor_name,expense_dept,gl_code,allocation_schedule,billing_party
adobe_com,Adobe Inc,IT,6100,MONTHLY,Chelsea Piers
microsoft_com,Microsoft Corporation,IT,6100,ANNUAL,Chelsea Piers
```

### Step 7.2: Run Seeding Script

```bash
# Navigate to scripts directory
cd ../../infrastructure/scripts

# Run seeding script
python seed_vendors.py \
  --storage-account $STORAGE_ACCOUNT_NAME \
  --csv-file ../../data/vendors.csv
```

### Step 7.3: Verify Data

```bash
# Query VendorMaster table
az storage entity query \
  --table-name VendorMaster \
  --account-name $STORAGE_ACCOUNT_NAME \
  --auth-mode login \
  --output table
```

---

## Troubleshooting

### Issue: Function App can't access Storage

**Symptoms:** Errors like "This request is not authorized"

**Solution:**
```bash
# Verify RBAC role assignments are complete
az deployment group show \
  --resource-group $RESOURCE_GROUP \
  --name main \
  --query properties.outputs.rbacRoleAssignments.value

# Role assignments can take 5-10 minutes to propagate
# Wait and then restart Function App
sleep 300
az functionapp restart --name $FUNCTION_APP_NAME --resource-group $RESOURCE_GROUP
```

### Issue: Function App can't access Key Vault

**Symptoms:** Key Vault reference errors in logs

**Solution:**
```bash
# Check if access policy is set
az keyvault show \
  --name $KEY_VAULT_NAME \
  --query "properties.accessPolicies[?objectId=='$PRINCIPAL_ID']"

# If empty, manually add access policy
az keyvault set-policy \
  --name $KEY_VAULT_NAME \
  --object-id $PRINCIPAL_ID \
  --secret-permissions get list
```

### Issue: Graph API authentication failures

**Symptoms:** "Failed to acquire token" errors

**Solution:**
```bash
# Verify App Registration permissions
az ad app permission list --id $APP_ID

# Verify admin consent was granted
az ad app permission list-grants --id $APP_ID

# Test Graph API access manually
az rest --method GET \
  --uri "https://graph.microsoft.com/v1.0/users/$AP_EMAIL/messages" \
  --headers "Authorization=Bearer $(az account get-access-token --resource https://graph.microsoft.com --query accessToken -o tsv)"
```

### Issue: MailIngest not polling emails

**Symptoms:** No function executions every 5 minutes

**Solution:**
```bash
# Check timer trigger configuration
func azure functionapp list-functions $FUNCTION_APP_NAME

# Manually trigger function
az functionapp function invoke \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --function-name MailIngest
```

### Issue: Unknown vendor not being handled

**Symptoms:** Processing stops at ExtractEnrich

**Solution:**
- Check VendorMaster table has data
- Verify vendor domain extraction logic matches your email domains
- Use AddVendor HTTP endpoint to add missing vendors

---

## Security Best Practices

### Production Recommendations

1. **Network Security**
   - Enable Private Endpoints for Storage and Key Vault
   - Restrict Function App to VNet
   - Use Azure Firewall for outbound traffic

2. **Secrets Management**
   - Rotate client secrets annually
   - Use managed identities wherever possible
   - Enable Key Vault logging and alerts

3. **Access Control**
   - Use separate App Registrations per environment
   - Implement least-privilege RBAC
   - Enable MFA for admin accounts

4. **Monitoring**
   - Set up alerts for failed authentications
   - Monitor Key Vault access logs
   - Track invoice processing SLAs

---

## Post-Deployment Checklist

- [ ] App Registration created with correct permissions
- [ ] Admin consent granted for Graph API
- [ ] Infrastructure deployed via Bicep
- [ ] RBAC role assignments verified (8 total)
- [ ] Key Vault secrets populated
- [ ] Function code deployed
- [ ] Vendor data seeded
- [ ] End-to-end test completed successfully
- [ ] Teams notifications working
- [ ] Application Insights dashboard configured
- [ ] Documentation updated with environment-specific values

---

## Additional Resources

- [Microsoft Graph API Documentation](https://learn.microsoft.com/en-us/graph/api/overview)
- [Azure Functions Python Guide](https://learn.microsoft.com/en-us/azure/azure-functions/functions-reference-python)
- [Azure RBAC Documentation](https://learn.microsoft.com/en-us/azure/role-based-access-control/overview)
- [Key Vault Best Practices](https://learn.microsoft.com/en-us/azure/key-vault/general/best-practices)

---

**Maintained By:** Development Team
**Last Updated:** 2024-11-11
**Version:** 1.0.0
