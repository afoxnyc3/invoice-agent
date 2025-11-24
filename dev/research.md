# Azure Function App Execution Failure - Diagnostic & Fix Guide

## Executive Summary

Your Azure Functions are accepting HTTP requests (202 Accepted) but failing to execute their core logic due to **three critical configuration issues**:

1. **Application Insights logging filter blocking all logs** (preventing visibility into actual errors)
2. **Key Vault references likely misconfigured or permissions missing** (causing silent failures in function startup)
3. **Microsoft Graph webhook validation not properly implemented** (preventing webhook notifications)

**Impact**: Zero pipeline throughput despite 9 unread emails and active webhook subscription.

---

## Root Cause Analysis

### Issue #1: Silent Failures Due to Logging Configuration

**Problem**: .NET isolated Azure Functions include a default Application Insights filter that **only logs Warning level and above**[1][2]. This means your Information, Debug, and Trace logs (including errors during execution) are being silently dropped.

**Why This Matters**: When functions accept requests but don't execute, you need detailed logs to see what's failing internally. Without proper logging configuration, you're flying blind.

**Evidence from Research**:
- Default ApplicationInsights filter captures only warnings and severe logs
- Developers commonly report "functions work locally but fail in Azure with no logs"
- This is the #1 cause of "202 accepted but nothing happens" scenarios

### Issue #2: Key Vault Reference Configuration

**Problem**: Key Vault references in application settings use special syntax that must be exact, and Managed Identity must have proper RBAC permissions. Silent failures occur when:
- Secret URI format is incorrect
- Managed Identity lacks "Get" permission on secrets
- Key Vault firewall blocks Function App
- Key Vault reference syntax is malformed

