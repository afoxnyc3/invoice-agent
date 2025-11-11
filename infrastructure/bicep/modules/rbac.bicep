// RBAC Role Assignments module for Invoice Agent
// Assigns required roles to Function App Managed Identity for secure access

@description('Function App principal ID (Managed Identity)')
param functionAppPrincipalId string

@description('Staging slot principal ID (Managed Identity)')
param stagingSlotPrincipalId string

@description('Storage Account resource ID')
param storageAccountId string

@description('Key Vault resource ID')
param keyVaultId string

// Built-in Azure Role Definition IDs
// See: https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles
var roles = {
  storageBlobDataContributor: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
  storageQueueDataContributor: '974c5e8b-45b9-4653-ba55-5f855dd0fb88'
  storageTableDataContributor: '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3'
  keyVaultSecretsUser: '4633458b-17de-408a-b874-0445c86b69e6'
}

// Declare existing resources for scoping role assignments
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: split(storageAccountId, '/')[8]
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: split(keyVaultId, '/')[8]
}

// Storage Blob Data Contributor - Production Slot
resource blobRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccountId, functionAppPrincipalId, roles.storageBlobDataContributor)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.storageBlobDataContributor)
    principalId: functionAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Storage Queue Data Contributor - Production Slot
resource queueRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccountId, functionAppPrincipalId, roles.storageQueueDataContributor)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.storageQueueDataContributor)
    principalId: functionAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Storage Table Data Contributor - Production Slot
resource tableRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccountId, functionAppPrincipalId, roles.storageTableDataContributor)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.storageTableDataContributor)
    principalId: functionAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Key Vault Secrets User - Production Slot
resource keyVaultRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVaultId, functionAppPrincipalId, roles.keyVaultSecretsUser)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.keyVaultSecretsUser)
    principalId: functionAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Storage Blob Data Contributor - Staging Slot
resource blobRoleAssignmentStaging 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccountId, stagingSlotPrincipalId, roles.storageBlobDataContributor)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.storageBlobDataContributor)
    principalId: stagingSlotPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Storage Queue Data Contributor - Staging Slot
resource queueRoleAssignmentStaging 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccountId, stagingSlotPrincipalId, roles.storageQueueDataContributor)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.storageQueueDataContributor)
    principalId: stagingSlotPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Storage Table Data Contributor - Staging Slot
resource tableRoleAssignmentStaging 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccountId, stagingSlotPrincipalId, roles.storageTableDataContributor)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.storageTableDataContributor)
    principalId: stagingSlotPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Key Vault Secrets User - Staging Slot
resource keyVaultRoleAssignmentStaging 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVaultId, stagingSlotPrincipalId, roles.keyVaultSecretsUser)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.keyVaultSecretsUser)
    principalId: stagingSlotPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Outputs for verification
output roleAssignmentsCreated object = {
  production: {
    blob: blobRoleAssignment.id
    queue: queueRoleAssignment.id
    table: tableRoleAssignment.id
    keyVault: keyVaultRoleAssignment.id
  }
  staging: {
    blob: blobRoleAssignmentStaging.id
    queue: queueRoleAssignmentStaging.id
    table: tableRoleAssignmentStaging.id
    keyVault: keyVaultRoleAssignmentStaging.id
  }
}
