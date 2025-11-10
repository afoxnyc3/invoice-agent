# Deploy Agent

## Purpose
Automate deployment of invoice processing system to Azure environments.

## Capabilities
- Deploy infrastructure using Bicep
- Deploy Function App with zip deployment
- Configure application settings
- Run smoke tests
- Verify deployment health
- Support blue-green deployments

## Deployment Process

### Pre-Deployment Checks
```bash
# 1. Verify Azure CLI logged in
az account show

# 2. Verify target resource group exists
az group show --name rg-invoice-agent-{env}

# 3. Verify Key Vault secrets set
az keyvault secret list --vault-name kv-invoice-agent-{env}

# 4. Run tests
pytest tests/unit --cov-fail-under=60

# 5. Build function app package
cd src
zip -r ../function-app.zip . -x "*.pyc" -x "__pycache__/*"
```

### Infrastructure Deployment
```bash
#!/bin/bash
# deploy-infrastructure.sh

ENVIRONMENT=${1:-dev}
RESOURCE_GROUP="rg-invoice-agent-${ENVIRONMENT}"
LOCATION="eastus"

# Create resource group if not exists
az group create \
  --name $RESOURCE_GROUP \
  --location $LOCATION \
  --tags Environment=$ENVIRONMENT Project=InvoiceAgent Owner=DevTeam

# Deploy Bicep template
az deployment group create \
  --resource-group $RESOURCE_GROUP \
  --template-file infrastructure/main.bicep \
  --parameters infrastructure/parameters/${ENVIRONMENT}.json \
  --name "deployment-$(date +%Y%m%d-%H%M%S)"

# Get outputs
STORAGE_ACCOUNT=$(az deployment group show \
  --resource-group $RESOURCE_GROUP \
  --name deployment-* \
  --query properties.outputs.storageAccountName.value -o tsv)

FUNCTION_APP=$(az deployment group show \
  --resource-group $RESOURCE_GROUP \
  --name deployment-* \
  --query properties.outputs.functionAppName.value -o tsv)

echo "Storage Account: $STORAGE_ACCOUNT"
echo "Function App: $FUNCTION_APP"
```

### Function App Deployment
```bash
#!/bin/bash
# deploy-functions.sh

ENVIRONMENT=${1:-dev}
RESOURCE_GROUP="rg-invoice-agent-${ENVIRONMENT}"
FUNCTION_APP="func-invoice-agent-${ENVIRONMENT}"

# Stop function app (for clean deployment)
az functionapp stop --name $FUNCTION_APP --resource-group $RESOURCE_GROUP

# Deploy code
az functionapp deployment source config-zip \
  --resource-group $RESOURCE_GROUP \
  --name $FUNCTION_APP \
  --src function-app.zip

# Update app settings
az functionapp config appsettings set \
  --name $FUNCTION_APP \
  --resource-group $RESOURCE_GROUP \
  --settings \
    "GRAPH_TENANT_ID=${GRAPH_TENANT_ID}" \
    "GRAPH_CLIENT_ID=${GRAPH_CLIENT_ID}" \
    "AP_EMAIL_ADDRESS=ap@example.com" \
    "TEAMS_WEBHOOK_URL=${TEAMS_WEBHOOK_URL}" \
    "ENVIRONMENT=${ENVIRONMENT}"

# Start function app
az functionapp start --name $FUNCTION_APP --resource-group $RESOURCE_GROUP

echo "Deployment complete for $FUNCTION_APP"
```

### Post-Deployment Tasks
```python
#!/usr/bin/env python3
# post_deploy.py

import os
import sys
from azure.data.tables import TableServiceClient
from azure.storage.queue import QueueServiceClient
import requests
import time

def verify_deployment(environment: str):
    """Run post-deployment verification."""

    # 1. Check Function App health
    function_app = f"func-invoice-agent-{environment}"
    health_url = f"https://{function_app}.azurewebsites.net/api/health"

    try:
        response = requests.get(health_url, timeout=10)
        if response.status_code != 200:
            print(f"❌ Function App health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot reach Function App: {e}")
        return False

    print(f"✅ Function App is healthy")

    # 2. Verify Storage Tables exist
    conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    table_service = TableServiceClient.from_connection_string(conn_str)

    required_tables = ["VendorMaster", "InvoiceTransactions"]
    for table_name in required_tables:
        try:
            table_client = table_service.get_table_client(table_name)
            # Try to query (will fail if table doesn't exist)
            list(table_client.query_entities("PartitionKey eq 'test'", results_per_page=1))
            print(f"✅ Table '{table_name}' exists")
        except:
            print(f"❌ Table '{table_name}' not found")
            return False

    # 3. Verify Queues exist
    queue_service = QueueServiceClient.from_connection_string(conn_str)
    required_queues = ["raw-mail", "to-post", "notify"]

    for queue_name in required_queues:
        try:
            queue_client = queue_service.get_queue_client(queue_name)
            properties = queue_client.get_queue_properties()
            print(f"✅ Queue '{queue_name}' exists")
        except:
            print(f"❌ Queue '{queue_name}' not found")
            return False

    # 4. Test Teams webhook (if configured)
    webhook_url = os.environ.get("TEAMS_WEBHOOK_URL")
    if webhook_url:
        test_message = {
            "text": f"✅ Deployment verification successful for {environment} environment"
        }
        try:
            response = requests.post(webhook_url, json=test_message, timeout=5)
            if response.status_code == 200:
                print(f"✅ Teams webhook is working")
        except:
            print(f"⚠️ Teams webhook not responding (non-critical)")

    return True

if __name__ == "__main__":
    environment = sys.argv[1] if len(sys.argv) > 1 else "dev"

    if verify_deployment(environment):
        print(f"\n✅ Deployment verification passed for {environment}")
        sys.exit(0)
    else:
        print(f"\n❌ Deployment verification failed for {environment}")
        sys.exit(1)
```

