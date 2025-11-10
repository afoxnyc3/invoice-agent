# /deploy - Deployment Pipeline

Deploy invoice-agent to Azure with zero-downtime deployment and verification.

## Actions

1. **Pre-deployment validation**
   - Run all tests
   - Check Azure connectivity
   - Verify Key Vault secrets
   - Backup current deployment

2. **Deploy infrastructure**
   - Update Bicep templates
   - Deploy resource changes
   - Configure networking
   - Set up monitoring

3. **Deploy Function App**
   - Package functions
   - Deploy to staging slot
   - Update app settings
   - Configure managed identity

4. **Run smoke tests**
   - Test function endpoints
   - Verify queue processing
   - Check Teams notifications
   - Validate data flow

5. **Promote to production**
   - Swap staging/production slots
   - Monitor for errors
   - Send deployment notification
   - Update documentation

## Deployment Process

When user types `/deploy [environment]`:

```bash
#!/bin/bash
# Deploy to specified environment (dev/staging/prod)

ENVIRONMENT=${1:-dev}
RESOURCE_GROUP="rg-invoice-agent-${ENVIRONMENT}"
FUNCTION_APP="func-invoice-agent-${ENVIRONMENT}"
STORAGE_ACCOUNT="stinvoiceagent${ENVIRONMENT}"

echo "🚀 Deploying Invoice Agent to ${ENVIRONMENT}"

# Step 1: Pre-deployment checks
echo "Step 1: Pre-deployment validation..."
pytest tests/unit --cov-fail-under=60 || exit 1
az account show || exit 1

# Step 2: Deploy infrastructure
echo "Step 2: Deploying infrastructure..."
az deployment group create \
  --resource-group $RESOURCE_GROUP \
  --template-file infrastructure/main.bicep \
  --parameters infrastructure/parameters/${ENVIRONMENT}.json \
  --name "deploy-$(date +%Y%m%d-%H%M%S)" \
  || exit 1

# Step 3: Package Function App
echo "Step 3: Packaging functions..."
cd src
zip -r ../deploy.zip . -x "*.pyc" -x "__pycache__/*" -x "tests/*"
cd ..

# Step 4: Deploy to staging slot
echo "Step 4: Deploying to staging slot..."
az functionapp deployment slot create \
  --name $FUNCTION_APP \
  --resource-group $RESOURCE_GROUP \
  --slot staging \
  2>/dev/null || true

az functionapp deployment source config-zip \
  --name $FUNCTION_APP \
  --resource-group $RESOURCE_GROUP \
  --slot staging \
  --src deploy.zip

# Step 5: Configure app settings
echo "Step 5: Configuring settings..."
az functionapp config appsettings set \
  --name $FUNCTION_APP \
  --resource-group $RESOURCE_GROUP \
  --slot staging \
  --settings \
    "GRAPH_TENANT_ID=${GRAPH_TENANT_ID}" \
    "GRAPH_CLIENT_ID=${GRAPH_CLIENT_ID}" \
    "AP_EMAIL_ADDRESS=ap@example.com" \
    "TEAMS_WEBHOOK_URL=@Microsoft.KeyVault(SecretUri=https://kv-invoice-agent-${ENVIRONMENT}.vault.azure.net/secrets/teams-webhook-url/)"

# Step 6: Run smoke tests
echo "Step 6: Running smoke tests..."
python scripts/smoke_test.py staging

# Step 7: Swap slots (staging → production)
echo "Step 7: Swapping to production..."
az functionapp deployment slot swap \
  --name $FUNCTION_APP \
  --resource-group $RESOURCE_GROUP \
  --slot staging \
  --target-slot production

# Step 8: Verify production
echo "Step 8: Verifying production..."
sleep 10
python scripts/verify_deployment.py production

# Step 9: Send notification
echo "Step 9: Sending deployment notification..."
curl -X POST $TEAMS_WEBHOOK_URL \
  -H "Content-Type: application/json" \
  -d '{
    "text": "✅ Invoice Agent deployed to '${ENVIRONMENT}'",
    "sections": [{
      "facts": [
        {"name": "Environment", "value": "'${ENVIRONMENT}'"},
        {"name": "Version", "value": "'$(git rev-parse --short HEAD)'"},
        {"name": "Deployed By", "value": "'${USER}'"},
        {"name": "Timestamp", "value": "'$(date +%Y-%m-%d\ %H:%M:%S)'"}
      ]
    }]
  }'

echo "✅ Deployment complete!"
```

## Deployment Verification

