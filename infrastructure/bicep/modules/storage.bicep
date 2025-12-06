// Storage Account module for Invoice Agent
@description('Storage account name')
param storageAccountName string

@description('Azure region')
param location string

@description('Resource tags')
param tags object

@description('Environment')
@allowed(['dev', 'staging', 'prod'])
param environment string

// Storage Account
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  tags: tags
  sku: {
    name: environment == 'prod' ? 'Standard_GRS' : 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_3'
    allowBlobPublicAccess: false
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

// Blob Service
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    cors: {
      corsRules: []
    }
    // Blob soft delete - recover deleted blobs
    deleteRetentionPolicy: {
      enabled: true
      days: environment == 'prod' ? 30 : 7
    }
    // Container soft delete - recover deleted containers (AZQR recommendation)
    containerDeleteRetentionPolicy: {
      enabled: true
      days: environment == 'prod' ? 30 : 7
    }
  }
}

// Blob Container for Invoices
resource invoiceContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: 'invoices'
  properties: {
    publicAccess: 'None'
  }
}

// Queue Service
resource queueService 'Microsoft.Storage/storageAccounts/queueServices@2023-01-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    cors: {
      corsRules: []
    }
  }
}

// Queues
var queueNames = [
  'raw-mail'
  'raw-mail-poison'
  'to-post'
  'to-post-poison'
  'notify'
  'notify-poison'
]

resource queues 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-01-01' = [for queueName in queueNames: {
  parent: queueService
  name: queueName
  properties: {}
}]

// Table Service
resource tableService 'Microsoft.Storage/storageAccounts/tableServices@2023-01-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    cors: {
      corsRules: []
    }
  }
}

// Tables
var tableNames = [
  'VendorMaster'
  'InvoiceTransactions'
]

resource tables 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-01-01' = [for tableName in tableNames: {
  parent: tableService
  name: tableName
  properties: {}
}]

// Outputs
output storageAccountName string = storageAccount.name
output storageAccountId string = storageAccount.id
@secure()
output connectionString string = 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};EndpointSuffix=${az.environment().suffixes.storage};AccountKey=${storageAccount.listKeys().keys[0].value}'
output blobEndpoint string = storageAccount.properties.primaryEndpoints.blob
output queueEndpoint string = storageAccount.properties.primaryEndpoints.queue
output tableEndpoint string = storageAccount.properties.primaryEndpoints.table