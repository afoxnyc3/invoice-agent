# Azure Functions Pipeline Execution Failure - Fix Plan
*Generated: November 23, 2025 @ 8:05 PM*

## Executive Summary
Azure Functions are accepting HTTP requests (202 response) but not executing core logic. The email processing pipeline has zero throughput despite successful deployments and passing tests. This plan addresses the root causes and provides a systematic approach to restore functionality.

## Root Causes Identified

### 1. Missing scriptFile Directives (CRITICAL)
Most function.json files are missing the `"scriptFile": "__init__.py"` directive that tells Azure Functions runtime which Python file to execute.

**Affected Functions:**
- MailIngest/function.json
- ExtractEnrich/function.json
- PostToAP/function.json
- Notify/function.json
- AddVendor/function.json

**Working Functions (have scriptFile):**
- MailWebhook/function.json
- MailWebhookProcessor/function.json
- SubscriptionManager/function.json

### 2. Storage Connection Configuration Mismatch
Function App uses Managed Identity for storage:
```json
{
  "AzureWebJobsStorage__credential": "managedidentity",
  "AzureWebJobsStorage__accountName": "stinvoiceagentprod"
}
```

But function bindings use `"connection": "AzureWebJobsStorage"` expecting connection strings, not identity-based auth.

### 3. Missing Critical Environment Variables
Two webhook-related variables not configured:
- `MAIL_WEBHOOK_URL` - Required by SubscriptionManager
- `GRAPH_CLIENT_STATE` - Required by MailWebhook for security validation

### 4. Python Version Mismatch
- Local environment: Python 3.13 (`src/venv/lib/python3.13`)
- Azure Functions: Configured for Python 3.11
- Potential package compatibility issues

### 5. Key Vault Reference Issues
Simplified format may not resolve properly:
```
@Microsoft.KeyVault(SecretUri=https://kv-name.vault.azure.net/secrets/secret-name/)
```

## Fix Implementation Plan

### Phase 1: Fix Function Configuration (Critical)

#### 1.1 Add scriptFile to All function.json Files
For each affected function, add to function.json:
```json
{
  "scriptFile": "__init__.py",
  "bindings": [...]
}
```

**Files to Update:**
- src/functions/MailIngest/function.json
- src/functions/ExtractEnrich/function.json
- src/functions/PostToAP/function.json
- src/functions/Notify/function.json
- src/functions/AddVendor/function.json

#### 1.2 Fix Storage Connection Configuration

**Option A: Use Connection Strings (Recommended for Quick Fix)**
1. Add storage connection string to Key Vault
2. Reference in Function App settings:
   ```
   AzureWebJobsStorage: @Microsoft.KeyVault(SecretUri=...)
   ```
3. Remove managed identity storage settings

**Option B: Update Bindings for Identity Auth**
1. Modify all queue bindings to support identity-based authentication
2. Update binding extensions if needed
3. Ensure proper RBAC roles (Storage Queue Data Contributor)

### Phase 2: Configure Missing Secrets

#### 2.1 Run Webhook Secrets Configuration
Execute the provided script:
```bash
./configure-webhook-secrets.sh
```

#### 2.2 Add Secrets to Key Vault
```bash
# Add MAIL_WEBHOOK_URL
az keyvault secret set \
  --vault-name kv-invoice-agent-prod \
  --name "MAIL-WEBHOOK-URL" \
  --value "https://func-invoice-agent-prod.azurewebsites.net/api/MailWebhook"

# Add GRAPH_CLIENT_STATE (generate secure random value)
az keyvault secret set \
  --vault-name kv-invoice-agent-prod \
  --name "GRAPH-CLIENT-STATE" \
  --value "$(openssl rand -base64 32)"
```

#### 2.3 Update Function App Settings
```bash
az functionapp config appsettings set \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --settings \
    MAIL_WEBHOOK_URL="@Microsoft.KeyVault(VaultName=kv-invoice-agent-prod;SecretName=MAIL-WEBHOOK-URL)" \
    GRAPH_CLIENT_STATE="@Microsoft.KeyVault(VaultName=kv-invoice-agent-prod;SecretName=GRAPH-CLIENT-STATE)"
```

### Phase 3: Validation & Testing

#### 3.1 Local Testing
```bash
# Set up local environment
cd src
source venv/bin/activate

# Install Python 3.11 dependencies
python3.11 -m pip install -r requirements.txt

# Test function discovery
func start --verbose

# Test individual functions
func start --functions MailIngest
```

#### 3.2 Verify Function Discovery
```bash
# After deployment, verify functions are discovered
az functionapp function list \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod

# Should list all 7 functions with proper trigger types
```

#### 3.3 Test Webhook Validation
```bash
# Test webhook endpoint with validation token
curl -X POST https://func-invoice-agent-prod.azurewebsites.net/api/MailWebhook \
  -H "Content-Type: text/plain" \
  -d "validationToken=test-token-12345"

# Should return the validation token in response
```