```python
# scripts/verify_deployment.py
import sys
import requests
import time
from azure.storage.queue import QueueServiceClient

def verify_deployment(environment: str) -> bool:
    """Verify deployment is working correctly."""

    print(f"Verifying {environment} deployment...")

    # 1. Check Function App health
    function_url = f"https://func-invoice-agent-{environment}.azurewebsites.net/api/health"
    try:
        response = requests.get(function_url, timeout=10)
        if response.status_code == 200:
            print("✅ Function App is healthy")
        else:
            print(f"❌ Function App returned {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Function App unreachable: {e}")
        return False

    # 2. Test queue connectivity
    conn_str = os.environ.get(f"AZURE_STORAGE_CONNECTION_STRING_{environment.upper()}")
    queue_service = QueueServiceClient.from_connection_string(conn_str)

    for queue_name in ["raw-mail", "to-post", "notify"]:
        try:
            queue = queue_service.get_queue_client(queue_name)
            properties = queue.get_queue_properties()
            print(f"✅ Queue '{queue_name}' accessible")
        except:
            print(f"❌ Queue '{queue_name}' not accessible")
            return False

    # 3. Send test message through pipeline
    test_message = {
        "id": f"deploy-test-{int(time.time())}",
        "sender": "test@adobe.com",
        "subject": "Deployment Test",
        "blob_url": "https://storage/test.pdf"
    }

    raw_mail = queue_service.get_queue_client("raw-mail")
    raw_mail.send_message(json.dumps(test_message))
    print("✅ Test message sent")

    return True
```

## Rollback Procedure

```bash
# If deployment fails, rollback to previous version
/deploy rollback [environment]

# Rollback script
az functionapp deployment slot swap \
  --name $FUNCTION_APP \
  --resource-group $RESOURCE_GROUP \
  --slot staging \
  --target-slot production

# Notify team
curl -X POST $TEAMS_WEBHOOK_URL \
  -H "Content-Type: application/json" \
  -d '{"text": "⚠️ Rollback executed for '${ENVIRONMENT}'"}'
```

## Environment-Specific Settings

### Development
```json
{
  "environment": "dev",
  "autoApprove": true,
  "slotSwap": false,
  "notifications": false,
  "retentionDays": 7
}
```

### Staging
```json
{
  "environment": "staging",
  "autoApprove": true,
  "slotSwap": true,
  "notifications": true,
  "retentionDays": 30
}
```

### Production
```json
{
  "environment": "prod",
  "autoApprove": false,
  "slotSwap": true,
  "notifications": true,
  "retentionDays": 90,
  "requireApproval": ["admin@example.com"]
}
```

## Deployment Output

```
🚀 Deploying Invoice Agent to production

Step 1: Pre-deployment validation...
  ✅ All tests passed (87% coverage)
  ✅ Azure authenticated

Step 2: Deploying infrastructure...
  ✅ Resource group updated
  ✅ Storage account configured
  ✅ Function App ready

Step 3: Packaging functions...
  ✅ Created deploy.zip (2.3 MB)

Step 4: Deploying to staging slot...
  ✅ Staging slot created
  ✅ Code deployed to staging

Step 5: Configuring settings...
  ✅ App settings updated
  ✅ Key Vault references configured

Step 6: Running smoke tests...
  ✅ Function endpoints responding
  ✅ Queue processing working
  ✅ Test invoice processed

Step 7: Swapping to production...
  ✅ Slot swap completed
  ✅ Production updated

Step 8: Verifying production...
  ✅ Health check passed
  ✅ All queues accessible
  ✅ End-to-end test successful

Step 9: Sending deployment notification...
  ✅ Teams notification sent

✅ Deployment complete!
   Version: abc123f
   Environment: production
   Duration: 3m 42s
```

## Post-Deployment Checklist

- [ ] Function App running
- [ ] Queues processing messages
- [ ] Tables accessible
- [ ] Key Vault connected
- [ ] Application Insights receiving telemetry
- [ ] Teams notifications working
- [ ] No errors in first 10 minutes
- [ ] Rollback procedure documented
- [ ] Team notified of deployment

## Monitoring After Deployment

```kusto
// Check for errors in Application Insights
exceptions
| where timestamp > ago(10m)
| where cloud_RoleName == "func-invoice-agent-prod"
| summarize count() by operation_Name, problemId
| order by count_ desc

// Check processing metrics
customMetrics
| where name == "InvoiceProcessingTime"
| where timestamp > ago(10m)
| summarize avg(value), max(value), min(value) by bin(timestamp, 1m)
```

## Success Criteria
- Zero-downtime deployment
- All smoke tests pass
- No errors in first 10 minutes
- Processing time <60 seconds
- Teams notification received