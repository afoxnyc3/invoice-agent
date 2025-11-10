# Infrastructure Agent

## Purpose
Generate Azure infrastructure as code (Bicep) for the invoice processing system.

## Capabilities
- Create Bicep templates for all required Azure resources
- Configure Managed Identity and RBAC assignments
- Set up networking and security configurations
- Generate environment-specific parameter files

## Input Requirements
```yaml
environment: dev|staging|prod
region: Azure region (e.g., eastus)
naming_prefix: Prefix for resource names
tags:
  project: invoice-agent
  owner: email
  environment: dev|staging|prod
```

## Resources to Create

### Core Infrastructure
1. **Resource Group**
   - Naming: `rg-{naming_prefix}-{environment}`
   - Tags: Inherited from input

2. **Storage Account**
   - Tier: Standard_LRS (dev), Standard_GRS (prod)
   - Containers:
     - `invoices` - Store email attachments
   - Tables:
     - `VendorMaster` - Vendor lookup data
     - `InvoiceTransactions` - Transaction audit log
   - Queues:
     - `raw-mail` - Unprocessed emails
     - `to-post` - Enriched invoices
     - `notify` - Teams notifications

3. **Function App**
   - Runtime: Python 3.11
   - Plan: Consumption (Y1)
   - OS: Linux
   - Managed Identity: System-assigned
   - App Settings:
     - `GRAPH_TENANT_ID`
     - `GRAPH_CLIENT_ID`
     - `AP_EMAIL_ADDRESS`
     - `TEAMS_WEBHOOK_URL`
     - `AzureWebJobsStorage`

4. **Key Vault**
   - SKU: Standard
   - Secrets:
     - `graph-client-secret`
     - `ap-email-address`
     - `teams-webhook-url`
   - Access Policy: Function App MI

5. **Application Insights**
   - Type: Web
   - Retention: 90 days
   - Sampling: 100% (dev), adaptive (prod)

## Bicep Template Structure
```
infrastructure/
├── main.bicep              # Root orchestrator
├── modules/
│   ├── storage.bicep       # Storage account with tables/queues
│   ├── functionapp.bicep   # Function app with settings
│   ├── keyvault.bicep      # Key Vault with secrets
│   └── monitoring.bicep    # App Insights
└── parameters/
    ├── dev.json            # Dev environment parameters
    └── prod.json           # Prod environment parameters
```

## RBAC Assignments
- Function App MI → Storage Blob Data Contributor
- Function App MI → Storage Table Data Contributor
- Function App MI → Storage Queue Data Contributor
- Function App MI → Key Vault Secrets User

## Security Configuration
- Storage: Private endpoints (prod only)
- Key Vault: Soft delete enabled
- Function App: HTTPS only
- All secrets in Key Vault

## Deployment Script
```bash
# Deploy infrastructure
az deployment group create \
  --resource-group rg-invoice-agent-{env} \
  --template-file main.bicep \
  --parameters @parameters/{env}.json

# Set Key Vault secrets (post-deployment)
az keyvault secret set \
  --vault-name kv-invoice-agent-{env} \
  --name graph-client-secret \
  --value $GRAPH_SECRET
```

## Outputs
- Storage account connection string
- Function App name and URL
- Key Vault URI
- Application Insights instrumentation key
- Resource group ID

## Cost Optimization
- Use Consumption plan for Functions
- Standard_LRS for dev storage
- 90-day retention for logs
- No reserved capacity

## Monitoring Setup
- CPU/Memory metrics
- Queue depth alerts
- Error rate alerts
- Daily cost alerts

## Success Criteria
- All resources deployed successfully
- Managed Identity configured
- RBAC assignments working
- Key Vault accessible
- Storage tables/queues created
- Function App healthy