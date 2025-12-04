// Function App module for Invoice Agent
@description('Function App name')
param functionAppName string

@description('App Service Plan name')
param appServicePlanName string

@description('Azure region')
param location string

@description('Resource tags')
param tags object

@description('Storage account name')
param storageAccountName string

@description('Storage account connection string (deprecated - kept for backward compatibility)')
@secure()
param storageAccountConnectionString string = ''

@description('Application Insights instrumentation key')
@secure()
param appInsightsInstrumentationKey string

@description('Key Vault name')
param keyVaultName string

// App Service Plan (Consumption)
resource appServicePlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: appServicePlanName
  location: location
  tags: tags
  sku: {
    name: 'Y1'
    tier: 'Dynamic'
  }
  properties: {
    reserved: true // Linux
  }
}

// Function App
resource functionApp 'Microsoft.Web/sites@2023-01-01' = {
  name: functionAppName
  location: location
  tags: tags
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlan.id
    reserved: true // Linux
    siteConfig: {
      pythonVersion: '3.11'
      linuxFxVersion: 'PYTHON|3.11'
      appSettings: [
        // Identity-based storage connection (recommended - uses Managed Identity)
        {
          name: 'AzureWebJobsStorage__accountName'
          value: storageAccountName
        }
        {
          name: 'AzureWebJobsStorage__blobServiceUri'
          value: 'https://${storageAccountName}.blob.${environment().suffixes.storage}'
        }
        {
          name: 'AzureWebJobsStorage__queueServiceUri'
          value: 'https://${storageAccountName}.queue.${environment().suffixes.storage}'
        }
        {
          name: 'AzureWebJobsStorage__tableServiceUri'
          value: 'https://${storageAccountName}.table.${environment().suffixes.storage}'
        }
        {
          name: 'AzureWebJobsStorage__credential'
          value: 'managedidentity'
        }
        // File share still requires connection string for content management
        {
          name: 'WEBSITE_CONTENTAZUREFILECONNECTIONSTRING'
          value: storageAccountConnectionString
        }
        {
          name: 'WEBSITE_CONTENTSHARE'
          value: toLower(functionAppName)
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
          value: appInsightsInstrumentationKey
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: 'InstrumentationKey=${appInsightsInstrumentationKey}'
        }
        {
          name: 'KEY_VAULT_URL'
          value: 'https://${keyVaultName}.${environment().suffixes.keyvaultDns}/'
        }
        // Key Vault references (Function App will use Managed Identity to access these)
        {
          name: 'GRAPH_TENANT_ID'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVaultName}.vault.azure.net/secrets/graph-tenant-id/)'
        }
        {
          name: 'GRAPH_CLIENT_ID'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVaultName}.vault.azure.net/secrets/graph-client-id/)'
        }
        {
          name: 'GRAPH_CLIENT_SECRET'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVaultName}.vault.azure.net/secrets/graph-client-secret/)'
        }
        {
          name: 'INVOICE_MAILBOX'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVaultName}.vault.azure.net/secrets/invoice-mailbox/)'
        }
        {
          name: 'AP_EMAIL_ADDRESS'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVaultName}.vault.azure.net/secrets/ap-email-address/)'
        }
        {
          name: 'TEAMS_WEBHOOK_URL'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVaultName}.vault.azure.net/secrets/teams-webhook-url/)'
        }
        // Azure OpenAI for PDF vendor extraction
        {
          name: 'AZURE_OPENAI_ENDPOINT'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVaultName}.vault.azure.net/secrets/azure-openai-endpoint/)'
        }
        {
          name: 'AZURE_OPENAI_API_KEY'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVaultName}.vault.azure.net/secrets/azure-openai-api-key/)'
        }
        {
          name: 'WEBSITE_RUN_FROM_PACKAGE'
          value: '1'
        }
        {
          name: 'PYDANTIC_PURE_PYTHON'
          value: '1'
        }
      ]
      cors: {
        allowedOrigins: []
      }
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      scmMinTlsVersion: '1.2'
      http20Enabled: true
      // Auto-heal configuration (AZQR recommendation)
      autoHealEnabled: true
      autoHealRules: {
        triggers: {
          statusCodes: [
            {
              status: 500
              subStatus: 0
              win32Status: 0
              count: 10
              timeInterval: '00:05:00'
            }
          ]
          slowRequests: {
            timeTaken: '00:01:00'
            count: 5
            timeInterval: '00:05:00'
          }
        }
        actions: {
          actionType: 'Recycle'
          minProcessExecutionTime: '00:01:00'
        }
      }
    }
    httpsOnly: true
  }
}

// Staging slot (for blue-green deployment)
resource stagingSlot 'Microsoft.Web/sites/slots@2023-01-01' = {
  parent: functionApp
  name: 'staging'
  location: location
  tags: tags
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlan.id
    reserved: true
    // ⚠️ IMPORTANT: App settings do NOT auto-sync from production to staging.
    // You MUST manually sync app settings from production to staging slot.
    // See: docs/DEPLOYMENT_GUIDE.md "Step 2.5: Configure Staging Slot App Settings"
    // Note: siteConfig is inherited from parent Function App at swap time.
  }
}

// Slot configuration names - defines which settings are "slot-sticky"
// Slot-sticky settings stay with the slot during swaps (don't swap with the code)
// NOTE: AzureWebJobsStorage* settings should NOT be slot-sticky as both slots
// need access to the same storage for triggers (queues, timers) to work correctly.
resource slotConfigNames 'Microsoft.Web/sites/config@2023-01-01' = {
  parent: functionApp
  name: 'slotConfigNames'
  properties: {
    // App settings that stay with the slot (not swapped)
    appSettingNames: [
      // Slot-specific monitoring (optional - enable if you want separate App Insights per slot)
      // 'APPINSIGHTS_INSTRUMENTATIONKEY'
      // 'APPLICATIONINSIGHTS_CONNECTION_STRING'
    ]
    // Connection strings that stay with the slot (not swapped)
    connectionStringNames: []
    // Azure Storage account settings - intentionally NOT included
    // Both slots must use the same storage for queue/timer triggers to function correctly
    azureStorageConfigNames: []
  }
}

// Outputs
output functionAppName string = functionApp.name
output functionAppId string = functionApp.id
output functionAppUrl string = 'https://${functionApp.properties.defaultHostName}'
output functionAppPrincipalId string = functionApp.identity.principalId
output stagingSlotPrincipalId string = stagingSlot.identity.principalId