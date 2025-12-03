// Key Vault module for Invoice Agent
@description('Key Vault name')
param keyVaultName string

@description('Azure region')
param location string

@description('Resource tags')
param tags object

@description('Function App principal ID (Managed Identity)')
param functionAppPrincipalId string = ''

@description('Staging slot principal ID (Managed Identity)')
param stagingSlotPrincipalId string = ''

@description('Log Analytics Workspace ID for diagnostic settings')
param logAnalyticsWorkspaceId string = ''

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
    accessPolicies: [
      // Production slot access policy
      {
        tenantId: subscription().tenantId
        objectId: functionAppPrincipalId
        permissions: {
          secrets: [
            'get'
            'list'
          ]
        }
      }
      // Staging slot access policy
      {
        tenantId: subscription().tenantId
        objectId: stagingSlotPrincipalId
        permissions: {
          secrets: [
            'get'
            'list'
          ]
        }
      }
    ]
  }
}

// Secrets are managed outside of Bicep to prevent accidental overwriting
// Use configure-prod-secrets.sh or Azure Portal to manage secrets

// Diagnostic Settings (AZQR recommendation - audit logging)
resource keyVaultDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (!empty(logAnalyticsWorkspaceId)) {
  name: '${keyVaultName}-diagnostics'
  scope: keyVault
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        category: 'AuditEvent'
        enabled: true
        retentionPolicy: {
          enabled: true
          days: 90
        }
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
        retentionPolicy: {
          enabled: true
          days: 90
        }
      }
    ]
  }
}

// Outputs
output keyVaultName string = keyVault.name
output keyVaultId string = keyVault.id
output keyVaultUri string = keyVault.properties.vaultUri