**Correct Syntax**[3]:
@Microsoft.KeyVault(SecretUri=https://<vault-name>.vault.azure.net/secrets/<secret-name>/<version>)

**Common Issues**:
- Missing version in URI (should use specific version or omit for latest)
- Managed Identity not assigned to Function App
- No access policy or RBAC role for Managed Identity on Key Vault
- Using VaultName syntax instead of SecretUri

### Issue #3: Microsoft Graph Webhook Validation

**Problem**: Microsoft Graph requires webhooks to respond to validation requests with a **200 OK** status and the validation token in plain text[4][5]. Your webhook function must:

1. Check for `validationToken` query parameter
2. Return it immediately with `Content-Type: text/plain`
3. Return HTTP 200 (not 202)

**Why Webhooks Don't Trigger**:
- Validation response not implemented correctly
- Webhook URL not publicly accessible
- Notification URL requires HTTPS
- Function authorization level prevents Graph from calling endpoint

---

## Solution Implementation

### Step 1: Fix Application Insights Logging (CRITICAL - Do This First)

This enables you to see what's actually failing in your functions.

**Update `Program.cs`** (for .NET isolated functions):

using Microsoft.Azure.Functions.Worker;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

var host = new HostBuilder()
    .ConfigureFunctionsWebApplication()
    .ConfigureServices(services =>
    {
        services.AddApplicationInsightsTelemetryWorkerService();
        services.ConfigureFunctionsApplicationInsights();
        
        // CRITICAL: Remove default Application Insights filter
        services.Configure<LoggerFilterOptions>(options =>
        {
            // The Application Insights SDK adds a default logging filter that 
            // instructs ILogger to capture only Warning and more severe logs.
            // This removes that filter so you can see all logs.
            LoggerFilterRule? defaultRule = options.Rules.FirstOrDefault(rule => 
                rule.ProviderName == "Microsoft.Extensions.Logging.ApplicationInsights.ApplicationInsightsLoggerProvider");
            
            if (defaultRule is not null)
            {
                options.Rules.Remove(defaultRule);
            }
        });
    })
    .ConfigureLogging(logging =>
    {
        // Set minimum log level to Information for production
        // Use Trace or Debug for troubleshooting
        logging.SetMinimumLevel(LogLevel.Information);
    })
    .Build();

host.Run();

**Update `host.json`** for enhanced logging:

{
  "version": "2.0",
  "logging": {
    "applicationInsights": {
      "samplingSettings": {
        "isEnabled": false
      },
      "enableDependencyTracking": true
    },
    "logLevel": {
      "default": "Information",
      "Host.Results": "Information",
      "Function": "Information",
      "Host.Aggregator": "Information"
    }
  }
}

**Deploy and Test**: After deploying this change, you'll immediately see detailed logs in Application Insights showing the actual errors.

---

### Step 2: Validate and Fix Key Vault Configuration

#### 2.1 Verify Key Vault Reference Syntax

**Check Application Settings** in Azure Portal:

# List all app settings to verify Key Vault reference syntax
az functionapp config appsettings list \
  --name <function-app-name> \
  --resource-group <resource-group-name> \
  --output table

**Correct Format**:
GRAPH_CLIENT_ID=@Microsoft.KeyVault(SecretUri=https://your-vault.vault.azure.net/secrets/GraphClientId/)
GRAPH_CLIENT_SECRET=@Microsoft.KeyVault(SecretUri=https://your-vault.vault.azure.net/secrets/GraphClientSecret/)
GRAPH_TENANT_ID=@Microsoft.KeyVault(SecretUri=https://your-vault.vault.azure.net/secrets/GraphTenantId/)

**Note**: Omit version to always get latest secret version, or include specific version: `/secrets/SecretName/abc123def456`

#### 2.2 Configure Managed Identity and Permissions

**Enable System-Assigned Managed Identity**:

# Enable system-assigned managed identity for Function App
az functionapp identity assign \
  --name <function-app-name> \
  --resource-group <resource-group-name>

# Save the Principal ID from output
PRINCIPAL_ID=$(az functionapp identity show \
  --name <function-app-name> \
  --resource-group <resource-group-name> \
  --query principalId \
  --output tsv)

echo "Managed Identity Principal ID: $PRINCIPAL_ID"

**Grant Key Vault Permissions** (using RBAC - preferred method):

# Get Key Vault resource ID
VAULT_ID=$(az keyvault show \
  --name <vault-name> \
  --resource-group <resource-group-name> \
  --query id \
  --output tsv)

# Assign "Key Vault Secrets User" role to Function App's Managed Identity
az role assignment create \
  --role "Key Vault Secrets User" \
  --assignee-object-id $PRINCIPAL_ID \
  --assignee-principal-type ServicePrincipal \
  --scope $VAULT_ID

**Alternative: Using Access Policies** (legacy method):

az keyvault set-policy \
  --name <vault-name> \
  --object-id $PRINCIPAL_ID \
  --secret-permissions get list

#### 2.3 Grant Storage Account Permissions

Your Managed Identity also needs access to Azure Storage for queue operations:

# Get storage account name from function app
STORAGE_ACCOUNT=$(az functionapp show \
  --name <function-app-name> \
  --resource-group <resource-group-name> \
  --query storageAccount \
  --output tsv)

# Get storage account resource ID
STORAGE_ID=$(az storage account show \
  --name $STORAGE_ACCOUNT \
  --query id \
  --output tsv)

# Assign Storage Queue Data Contributor role
az role assignment create \
  --role "Storage Queue Data Contributor" \
  --assignee-object-id $PRINCIPAL_ID \
  --assignee-principal-type ServicePrincipal \
  --scope $STORAGE_ID

# Assign Storage Blob Data Contributor role (if using blob storage)
az role assignment create \
  --role "Storage Blob Data Contributor" \
  --assignee-object-id $PRINCIPAL_ID \
  --assignee-principal-type ServicePrincipal \
  --scope $STORAGE_ID

#### 2.4 Verify Key Vault Firewall Settings

# Check if Key Vault has network restrictions
az keyvault show \
  --name <vault-name> \
  --query "properties.networkAcls" \
  --output json

# If firewall is enabled, add Function App outbound IPs or enable "Allow trusted Microsoft services"
az keyvault update \
  --name <vault-name> \
  --resource-group <resource-group-name> \
  --bypass AzureServices

---

### Step 3: Fix Microsoft Graph Webhook Function

Your webhook function must handle two scenarios: validation and notification processing.

**Correct Implementation Pattern**:

using Microsoft.Azure.Functions.Worker;
using Microsoft.Azure.Functions.Worker.Http;
using Microsoft.Extensions.Logging;
using System.Net;
using System.Text.Json;

public class MailWebhook
{
    private readonly ILogger<MailWebhook> _logger;

    public MailWebhook(ILogger<MailWebhook> logger)
    {
        _logger = logger;
    }

    [Function("MailWebhook")]
    public async Task<HttpResponseData> Run(
        [HttpTrigger(AuthorizationLevel.Anonymous, "post", Route = "webhook/mail")] 
        HttpRequestData req)
    {
        _logger.LogInformation("Mail webhook triggered");

        // STEP 1: Handle validation request from Microsoft Graph
        // Graph sends validation token as query parameter on subscription creation
        var validationToken = req.Query["validationToken"];
        
        if (!string.IsNullOrEmpty(validationToken))
        {
            _logger.LogInformation("Validation request received. Token: {Token}", validationToken);
            
            // CRITICAL: Must return 200 OK with token as plain text
            var response = req.CreateResponse(HttpStatusCode.OK);
            response.Headers.Add("Content-Type", "text/plain");
            await response.WriteStringAsync(validationToken);
            
            return response;
        }

        // STEP 2: Handle actual notification
        try
        {
            var body = await new StreamReader(req.Body).ReadToEndAsync();
            _logger.LogInformation("Notification received: {Body}", body);

            if (string.IsNullOrEmpty(body))
            {
                _logger.LogWarning("Empty notification body received");
                return req.CreateResponse(HttpStatusCode.BadRequest);
            }

            var notification = JsonSerializer.Deserialize<GraphNotification>(body);
            
            if (notification?.Value == null || !notification.Value.Any())
            {
                _logger.LogWarning("No notification values in payload");
                return req.CreateResponse(HttpStatusCode.BadRequest);
            }

            // Verify client state matches your subscription
            foreach (var item in notification.Value)
            {
                _logger.LogInformation(
                    "Processing notification - Resource: {Resource}, ChangeType: {ChangeType}",
                    item.Resource,
                    item.ChangeType);

                if (item.ClientState != "YourExpectedClientState")
                {
                    _logger.LogWarning("Client state mismatch. Expected: YourExpectedClientState, Got: {ClientState}", 
                        item.ClientState);
                    continue;
                }

                // TODO: Process the notification
                // - Enqueue message to storage queue
                // - Create transaction record
                await ProcessNotificationAsync(item);
            }

            // Return 202 Accepted for async processing
            return req.CreateResponse(HttpStatusCode.Accepted);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error processing webhook notification");
            return req.CreateResponse(HttpStatusCode.InternalServerError);
        }
    }

    private async Task ProcessNotificationAsync(NotificationItem item)
    {
        // Your processing logic here
        _logger.LogInformation("Processing notification for resource: {Resource}", item.Resource);
        
        // Add to queue, create transaction, etc.
    }
}

// Models for deserialization
public class GraphNotification
{
    public List<NotificationItem> Value { get; set; }
}

public class NotificationItem
{
    public string SubscriptionId { get; set; }
    public string ClientState { get; set; }
    public string ChangeType { get; set; }
    public string Resource { get; set; }
    public DateTimeOffset SubscriptionExpirationDateTime { get; set; }
    public string ResourceData { get; set; }
}

**Critical Requirements for Graph Webhooks**:

1. **Authorization Level**: Must be `Anonymous` or have proper authentication that Graph can satisfy
2. **HTTPS**: Notification URL must use HTTPS (Azure Functions provides this by default)
3. **Publicly Accessible**: No authentication required for validation token request
4. **Response Time**: Must respond to validation within 10 seconds
5. **Status Code**: Return 200 OK for validation, 202 Accepted for notifications

**Update Function Configuration**:

// function.json (if using function.json instead of attributes)
{
  "bindings": [
    {
      "authLevel": "anonymous",
      "type": "httpTrigger",
      "direction": "in",
      "name": "req",
      "methods": ["post"]
    },
    {
      "type": "http",
      "direction": "out",
      "name": "res"
    }
  ]
}

---

### Step 4: Fix MailIngest Function Queue Output Binding

The MailIngest function accepting HTTP 202 but not creating queue messages indicates a binding configuration or execution issue.

**Verify Queue Output Binding Configuration**:

using Azure.Storage.Queues.Models;
using Microsoft.Azure.Functions.Worker;
using Microsoft.Azure.Functions.Worker.Http;
using Microsoft.Extensions.Logging;
using System.Net;

public class MailIngest
{
    private readonly ILogger<MailIngest> _logger;

    public MailIngest(ILogger<MailIngest> logger)
    {
        _logger = logger;
    }

    [Function("MailIngest")]
    [QueueOutput("mail-processing-queue", Connection = "AzureWebJobsStorage")]
    public async Task<MultiResponse> Run(
        [HttpTrigger(AuthorizationLevel.Function, "post", Route = "mail/ingest")] 
        HttpRequestData req)
    {
        _logger.LogInformation("MailIngest function triggered");

        try
        {
            var body = await new StreamReader(req.Body).ReadToEndAsync();
            _logger.LogInformation("Request body received: {Body}", body);

            if (string.IsNullOrEmpty(body))
            {
                _logger.LogWarning("Empty request body");
                var errorResponse = req.CreateResponse(HttpStatusCode.BadRequest);
                await errorResponse.WriteStringAsync("Request body is required");
                return new MultiResponse { HttpResponse = errorResponse };
            }

            // Validate and parse request
            var mailRequest = JsonSerializer.Deserialize<MailIngestRequest>(body);
            
            if (mailRequest == null)
            {
                _logger.LogWarning("Failed to deserialize request");
                var errorResponse = req.CreateResponse(HttpStatusCode.BadRequest);
                await errorResponse.WriteStringAsync("Invalid request format");
                return new MultiResponse { HttpResponse = errorResponse };
            }

            _logger.LogInformation("Creating queue message for mail ID: {MailId}", mailRequest.MailId);

            // Create queue message
            var queueMessage = JsonSerializer.Serialize(new
            {
                mailRequest.MailId,
                mailRequest.Subject,
                ProcessedAt = DateTime.UtcNow,
                Status = "Pending"
            });

            _logger.LogInformation("Queue message created: {Message}", queueMessage);

            var response = req.CreateResponse(HttpStatusCode.Accepted);
            await response.WriteStringAsync($"Mail {mailRequest.MailId} queued for processing");

            return new MultiResponse 
            { 
                HttpResponse = response,
                QueueMessage = queueMessage
            };
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error in MailIngest function");
            var errorResponse = req.CreateResponse(HttpStatusCode.InternalServerError);
            await errorResponse.WriteStringAsync($"Error: {ex.Message}");
            return new MultiResponse { HttpResponse = errorResponse };
        }
    }
}

public class MultiResponse
{
    [HttpResponse]
    public HttpResponseData HttpResponse { get; set; }

    [QueueOutput("mail-processing-queue", Connection = "AzureWebJobsStorage")]
    public string QueueMessage { get; set; }
}

public class MailIngestRequest
{
    public string MailId { get; set; }
    public string Subject { get; set; }
    public string From { get; set; }
}

**Alternative Pattern Using QueueClient Directly**:

If output binding isn't working, use Azure Storage SDK directly:

using Azure.Storage.Queues;
using Microsoft.Extensions.Configuration;

public class MailIngest
{
    private readonly ILogger<MailIngest> _logger;
    private readonly QueueClient _queueClient;

    public MailIngest(ILogger<MailIngest> logger, IConfiguration configuration)
    {
        _logger = logger;
        
        var connectionString = configuration["AzureWebJobsStorage"];
        _queueClient = new QueueClient(connectionString, "mail-processing-queue");
        _queueClient.CreateIfNotExists();
    }

    [Function("MailIngest")]
    public async Task<HttpResponseData> Run(
        [HttpTrigger(AuthorizationLevel.Function, "post")] HttpRequestData req)
    {
        _logger.LogInformation("MailIngest triggered");

        try
        {
            var body = await new StreamReader(req.Body).ReadToEndAsync();
            var mailRequest = JsonSerializer.Deserialize<MailIngestRequest>(body);

            // Create queue message directly
            var message = JsonSerializer.Serialize(new
            {
                mailRequest.MailId,
                mailRequest.Subject,
                QueuedAt = DateTime.UtcNow
            });

            _logger.LogInformation("Sending message to queue: {Message}", message);
            
            var result = await _queueClient.SendMessageAsync(message);
            
            _logger.LogInformation("Message queued successfully. MessageId: {MessageId}", result.Value.MessageId);

            var response = req.CreateResponse(HttpStatusCode.Accepted);
            await response.WriteStringAsync($"Queued: {result.Value.MessageId}");
            return response;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to queue message");
            return req.CreateResponse(HttpStatusCode.InternalServerError);
        }
    }
}

**Update `Program.cs` to register QueueClient**:

var host = new HostBuilder()
    .ConfigureFunctionsWebApplication()
    .ConfigureServices((context, services) =>
    {
        services.AddApplicationInsightsTelemetryWorkerService();
        services.ConfigureFunctionsApplicationInsights();
        
        // Register QueueClient as singleton
        services.AddSingleton(sp =>
        {
            var config = sp.GetRequiredService<IConfiguration>();
            var connectionString = config["AzureWebJobsStorage"];
            return new QueueClient(connectionString, "mail-processing-queue");
        });
    })
    .Build();

---

### Step 5: Implement Comprehensive Health Checks

Create health check functions to validate each component:

using Azure.Identity;
using Azure.Security.KeyVault.Secrets;
using Azure.Storage.Queues;
using Microsoft.Graph;

public class HealthCheck
{
    private readonly ILogger<HealthCheck> _logger;
    private readonly IConfiguration _configuration;

    public HealthCheck(ILogger<HealthCheck> logger, IConfiguration configuration)
    {
        _logger = logger;
        _configuration = configuration;
    }

    [Function("HealthCheck")]
    public async Task<HttpResponseData> Run(
        [HttpTrigger(AuthorizationLevel.Function, "get", Route = "health")] 
        HttpRequestData req)
    {
        _logger.LogInformation("Health check initiated");

        var healthStatus = new Dictionary<string, object>();

        // Check 1: Key Vault Access
        try
        {
            var vaultUrl = _configuration["KEY_VAULT_URL"];
            var client = new SecretClient(new Uri(vaultUrl), new DefaultAzureCredential());
            
            var secret = await client.GetSecretAsync("GRAPH_CLIENT_ID");
            healthStatus["keyVault"] = new { status = "healthy", message = "Successfully retrieved secret" };
            _logger.LogInformation("Key Vault check: PASS");
        }
        catch (Exception ex)
        {
            healthStatus["keyVault"] = new { status = "unhealthy", error = ex.Message };
            _logger.LogError(ex, "Key Vault check: FAIL");
        }

        // Check 2: Storage Queue Access
        try
        {
            var connectionString = _configuration["AzureWebJobsStorage"];
            var queueClient = new QueueClient(connectionString, "mail-processing-queue");
            
            await queueClient.CreateIfNotExistsAsync();
            var properties = await queueClient.GetPropertiesAsync();
            
            healthStatus["storageQueue"] = new 
            { 
                status = "healthy", 
                queueName = queueClient.Name,
                messageCount = properties.Value.ApproximateMessagesCount 
            };
            _logger.LogInformation("Storage Queue check: PASS - {Count} messages", 
                properties.Value.ApproximateMessagesCount);
        }
        catch (Exception ex)
        {
            healthStatus["storageQueue"] = new { status = "unhealthy", error = ex.Message };
            _logger.LogError(ex, "Storage Queue check: FAIL");
        }

        // Check 3: Microsoft Graph API Access
        try
        {
            var clientId = _configuration["GRAPH_CLIENT_ID"];
            var clientSecret = _configuration["GRAPH_CLIENT_SECRET"];
            var tenantId = _configuration["GRAPH_TENANT_ID"];

            var credential = new ClientSecretCredential(tenantId, clientId, clientSecret);
            var graphClient = new GraphServiceClient(credential);

            var messages = await graphClient.Me.Messages
                .GetAsync(config => config.QueryParameters.Top = 1);

            healthStatus["graphApi"] = new 
            { 
                status = "healthy", 
                message = "Successfully authenticated and queried Graph API" 
            };
            _logger.LogInformation("Microsoft Graph check: PASS");
        }
        catch (Exception ex)
        {
            healthStatus["graphApi"] = new { status = "unhealthy", error = ex.Message };
            _logger.LogError(ex, "Microsoft Graph check: FAIL");
        }

        // Check 4: Application Settings
        var requiredSettings = new[] 
        { 
            "GRAPH_CLIENT_ID", 
            "GRAPH_CLIENT_SECRET", 
            "GRAPH_TENANT_ID",
            "AzureWebJobsStorage" 
        };

        var missingSettings = requiredSettings
            .Where(s => string.IsNullOrEmpty(_configuration[s]))
            .ToList();

        healthStatus["configuration"] = missingSettings.Any()
            ? new { status = "unhealthy", missingSettings }
            : new { status = "healthy", message = "All required settings present" };

        // Overall status
        var allHealthy = healthStatus.Values
            .All(v => ((dynamic)v).status == "healthy");

        var response = req.CreateResponse(allHealthy ? HttpStatusCode.OK : HttpStatusCode.ServiceUnavailable);
        await response.WriteAsJsonAsync(new
        {
            overallStatus = allHealthy ? "healthy" : "unhealthy",
            timestamp = DateTime.UtcNow,
            checks = healthStatus
        });

        return response;
    }
}

---

## Deployment & Testing Checklist

### Pre-Deployment Validation

- [ ] Updated `Program.cs` to remove Application Insights filter
- [ ] Updated `host.json` with enhanced logging configuration
- [ ] Verified Key Vault reference syntax in all app settings
- [ ] Enabled Managed Identity on Function App
- [ ] Assigned "Key Vault Secrets User" RBAC role to Managed Identity
- [ ] Assigned "Storage Queue Data Contributor" role to Managed Identity
- [ ] Verified Key Vault firewall allows Function App access
- [ ] Updated MailWebhook function to handle validation token
- [ ] Set MailWebhook authorization level to Anonymous
- [ ] Updated MailIngest function with proper queue output binding
- [ ] Added health check function

### Deployment Steps

# 1. Build the project
dotnet build --configuration Release

# 2. Publish to Azure
func azure functionapp publish <function-app-name>

# 3. Restart Function App to apply configuration changes
az functionapp restart \
  --name <function-app-name> \
  --resource-group <resource-group-name>

# 4. Wait 30 seconds for startup
sleep 30

### Post-Deployment Testing

#### Test 1: Health Check

# Get function key
FUNCTION_KEY=$(az functionapp function keys list \
  --name <function-app-name> \
  --resource-group <resource-group-name> \
  --function-name HealthCheck \
  --query default \
  --output tsv)

# Call health check endpoint
curl "https://<function-app-name>.azurewebsites.net/api/health?code=$FUNCTION_KEY"

**Expected Result**: All checks return "healthy" status.

#### Test 2: Application Insights Logging

# Query Application Insights for recent logs
az monitor app-insights query \
  --app <app-insights-name> \
  --analytics-query "traces | where timestamp > ago(5m) | order by timestamp desc | take 20" \
  --output table

**Expected Result**: You should now see Information-level logs from your functions.

#### Test 3: Key Vault Reference Resolution

# Check if Key Vault references resolved successfully
az functionapp config appsettings list \
  --name <function-app-name> \
  --resource-group <resource-group-name> \
  --query "[?contains(value, '@Microsoft.KeyVault')]" \
  --output table

# Check for Key Vault reference errors in logs
az monitor app-insights query \
  --app <app-insights-name> \
  --analytics-query "traces | where message contains 'KeyVault' | where timestamp > ago(10m)" \
  --output table

**Expected Result**: No Key Vault errors in logs. Settings with `@Microsoft.KeyVault` prefix should resolve.

#### Test 4: Microsoft Graph Webhook Validation

First, get your webhook URL:

WEBHOOK_URL="https://<function-app-name>.azurewebsites.net/api/webhook/mail"

Test validation manually:

# Simulate Graph validation request
curl "$WEBHOOK_URL?validationToken=test-validation-123"

**Expected Result**: Response should be `200 OK` with body `test-validation-123`

Create actual subscription:

# Get access token for Graph API
ACCESS_TOKEN=$(az account get-access-token --resource https://graph.microsoft.com --query accessToken --output tsv)

# Create webhook subscription
curl -X POST "https://graph.microsoft.com/v1.0/subscriptions" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "changeType": "created,updated",
    "notificationUrl": "'$WEBHOOK_URL'",
    "resource": "me/mailFolders('Inbox')/messages",
    "expirationDateTime": "'$(date -u -d '+3 days' +%Y-%m-%dT%H:%M:%S.0000000Z)'",
    "clientState": "YourExpectedClientState"
  }'

**Expected Result**: Subscription created successfully with subscription ID returned.

#### Test 5: Queue Message Creation

# Test MailIngest function
INGEST_KEY=$(az functionapp function keys list \
  --name <function-app-name> \
  --resource-group <resource-group-name> \
  --function-name MailIngest \
  --query default \
  --output tsv)

curl -X POST "https://<function-app-name>.azurewebsites.net/api/mail/ingest?code=$INGEST_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "mailId": "test-123",
    "subject": "Test Email",
    "from": "test@example.com"
  }'

**Expected Result**: 
- Response: `202 Accepted`
- Check queue for message:

# Verify message was created in queue
az storage message peek \
  --queue-name mail-processing-queue \
  --account-name <storage-account-name> \
  --num-messages 5

#### Test 6: End-to-End Pipeline Test

Send a test email to trigger the webhook:

1. Send email to the monitored mailbox
2. Wait 10-30 seconds for webhook notification
3. Check Application Insights for webhook trigger:

az monitor app-insights query \
  --app <app-insights-name> \
  --analytics-query "
    traces 
    | where timestamp > ago(2m) 
    | where message contains 'webhook' or message contains 'notification'
    | order by timestamp desc
  " \
  --output table

4. Verify queue message created:

az storage message peek \
  --queue-name mail-processing-queue \
  --account-name <storage-account-name> \
  --num-messages 10

5. Check for processing by queue-triggered function

---

## Monitoring & Alerting Setup

### Application Insights Queries for Ongoing Monitoring

**Save these as custom queries in Application Insights:**

#### 1. Function Execution Failures

requests
| where timestamp > ago(1h)
| where success == false
| summarize FailureCount=count() by name, resultCode
| order by FailureCount desc

#### 2. Queue Message Processing Rate

traces
| where timestamp > ago(1h)
| where message contains "queue" or message contains "processing"
| summarize MessageCount=count() by bin(timestamp, 5m)
| render timechart

#### 3. Webhook Notification Tracking

traces
| where timestamp > ago(1h)
| where message contains "webhook" or message contains "notification"
| project timestamp, severityLevel, message
| order by timestamp desc

#### 4. Key Vault Access Errors

exceptions
| where timestamp > ago(1h)
| where outerMessage contains "KeyVault" or outerMessage contains "Secret"
| project timestamp, problemId, outerMessage, innermostMessage

### Azure Monitor Alerts

Create alerts for critical failures:

# Alert on function failures
az monitor metrics alert create \
  --name "FunctionAppFailures" \
  --resource-group <resource-group-name> \
  --scopes /subscriptions/<subscription-id>/resourceGroups/<resource-group-name>/providers/Microsoft.Web/sites/<function-app-name> \
  --condition "count FunctionExecutionCount < 1" \
  --window-size 5m \
  --evaluation-frequency 5m

# Alert on queue depth growth (indicating processing stopped)
az monitor metrics alert create \
  --name "QueueDepthHigh" \
  --resource-group <resource-group-name> \
  --scopes /subscriptions/<subscription-id>/resourceGroups/<resource-group-name>/providers/Microsoft.Storage/storageAccounts/<storage-account-name> \
  --condition "total ApproximateMessageCount > 100" \
  --window-size 15m \
  --evaluation-frequency 5m

---

## Common Issues & Troubleshooting

### Issue: "202 Accepted but Function Doesn't Execute"

**Symptoms**: HTTP requests return 202, no logs appear, no queue messages created.

**Root Causes**:
1. **Logging filter blocking visibility** → Fixed by Step 1
2. **Key Vault reference failure during startup** → Fixed by Step 2
3. **Missing Managed Identity permissions** → Fixed by Step 2
4. **Binding configuration error** → Fixed by Step 4

**Debugging Steps**:
# Check Function App logs in real-time
az webapp log tail \
  --name <function-app-name> \
  --resource-group <resource-group-name>

# Check for startup errors
az monitor app-insights query \
  --app <app-insights-name> \
  --analytics-query "traces | where message contains 'Host' or message contains 'startup' | where timestamp > ago(15m)"

### Issue: "Webhook Not Triggering"

**Symptoms**: Subscription created successfully, but no notifications received.

**Root Causes**:
1. Validation not implemented correctly
2. Function URL not publicly accessible
3. Authorization level blocking requests
4. Subscription expired

**Debugging Steps**:
# Test webhook URL accessibility
curl -I "https://<function-app-name>.azurewebsites.net/api/webhook/mail"

# Check subscription status
curl -X GET "https://graph.microsoft.com/v1.0/subscriptions/<subscription-id>" \
  -H "Authorization: Bearer $ACCESS_TOKEN"

# Verify notification URL matches exactly
# Check expiration date hasn't passed

### Issue: "Queue Messages Not Created"

**Symptoms**: Function executes, logs show success, but queue remains empty.

**Root Causes**:
1. Connection string incorrect or missing
2. Queue name mismatch
3. Managed Identity lacks Storage permissions
4. Output binding not configured correctly

**Debugging Steps**:
# Verify connection string resolves
az functionapp config appsettings list \
  --name <function-app-name> \
  --resource-group <resource-group-name> \
  --query "[?name=='AzureWebJobsStorage'].value" \
  --output tsv

# Check queue exists
az storage queue exists \
  --name mail-processing-queue \
  --account-name <storage-account-name>

# Verify RBAC permissions
az role assignment list \
  --assignee $PRINCIPAL_ID \
  --scope $STORAGE_ID \
  --output table

### Issue: "Key Vault Reference Not Resolving"

**Symptoms**: App settings show `@Microsoft.KeyVault(...)` in portal, function fails to start.

**Root Causes**:
1. Managed Identity not assigned
2. No access policy or RBAC role
3. Incorrect secret URI
4. Key Vault firewall blocking access

**Debugging Steps**:
# Check if Managed Identity is enabled
az functionapp identity show \
  --name <function-app-name> \
  --resource-group <resource-group-name>

# Check RBAC assignments
az role assignment list \
  --assignee $PRINCIPAL_ID \
  --all \
  --output table

# Test Key Vault access manually
az keyvault secret show \
  --vault-name <vault-name> \
  --name <secret-name>

# Check for Key Vault reference resolution status
az resource show \
  --ids /subscriptions/<subscription-id>/resourceGroups/<resource-group-name>/providers/Microsoft.Web/sites/<function-app-name>/config/appsettings \
  --query properties \
  --output json

---

## Prevention: Best Practices Going Forward

### 1. Always Configure Logging First

When debugging Azure Functions:
- Remove Application Insights default filter immediately
- Set log level to Information minimum, Debug/Trace for troubleshooting
- Enable dependency tracking in host.json
- Disable sampling during development and debugging

### 2. Use Managed Identity for All Azure Resources

- Enable system-assigned identity on Function App
- Use RBAC roles instead of access keys
- Grant least-privilege permissions (e.g., "Key Vault Secrets User" not "Key Vault Administrator")
- Document all role assignments

### 3. Validate Configurations in Non-Production First

- Test Key Vault references in dev/staging before production
- Verify webhook validation logic works locally with ngrok
- Test queue bindings with small message volumes first
- Use health check endpoint to validate all dependencies

### 4. Implement Comprehensive Error Handling

// Always wrap function code in try-catch
try
{
    _logger.LogInformation("Starting operation");
    // Your logic here
    _logger.LogInformation("Operation completed successfully");
}
catch (Exception ex)
{
    _logger.LogError(ex, "Operation failed: {Message}", ex.Message);
    // Return appropriate error response
    throw; // Re-throw if function should be retried
}

### 5. Add Telemetry and Metrics

// Track custom metrics
_logger.LogMetric("MailsProcessed", 1, new Dictionary<string, object>
{
    ["MailId"] = mailId,
    ["ProcessingTimeMs"] = stopwatch.ElapsedMilliseconds
});

### 6. Monitor Queue Depth

Set up alerts for:
- Queue depth growing beyond threshold (indicates processing stopped)
- Messages with high dequeue count (indicates repeated failures)
- Old messages (indicates stale data)

### 7. Document Function Dependencies

Create a dependency map:
MailWebhook Function
├── Depends On: Microsoft Graph API webhook subscription
├── Requires: Anonymous authorization level
├── Outputs To: mail-processing-queue
└── Secrets: GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET, GRAPH_TENANT_ID

MailIngest Function
├── Triggered By: HTTP POST
├── Requires: Function-level authorization
├── Outputs To: mail-processing-queue
└── Secrets: AzureWebJobsStorage

---

## Summary: Implementation Order

**Phase 1: Enable Visibility** (15 minutes)
1. Update `Program.cs` to remove Application Insights filter
2. Update `host.json` for enhanced logging
3. Deploy changes
4. Verify logs now appear in Application Insights

**Phase 2: Fix Key Vault** (20 minutes)
1. Enable Managed Identity
2. Verify Key Vault reference syntax
3. Assign RBAC roles for Key Vault
4. Assign RBAC roles for Storage
5. Test health check endpoint

**Phase 3: Fix Webhook** (15 minutes)
1. Update MailWebhook function to handle validation
2. Set authorization level to Anonymous
3. Deploy and test validation
4. Create Graph subscription

**Phase 4: Fix Queue Output** (15 minutes)
1. Update MailIngest function with queue output binding
2. Add comprehensive logging
3. Deploy and test queue message creation

**Phase 5: End-to-End Testing** (30 minutes)
1. Send test email to trigger webhook
2. Verify webhook notification received
3. Verify queue message created
4. Verify queue processor consumes message
5. Verify transaction record created

**Total Estimated Time**: 95 minutes

---

## References

[1] Microsoft Learn: Configure monitoring for Azure Functions - https://learn.microsoft.com/en-us/azure/azure-functions/configure-monitoring

[2] Microsoft Learn: Managing log levels in isolated process Functions - https://learn.microsoft.com/en-us/azure/azure-functions/dotnet-isolated-process-guide#managing-log-levels

[3] Microsoft Learn: Use Key Vault references as App Settings - https://learn.microsoft.com/en-us/azure/app-service/app-service-key-vault-references

[4] Microsoft Learn: Receive change notifications through webhooks - https://learn.microsoft.com/en-us/graph/change-notifications-delivery-webhooks

[5] Dev.to: Graph Change Notification Web Hook with Azure Functions - https://dev.to/425show/graph-change-notification-web-hook-with-azure-functions-l4i

## Next Steps

After implementing these fixes:

1. **Monitor for 24 hours** - Verify all 9 unread emails are processed
2. **Review Application Insights** - Check for any remaining errors
3. **Load test** - Send multiple emails to verify pipeline throughput
4. **Document** - Update runbook with final configuration
5. **Set up alerts** - Implement monitoring alerts for production

The root cause of your "202 Accepted but not executing" issue is almost certainly the combination of **missing Application Insights logs** (preventing you from seeing the actual errors) and **Key Vault reference configuration issues** (causing silent startup failures). Once you implement Step 1 (logging), you'll immediately see what's actually failing, and the subsequent steps will resolve those issues.