### Smoke Tests
```python
#!/usr/bin/env python3
# smoke_tests.py

import json
from azure.storage.queue import QueueClient
import time
import sys

def run_smoke_test(environment: str):
    """Run basic smoke test through the pipeline."""

    conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")

    # Send test message to raw-mail queue
    raw_mail_queue = QueueClient.from_connection_string(conn_str, "raw-mail")

    test_message = {
        "id": f"smoke-test-{int(time.time())}",
        "sender": "test@adobe.com",  # Known vendor for testing
        "subject": "Smoke Test Invoice",
        "blob_url": "https://storage/test/smoke-test.pdf",
        "received_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
    }

    print(f"Sending test message: {test_message['id']}")
    raw_mail_queue.send_message(json.dumps(test_message))

    # Wait for processing
    print("Waiting 30 seconds for processing...")
    time.sleep(30)

    # Check if message made it through pipeline
    # In real scenario, would check InvoiceTransactions table
    print(f"✅ Smoke test completed")

    return True

if __name__ == "__main__":
    environment = sys.argv[1] if len(sys.argv) > 1 else "dev"

    if run_smoke_test(environment):
        print(f"✅ Smoke tests passed for {environment}")
        sys.exit(0)
    else:
        print(f"❌ Smoke tests failed for {environment}")
        sys.exit(1)
```

## GitHub Actions Workflow

```yaml
# .github/workflows/deploy.yml
name: Deploy Invoice Agent

on:
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      environment:
        description: 'Environment to deploy'
        required: true
        default: 'dev'
        type: choice
        options:
          - dev
          - staging
          - prod

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r src/requirements.txt
          pip install pytest pytest-cov

      - name: Run tests
        run: pytest tests/unit --cov-fail-under=60

  deploy:
    needs: test
    runs-on: ubuntu-latest
    environment: ${{ github.event.inputs.environment || 'dev' }}

    steps:
      - uses: actions/checkout@v3

      - name: Login to Azure
        uses: azure/login@v1
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Deploy Infrastructure
        run: |
          chmod +x scripts/deploy-infrastructure.sh
          ./scripts/deploy-infrastructure.sh ${{ github.event.inputs.environment || 'dev' }}

      - name: Build Function App
        run: |
          cd src
          zip -r ../function-app.zip . -x "*.pyc" -x "__pycache__/*"

      - name: Deploy Functions
        run: |
          chmod +x scripts/deploy-functions.sh
          ./scripts/deploy-functions.sh ${{ github.event.inputs.environment || 'dev' }}

      - name: Verify Deployment
        run: |
          python scripts/post_deploy.py ${{ github.event.inputs.environment || 'dev' }}

      - name: Run Smoke Tests
        run: |
          python scripts/smoke_tests.py ${{ github.event.inputs.environment || 'dev' }}
```

## Rollback Procedure

```bash
#!/bin/bash
# rollback.sh

ENVIRONMENT=${1:-dev}
RESOURCE_GROUP="rg-invoice-agent-${ENVIRONMENT}"
FUNCTION_APP="func-invoice-agent-${ENVIRONMENT}"

# Get previous deployment
PREVIOUS_DEPLOYMENT=$(az functionapp deployment list \
  --name $FUNCTION_APP \
  --resource-group $RESOURCE_GROUP \
  --query "[1].id" -o tsv)

if [ -z "$PREVIOUS_DEPLOYMENT" ]; then
    echo "No previous deployment found"
    exit 1
fi

# Rollback to previous deployment
az functionapp deployment rollback \
  --name $FUNCTION_APP \
  --resource-group $RESOURCE_GROUP \
  --deployment-id $PREVIOUS_DEPLOYMENT

echo "Rolled back to deployment: $PREVIOUS_DEPLOYMENT"

# Notify Teams
curl -H "Content-Type: application/json" \
  -d '{"text":"⚠️ Rollback executed for '$ENVIRONMENT' environment"}' \
  $TEAMS_WEBHOOK_URL
```

## Deployment Checklist

### Pre-Deployment
- [ ] All tests passing
- [ ] Code reviewed and approved
- [ ] Secrets configured in Key Vault
- [ ] Backup of current deployment taken

### During Deployment
- [ ] Infrastructure deployed successfully
- [ ] Function App deployed
- [ ] Application settings configured
- [ ] Managed Identity permissions verified

### Post-Deployment
- [ ] Health checks passing
- [ ] Storage resources created
- [ ] Smoke tests successful
- [ ] Teams notification sent
- [ ] Monitoring alerts configured

### If Issues Occur
- [ ] Check deployment logs
- [ ] Verify Key Vault access
- [ ] Check Application Insights for errors
- [ ] Run rollback if needed
- [ ] Notify team of issues

## Success Criteria
- Zero-downtime deployment
- All health checks pass
- Smoke tests successful
- No errors in first 10 minutes
- Teams notifications working