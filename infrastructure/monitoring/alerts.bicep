// Alert Rules for Invoice Agent Production Monitoring
targetScope = 'resourceGroup'

@description('Environment name')
param environment string = 'prod'

@description('Project prefix')
param projectPrefix string = 'invoice-agent'

@description('Action Group email addresses')
param alertEmailAddresses array = []

@description('Teams webhook URL for critical alerts')
@secure()
param teamsWebhookUrl string = ''

@description('Enable SMS alerts (optional)')
param enableSmsAlerts bool = false

@description('SMS phone number in E.164 format (+1XXXXXXXXXX)')
param smsPhoneNumber string = ''

// Variables
var namingPrefix = '${projectPrefix}-${environment}'
var functionAppName = 'func-${namingPrefix}'
var storageAccountName = replace('st${projectPrefix}${environment}', '-', '')
var appInsightsName = 'ai-${namingPrefix}'
var actionGroupName = 'ag-${namingPrefix}-ops'

// Get existing resources
resource appInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: appInsightsName
}

resource functionApp 'Microsoft.Web/sites@2023-12-01' existing = {
  name: functionAppName
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

// Action Group for alert notifications
resource actionGroup 'Microsoft.Insights/actionGroups@2023-09-01-preview' = {
  name: actionGroupName
  location: 'global'
  tags: {
    Project: 'InvoiceAgent'
    Environment: environment
  }
  properties: {
    groupShortName: 'InvAgentOps'
    enabled: true
    emailReceivers: [for (email, i) in alertEmailAddresses: {
      name: 'Email-${i}'
      emailAddress: email
      useCommonAlertSchema: true
    }]
    smsReceivers: enableSmsAlerts && !empty(smsPhoneNumber) ? [
      {
        name: 'SMS-Critical'
        countryCode: '1'
        phoneNumber: substring(smsPhoneNumber, 2) // Remove +1 prefix
      }
    ] : []
    webhookReceivers: !empty(teamsWebhookUrl) ? [
      {
        name: 'Teams-Webhook'
        serviceUri: teamsWebhookUrl
        useCommonAlertSchema: true
      }
    ] : []
  }
}

// Alert 1: High Error Rate (>1% over 5 minutes)
resource errorRateAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'alert-${namingPrefix}-high-error-rate'
  location: 'global'
  tags: {
    Project: 'InvoiceAgent'
    Environment: environment
    Severity: 'P1'
  }
  properties: {
    description: 'Triggers when function error rate exceeds 1% over 5 minutes'
    severity: 1 // Warning
    enabled: true
    scopes: [
      appInsights.id
    ]
    evaluationFrequency: 'PT1M' // Check every 1 minute
    windowSize: 'PT5M' // 5 minute window
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'ErrorRateThreshold'
          metricName: 'requests/failed'
          metricNamespace: 'microsoft.insights/components'
          operator: 'GreaterThan'
          threshold: 1
          timeAggregation: 'Average'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroup.id
      }
    ]
  }
}

// Alert 2: Function Execution Failures (>5 failures in 5 minutes)
resource functionFailureAlert 'Microsoft.Insights/scheduledQueryRules@2023-12-01-preview' = {
  name: 'alert-${namingPrefix}-function-failures'
  location: resourceGroup().location
  tags: {
    Project: 'InvoiceAgent'
    Environment: environment
    Severity: 'P1'
  }
  properties: {
    description: 'Triggers when more than 5 function executions fail in 5 minutes'
    severity: 1
    enabled: true
    evaluationFrequency: 'PT5M'
    scopes: [
      appInsights.id
    ]
    windowSize: 'PT5M'
    criteria: {
      allOf: [
        {
          query: '''
            requests
            | where success == false
            | where cloud_RoleName startswith "func-invoice-agent"
            | summarize FailureCount = count() by operation_Name, resultCode
          '''
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 5
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: [
        actionGroup.id
      ]
    }
  }
}

// Alert 3: High Queue Depth (>100 messages for >10 minutes)
resource queueDepthAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'alert-${namingPrefix}-high-queue-depth'
  location: 'global'
  tags: {
    Project: 'InvoiceAgent'
    Environment: environment
    Severity: 'P2'
  }
  properties: {
    description: 'Triggers when any queue has more than 100 messages for over 10 minutes'
    severity: 2 // Warning
    enabled: true
    scopes: [
      storageAccount.id
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT10M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'QueueDepthThreshold'
          metricName: 'QueueMessageCount'
          metricNamespace: 'microsoft.storage/storageaccounts/queueservices'
          operator: 'GreaterThan'
          threshold: 100
          timeAggregation: 'Average'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroup.id
      }
    ]
  }
}

