# /init - Project Initializer

Initialize the invoice-agent project with Azure infrastructure and local development environment.

## Actions

1. **Check prerequisites**
   - Verify Azure CLI is installed and logged in
   - Check Python 3.11 is available
   - Ensure Azure Functions Core Tools v4 installed

2. **Create Azure resources**
   - Deploy resource group
   - Deploy storage account with tables and queues
   - Deploy Function App
   - Deploy Key Vault
   - Deploy Application Insights

3. **Configure local environment**
   - Create local.settings.json from template
   - Set environment variables
   - Install Python dependencies
   - Create virtual environment

4. **Seed initial data**
   - Create VendorMaster table
   - Load sample vendor data (10 common vendors)
   - Create test entries in InvoiceTransactions

5. **Verify setup**
   - Test Graph API connection
   - Verify storage access
   - Check Key Vault connectivity
   - Send test Teams notification

## Usage

When user types `/init` or requests project initialization:

```bash
# Check Azure login
az account show

# Set subscription
az account set --subscription "YOUR_SUBSCRIPTION_ID"

# Deploy infrastructure
az deployment group create \
  --resource-group rg-invoice-agent-dev \
  --template-file infrastructure/main.bicep \
  --parameters infrastructure/parameters/dev.json

# Create local.settings.json
cat > src/local.settings.json << EOF
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "$(az storage account show-connection-string --name stinvoiceagentdev --resource-group rg-invoice-agent-dev --query connectionString -o tsv)",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "GRAPH_TENANT_ID": "${GRAPH_TENANT_ID}",
    "GRAPH_CLIENT_ID": "${GRAPH_CLIENT_ID}",
    "GRAPH_CLIENT_SECRET": "${GRAPH_CLIENT_SECRET}",
    "AP_EMAIL_ADDRESS": "ap@example.com",
    "TEAMS_WEBHOOK_URL": "${TEAMS_WEBHOOK_URL}"
  }
}
EOF

# Install dependencies
cd src
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Seed vendor data
python scripts/seed_vendors.py

# Verify setup
python scripts/verify_setup.py
```

## Checklist

- [ ] Azure CLI authenticated
- [ ] Resource group created
- [ ] Storage account deployed
- [ ] Function App deployed
- [ ] Key Vault configured
- [ ] Application Insights active
- [ ] Local settings created
- [ ] Python dependencies installed
- [ ] Vendor data seeded
- [ ] Graph API tested
- [ ] Teams webhook verified

## Success Output

```
✅ Azure resources deployed
✅ Storage tables created
✅ Queues configured
✅ Function App ready
✅ Local environment configured
✅ 10 vendors loaded
✅ Graph API connected
✅ Teams webhook working

🚀 Invoice Agent initialized successfully!
Next steps:
1. Run `/build` to generate functions
2. Run `/test` to validate
3. Run `/deploy` to push to Azure
```

## Error Handling

If initialization fails:
1. Check Azure subscription and permissions
2. Verify all environment variables are set
3. Ensure network connectivity to Azure
4. Review error logs in `.claude/logs/init.log`
5. Run `/init --cleanup` to reset and try again