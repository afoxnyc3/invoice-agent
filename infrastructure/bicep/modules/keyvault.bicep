// Key Vault module for Invoice Agent
@description('Key Vault name')
param keyVaultName string

@description('Azure region')
param location string

@description('Resource tags')
param tags object

// Key Vault
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enabledForDeployment: false
    enabledForTemplateDeployment: true
    enabledForDiskEncryption: false
    enableRbacAuthorization: false
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    enablePurgeProtection: true
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
    accessPolicies: []
  }
}

// Placeholder secrets (will be populated post-deployment)
var secrets = [
  {
    name: 'graph-tenant-id'
    value: 'placeholder-update-after-deployment'
  }
  {
    name: 'graph-client-id'
    value: 'placeholder-update-after-deployment'
  }
  {
    name: 'graph-client-secret'
    value: 'placeholder-update-after-deployment'
  }
  {
    name: 'ap-email-address'
    value: 'accountspayable@chelseapiers.com'
  }
  {
    name: 'teams-webhook-url'
    value: 'placeholder-update-after-deployment'
  }
]

resource keyVaultSecrets 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = [for secret in secrets: {
  parent: keyVault
  name: secret.name
  properties: {
    value: secret.value
  }
}]

// Outputs
output keyVaultName string = keyVault.name
output keyVaultId string = keyVault.id
output keyVaultUri string = keyVault.properties.vaultUri