// Alert 4: Processing Latency (>60 seconds end-to-end)
resource processingLatencyAlert 'Microsoft.Insights/scheduledQueryRules@2023-12-01-preview' = {
  name: 'alert-${namingPrefix}-slow-processing'
  location: resourceGroup().location
  tags: {
    Project: 'InvoiceAgent'
    Environment: environment
    Severity: 'P2'
  }
  properties: {
    description: 'Triggers when invoice processing takes longer than 60 seconds end-to-end'
    severity: 2
    enabled: true
    evaluationFrequency: 'PT5M'
    scopes: [
      appInsights.id
    ]
    windowSize: 'PT15M'
    criteria: {
      allOf: [
        {
          query: '''
            requests
            | where cloud_RoleName startswith "func-invoice-agent"
            | where duration > 60000
            | summarize SlowRequests = count(), AvgDuration = avg(duration) by operation_Name
          '''
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 5 // More than 5 slow requests in 15 minutes
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: [
        actionGroup.id
      ]
    }
  }
}

// Alert 5: Dead Letter Queue (Poison Queue) Has Messages
resource deadLetterQueueAlert 'Microsoft.Insights/scheduledQueryRules@2023-12-01-preview' = {
  name: 'alert-${namingPrefix}-poison-queue'
  location: resourceGroup().location
  tags: {
    Project: 'InvoiceAgent'
    Environment: environment
    Severity: 'P0'
  }
  properties: {
    description: 'CRITICAL: Messages in poison queues indicate repeated processing failures'
    severity: 0 // Critical
    enabled: true
    evaluationFrequency: 'PT5M'
    scopes: [
      appInsights.id
    ]
    windowSize: 'PT5M'
    criteria: {
      allOf: [
        {
          query: '''
            traces
            | where message contains "poison" or message contains "dead-letter"
            | summarize PoisonMessages = count()
          '''
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 0
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: [
        actionGroup.id
      ]
    }
  }
}

// Alert 6: High Unknown Vendor Rate (>20% over 1 hour)
resource unknownVendorAlert 'Microsoft.Insights/scheduledQueryRules@2023-12-01-preview' = {
  name: 'alert-${namingPrefix}-high-unknown-vendors'
  location: resourceGroup().location
  tags: {
    Project: 'InvoiceAgent'
    Environment: environment
    Severity: 'P2'
  }
  properties: {
    description: 'Triggers when unknown vendor rate exceeds 20% (indicates VendorMaster may need updates)'
    severity: 2
    enabled: true
    evaluationFrequency: 'PT15M'
    scopes: [
      appInsights.id
    ]
    windowSize: 'PT1H'
    criteria: {
      allOf: [
        {
          query: '''
            traces
            | where message contains "Unknown vendor" or message contains "vendor not found"
            | summarize UnknownCount = count()
            | extend Threshold = 10
            | where UnknownCount > Threshold
          '''
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 0
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: [
        actionGroup.id
      ]
    }
  }
}

// Alert 7: Function App Availability
resource availabilityAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'alert-${namingPrefix}-low-availability'
  location: 'global'
  tags: {
    Project: 'InvoiceAgent'
    Environment: environment
    Severity: 'P0'
  }
  properties: {
    description: 'CRITICAL: Function App availability drops below 95%'
    severity: 0
    enabled: true
    scopes: [
      functionApp.id
    ]
    evaluationFrequency: 'PT1M'
    windowSize: 'PT5M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'AvailabilityThreshold'
          metricName: 'HealthCheckStatus'
          metricNamespace: 'microsoft.web/sites'
          operator: 'LessThan'
          threshold: 95
          timeAggregation: 'Average'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroup.id
      }
    ]
  }
}

// Alert 8: Storage Account Throttling
resource storageThrottlingAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'alert-${namingPrefix}-storage-throttling'
  location: 'global'
  tags: {
    Project: 'InvoiceAgent'
    Environment: environment
    Severity: 'P1'
  }
  properties: {
    description: 'Storage account is being throttled (too many requests)'
    severity: 1
    enabled: true
    scopes: [
      storageAccount.id
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'ThrottlingThreshold'
          metricName: 'SuccessServerLatency'
          metricNamespace: 'microsoft.storage/storageaccounts'
          operator: 'GreaterThan'
          threshold: 1000 // 1 second latency
          timeAggregation: 'Average'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroup.id
      }
    ]
  }
}

// Outputs
output actionGroupId string = actionGroup.id
output actionGroupName string = actionGroup.name
output alertsCreated array = [
  errorRateAlert.name
  functionFailureAlert.name
  queueDepthAlert.name
  processingLatencyAlert.name
  deadLetterQueueAlert.name
  unknownVendorAlert.name
  availabilityAlert.name
  storageThrottlingAlert.name
]