#### 3.4 Monitor Queue Creation
```bash
# Check queue depths
az storage queue show \
  --name webhook-notifications \
  --account-name stinvoiceagentprod \
  --query approximateMessageCount

az storage queue show \
  --name raw-mail \
  --account-name stinvoiceagentprod \
  --query approximateMessageCount
```

### Phase 4: Add Monitoring & Error Handling

#### 4.1 Enhance Error Handling
Add comprehensive error handling to each function:
```python
import logging
import traceback

def main(req: func.HttpRequest) -> func.HttpResponse:
    correlation_id = ULID()
    logger = logging.getLogger(__name__)

    try:
        logger.info(f"Function started - Correlation ID: {correlation_id}")

        # Function logic here

        # Queue operation with explicit error handling
        try:
            queue_client.send_message(message)
            logger.info(f"Queue message sent successfully - ID: {correlation_id}")
        except Exception as queue_error:
            logger.error(f"Queue operation failed - ID: {correlation_id}: {queue_error}")
            raise

        return func.HttpResponse(status_code=202)

    except Exception as e:
        logger.error(f"Function failed - ID: {correlation_id}: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )
```

#### 4.2 Add Health Check Endpoints
Create health check function for monitoring:
```python
# src/functions/HealthCheck/__init__.py
def main(req: func.HttpRequest) -> func.HttpResponse:
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {
            "key_vault": check_key_vault_access(),
            "storage": check_storage_access(),
            "graph_api": check_graph_api_access()
        }
    }
    return func.HttpResponse(
        json.dumps(health_status),
        status_code=200,
        headers={"Content-Type": "application/json"}
    )
```

#### 4.3 Set Up Monitoring Alerts
```bash
# Create alert for function failures
az monitor metrics alert create \
  --name "FunctionExecutionFailures" \
  --resource-group rg-invoice-agent-prod \
  --scopes "/subscriptions/{sub-id}/resourceGroups/rg-invoice-agent-prod/providers/Microsoft.Web/sites/func-invoice-agent-prod" \
  --condition "count FailedRequests > 5" \
  --window-size 5m \
  --evaluation-frequency 1m
```

## Testing Checklist

### Pre-Deployment
- [ ] All function.json files have scriptFile directive
- [ ] Storage connection configuration resolved
- [ ] Webhook secrets added to Key Vault
- [ ] Python 3.11 virtual environment used
- [ ] Local function discovery successful (`func start`)
- [ ] Unit tests passing (`pytest`)

### Post-Deployment Staging
- [ ] Functions listed in Azure (`az functionapp function list`)
- [ ] App settings show resolved Key Vault references
- [ ] No startup errors in Application Insights
- [ ] Webhook validation endpoint responds correctly
- [ ] Health check endpoint returns healthy status

### Post-Deployment Production
- [ ] Email triggers create queue messages
- [ ] Messages flow through all queues
- [ ] Database records created
- [ ] Teams notifications sent
- [ ] No poison messages in queues
- [ ] Monitoring alerts configured

## Rollback Plan

If issues persist after fixes:

1. **Immediate Rollback**
   ```bash
   # Swap back to previous slot
   az functionapp deployment slot swap \
     --name func-invoice-agent-prod \
     --resource-group rg-invoice-agent-prod \
     --slot staging \
     --target-slot production
   ```

2. **Revert to Timer-Based Polling**
   - Re-enable 5-minute timer on MailIngest
   - Disable webhook endpoint
   - Monitor for stability

3. **Manual Processing**
   - Use manual trigger for MailIngest
   - Process emails in batches
   - Monitor and fix issues

## Success Metrics

### Immediate (Within 1 hour)
- All 7 functions discovered and callable
- Webhook validation successful
- Queue messages being created

### Short-term (Within 24 hours)
- 100% of emails processed successfully
- <10 second processing latency
- Zero poison messages

### Long-term (Within 1 week)
- 99.9% uptime
- Consistent <10 second latency
- Successful webhook renewal cycles

## Additional Considerations

### Security
- Ensure GRAPH_CLIENT_STATE is kept secret
- Validate all webhook payloads
- Use managed identity where possible
- Regular security scans

### Performance
- Monitor cold start times
- Optimize function initialization
- Consider premium plan if needed
- Implement connection pooling

### Maintenance
- Document all configuration changes
- Update runbooks
- Train team on new webhook flow
- Regular backup of configurations

## Next Steps After Fix

1. **Phase 2 Planning**: PDF extraction and AI vendor matching
2. **Performance Optimization**: Reduce cold starts
3. **Multi-mailbox Support**: Extend to multiple mailboxes
4. **Advanced Monitoring**: Custom dashboards and reports

## Resources

- [Azure Functions Python Developer Guide](https://docs.microsoft.com/azure/azure-functions/functions-reference-python)
- [Microsoft Graph Change Notifications](https://docs.microsoft.com/graph/api/resources/webhooks)
- [Azure Functions Managed Identity](https://docs.microsoft.com/azure/app-service/overview-managed-identity)
- [Key Vault References](https://docs.microsoft.com/azure/app-service/app-service-key-vault-references)

---
*End of Fix Plan - Ready for Implementation*