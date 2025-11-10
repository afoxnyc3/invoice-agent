// Main Bicep template for Invoice Agent infrastructure
targetScope = 'resourceGroup'

// Parameters
@description('Environment name')
@allowed(['dev', 'staging', 'prod'])
param environment string = 'dev'

@description('Azure region for resources')
param location string = resourceGroup().location

@description('Project name prefix')
param projectPrefix string = 'invoice-agent'

@description('Tags to apply to all resources')
param tags object = {
  Project: 'InvoiceAgent'
  Environment: environment
  Owner: 'AlexFox'
  ManagedBy: 'Bicep'
}

// Variables
var namingPrefix = '${projectPrefix}-${environment}'
var storageAccountName = replace('st${projectPrefix}${environment}', '-', '')
var functionAppName = 'func-${namingPrefix}'
var appServicePlanName = 'asp-${namingPrefix}'
var keyVaultName = 'kv-${take(namingPrefix, 20)}'
var appInsightsName = 'ai-${namingPrefix}'
var workspaceName = 'log-${namingPrefix}'

// Storage Account
module storage './modules/storage.bicep' = {
  name: 'storage-deployment'
  params: {
    storageAccountName: storageAccountName
    location: location
    tags: tags
    environment: environment
  }
}

// Application Insights
module monitoring './modules/monitoring.bicep' = {
  name: 'monitoring-deployment'
  params: {
    appInsightsName: appInsightsName
    workspaceName: workspaceName
    location: location
    tags: tags
  }
}

// Key Vault
module keyVault './modules/keyvault.bicep' = {
  name: 'keyvault-deployment'
  params: {
    keyVaultName: keyVaultName
    location: location
    tags: tags
  }
}

// Function App
module functionApp './modules/functionapp.bicep' = {
  name: 'functionapp-deployment'
  params: {
    functionAppName: functionAppName
    appServicePlanName: appServicePlanName
    location: location
    tags: tags
    storageAccountName: storage.outputs.storageAccountName
    storageAccountConnectionString: storage.outputs.connectionString
    appInsightsInstrumentationKey: monitoring.outputs.instrumentationKey
    keyVaultName: keyVault.outputs.keyVaultName
  }
}

// Outputs
output functionAppName string = functionApp.outputs.functionAppName
output functionAppUrl string = functionApp.outputs.functionAppUrl
output storageAccountName string = storage.outputs.storageAccountName
output keyVaultName string = keyVault.outputs.keyVaultName
output keyVaultUri string = keyVault.outputs.keyVaultUri
output appInsightsInstrumentationKey string = monitoring.outputs.instrumentationKey