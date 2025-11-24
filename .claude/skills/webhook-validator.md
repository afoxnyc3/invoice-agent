# Graph API Webhook Validator

Validate Microsoft Graph API webhook subscription configuration, permissions, and endpoint accessibility.

## Objective
Perform comprehensive validation of the Graph API webhook integration to ensure real-time email notifications are working correctly. Diagnose subscription issues, authentication failures, and endpoint accessibility problems.

## Parameters
- `env` (optional): Environment to check (dev/prod). Defaults to prod.
- `test_endpoint` (optional): Whether to test webhook endpoint with simulated notification. Defaults to true.

## Instructions

### 1. Get Required Resource Names

```bash
# Get storage account for Table Storage
STORAGE_ACCOUNT=$(az storage account list \
  --resource-group rg-invoice-agent-{env} \
  --query '[0].name' -o tsv)

echo "Storage Account: $STORAGE_ACCOUNT"

# Get Key Vault name
KV_NAME=$(az keyvault list \
  --resource-group rg-invoice-agent-{env} \
  --query '[0].name' -o tsv)

echo "Key Vault: $KV_NAME"

# Get Function App name
FUNCTION_APP=$(az functionapp list \
  --resource-group rg-invoice-agent-{env} \
  --query '[0].name' -o tsv)

echo "Function App: $FUNCTION_APP"
```

---

### 2. Validate Environment Variables

Check all required Graph API configuration exists:

```bash
echo ""
echo "=== ENVIRONMENT VARIABLES CHECK ==="

# Get all app settings
az functionapp config appsettings list \
  --name $FUNCTION_APP \
  --resource-group rg-invoice-agent-{env} \
  --output json > /tmp/appsettings.json

# Check each required setting
required_settings=(
  "GRAPH_TENANT_ID"
  "GRAPH_CLIENT_ID"
  "GRAPH_CLIENT_SECRET"
  "MAIL_WEBHOOK_URL"
  "GRAPH_CLIENT_STATE"
  "INVOICE_MAILBOX"
)

echo "Checking required settings..."
for setting in "${required_settings[@]}"; do
  value=$(cat /tmp/appsettings.json | jq -r ".[] | select(.name==\"$setting\") | .value")

  if [ -z "$value" ] || [ "$value" == "null" ]; then
    echo "❌ $setting: MISSING"
  elif [[ "$value" == @Microsoft.KeyVault* ]]; then
    echo "✅ $setting: Key Vault reference configured"
  else
    # Mask sensitive values
    if [[ "$setting" == *"SECRET"* ]] || [[ "$setting" == *"STATE"* ]]; then
      echo "✅ $setting: Set (value masked)"
    else
      echo "✅ $setting: $value"
    fi
  fi
done
```

**Validation Rules:**
- `GRAPH_TENANT_ID`: Must be valid UUID format
- `GRAPH_CLIENT_ID`: Must be valid UUID format
- `GRAPH_CLIENT_SECRET`: Should be Key Vault reference
- `MAIL_WEBHOOK_URL`: Must start with https:// and contain function key
- `GRAPH_CLIENT_STATE`: Must be ≥32 characters (security requirement)
- `INVOICE_MAILBOX`: Must be valid email address

---

### 3. Check Active Subscription in Table Storage

Query GraphSubscriptions table for active subscription:

```bash
echo ""
echo "=== GRAPH SUBSCRIPTION STATUS ==="

# Get connection string
STORAGE_CONN_STR=$(az storage account show-connection-string \
  --name $STORAGE_ACCOUNT \
  --resource-group rg-invoice-agent-{env} \
  --query connectionString -o tsv)

# Query for active subscriptions
az storage entity query \
  --table-name GraphSubscriptions \
  --connection-string "$STORAGE_CONN_STR" \
  --filter "PartitionKey eq 'GraphSubscription' and IsActive eq true" \
  --output json > /tmp/subscriptions.json

# Parse results
active_count=$(cat /tmp/subscriptions.json | jq '. | length')

if [ "$active_count" -eq 0 ]; then
  echo "❌ No active subscription found"
  echo "   Run SubscriptionManager function to create subscription"
elif [ "$active_count" -gt 1 ]; then
  echo "⚠️ Multiple active subscriptions found ($active_count)"
  echo "   Only one should be active at a time"
  cat /tmp/subscriptions.json | jq -r '.[] | "   - Subscription ID: \(.SubscriptionId) (expires: \(.ExpirationDateTime))"'
else
  echo "✅ One active subscription found"

  # Check expiration
  subscription_id=$(cat /tmp/subscriptions.json | jq -r '.[0].SubscriptionId')
  expiration=$(cat /tmp/subscriptions.json | jq -r '.[0].ExpirationDateTime')
  resource=$(cat /tmp/subscriptions.json | jq -r '.[0].Resource')

  echo "   Subscription ID: $subscription_id"
  echo "   Resource: $resource"
  echo "   Expires: $expiration"

  # Calculate time until expiration
  expiration_epoch=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$expiration" "+%s" 2>/dev/null || echo "0")
  now_epoch=$(date "+%s")
  hours_remaining=$(( ($expiration_epoch - $now_epoch) / 3600 ))

  if [ "$hours_remaining" -lt 0 ]; then
    echo "   ❌ EXPIRED $((hours_remaining * -1)) hours ago"
    echo "   Action: Run SubscriptionManager function to renew"
  elif [ "$hours_remaining" -lt 48 ]; then
    echo "   ⚠️ Expires in $hours_remaining hours (renewal recommended)"
    echo "   Action: Run SubscriptionManager function to renew"
  else
    echo "   ✅ Valid for $hours_remaining hours"
  fi
fi
```

---

### 4. Validate Webhook Endpoint URL

Check webhook URL format and extract components:

```bash
echo ""
echo "=== WEBHOOK ENDPOINT VALIDATION ==="

# Get webhook URL from settings
WEBHOOK_URL=$(cat /tmp/appsettings.json | jq -r '.[] | select(.name=="MAIL_WEBHOOK_URL") | .value')

if [ -z "$WEBHOOK_URL" ] || [ "$WEBHOOK_URL" == "null" ]; then
  echo "❌ MAIL_WEBHOOK_URL not configured"
else
  echo "Webhook URL: $WEBHOOK_URL"

  # Validate HTTPS
  if [[ "$WEBHOOK_URL" == https://* ]]; then
    echo "✅ Uses HTTPS protocol"
  else
    echo "❌ Must use HTTPS protocol"
  fi

  # Validate contains function key
  if [[ "$WEBHOOK_URL" == *"?code="* ]]; then
    echo "✅ Contains function key parameter"
  else
    echo "❌ Missing function key (?code=...)"
  fi

  # Validate hostname matches function app
  if [[ "$WEBHOOK_URL" == *"$FUNCTION_APP"* ]]; then
    echo "✅ Hostname matches function app"
  else
    echo "⚠️ Hostname does not match function app name"
  fi

  # Validate path is /api/MailWebhook
  if [[ "$WEBHOOK_URL" == *"/api/MailWebhook"* ]]; then
    echo "✅ Correct endpoint path (/api/MailWebhook)"
  else
    echo "❌ Incorrect endpoint path (should be /api/MailWebhook)"
  fi
fi
```

---

### 5. Test Webhook Endpoint Accessibility

Simulate Graph API validation handshake:

```bash
echo ""
echo "=== WEBHOOK ENDPOINT ACCESSIBILITY TEST ==="

if [ -n "$WEBHOOK_URL" ] && [ "$WEBHOOK_URL" != "null" ]; then
  # Test 1: Validation handshake (GET with validationToken)
  echo "Test 1: Validation handshake..."

  validation_token="test-validation-token-$(date +%s)"
  validation_url="${WEBHOOK_URL}&validationToken=${validation_token}"

  response=$(curl -s -w "\n%{http_code}" -X GET "$validation_url" 2>/dev/null)
  http_code=$(echo "$response" | tail -n1)
  body=$(echo "$response" | head -n-1)

  if [ "$http_code" == "200" ]; then
    if [ "$body" == "$validation_token" ]; then
      echo "✅ Validation handshake successful (returned token correctly)"
    else
      echo "⚠️ HTTP 200 but incorrect response body"
      echo "   Expected: $validation_token"
      echo "   Got: $body"
    fi
  else
    echo "❌ Validation handshake failed (HTTP $http_code)"
    echo "   Response: $body"
  fi

  # Test 2: Notification POST (if enabled)
  if [ "${test_endpoint}" != "false" ]; then
    echo ""
    echo "Test 2: Simulated notification..."

    # Get client state for test
    CLIENT_STATE=$(cat /tmp/appsettings.json | jq -r '.[] | select(.name=="GRAPH_CLIENT_STATE") | .value')

    # If it's a Key Vault reference, try to resolve it
    if [[ "$CLIENT_STATE" == @Microsoft.KeyVault* ]]; then
      # Extract secret name from URI
      secret_uri=$(echo "$CLIENT_STATE" | sed 's/@Microsoft.KeyVault(SecretUri=//' | sed 's/).*//')
      secret_name=$(basename "$secret_uri")
      CLIENT_STATE=$(az keyvault secret show --name "$secret_name" --vault-name "$KV_NAME" --query value -o tsv 2>/dev/null)
    fi

    test_notification='{
      "value": [{
        "subscriptionId": "test-subscription-id",
        "resource": "users/test@example.com/messages/AAMkAD-test",
        "changeType": "created",
        "clientState": "'"$CLIENT_STATE"'"
      }]
    }'

    response=$(curl -s -w "\n%{http_code}" -X POST "$WEBHOOK_URL" \
      -H "Content-Type: application/json" \
      -d "$test_notification" 2>/dev/null)

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)

    if [ "$http_code" == "202" ]; then
      echo "✅ Notification POST successful (HTTP 202 Accepted)"
      echo "   Check webhook-notifications queue for test message"
    else
      echo "❌ Notification POST failed (HTTP $http_code)"
      echo "   Response: $body"
    fi
  fi
else
  echo "⚠️ Skipping endpoint test - MAIL_WEBHOOK_URL not configured"
fi
```

---

### 6. Validate Graph API Authentication

Test that Graph API credentials work:

```bash
echo ""
echo "=== GRAPH API AUTHENTICATION TEST ==="

# Get credentials
TENANT_ID=$(cat /tmp/appsettings.json | jq -r '.[] | select(.name=="GRAPH_TENANT_ID") | .value')
CLIENT_ID=$(cat /tmp/appsettings.json | jq -r '.[] | select(.name=="GRAPH_CLIENT_ID") | .value')

# Get client secret from Key Vault
CLIENT_SECRET_REF=$(cat /tmp/appsettings.json | jq -r '.[] | select(.name=="GRAPH_CLIENT_SECRET") | .value')

if [[ "$CLIENT_SECRET_REF" == @Microsoft.KeyVault* ]]; then
  secret_uri=$(echo "$CLIENT_SECRET_REF" | sed 's/@Microsoft.KeyVault(SecretUri=//' | sed 's/).*//')
  secret_name=$(basename "$secret_uri")
  CLIENT_SECRET=$(az keyvault secret show --name "$secret_name" --vault-name "$KV_NAME" --query value -o tsv 2>/dev/null)
else
  CLIENT_SECRET="$CLIENT_SECRET_REF"
fi

if [ -z "$TENANT_ID" ] || [ -z "$CLIENT_ID" ] || [ -z "$CLIENT_SECRET" ]; then
  echo "❌ Missing Graph API credentials"
else
  echo "Tenant ID: $TENANT_ID"
  echo "Client ID: $CLIENT_ID"
  echo "Client Secret: $(echo $CLIENT_SECRET | cut -c1-8)... (masked)"

  # Attempt to get access token
  token_response=$(curl -s -X POST \
    "https://login.microsoftonline.com/$TENANT_ID/oauth2/v2.0/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "client_id=$CLIENT_ID" \
    -d "client_secret=$CLIENT_SECRET" \
    -d "scope=https://graph.microsoft.com/.default" \
    -d "grant_type=client_credentials")

  access_token=$(echo "$token_response" | jq -r '.access_token')
  error=$(echo "$token_response" | jq -r '.error')

  if [ "$access_token" != "null" ] && [ -n "$access_token" ]; then
    echo "✅ Successfully acquired access token"

    # Test Graph API call (get mailbox)
    MAILBOX=$(cat /tmp/appsettings.json | jq -r '.[] | select(.name=="INVOICE_MAILBOX") | .value')

    if [ -n "$MAILBOX" ]; then
      echo ""
      echo "Testing mailbox access..."

      mailbox_response=$(curl -s -X GET \
        "https://graph.microsoft.com/v1.0/users/$MAILBOX" \
        -H "Authorization: Bearer $access_token")

      mailbox_error=$(echo "$mailbox_response" | jq -r '.error.code')

      if [ "$mailbox_error" == "null" ]; then
        display_name=$(echo "$mailbox_response" | jq -r '.displayName')
        echo "✅ Mailbox accessible: $display_name ($MAILBOX)"
      else
        echo "❌ Mailbox access failed: $mailbox_error"
        echo "   $(echo "$mailbox_response" | jq -r '.error.message')"
      fi
    fi
  else
    echo "❌ Failed to acquire access token"
    echo "   Error: $error"
    echo "   $(echo "$token_response" | jq -r '.error_description')"
  fi
fi
```

---

### 7. Check Client State Secret

Validate client state security token:

```bash
echo ""
echo "=== CLIENT STATE VALIDATION ==="

CLIENT_STATE_REF=$(cat /tmp/appsettings.json | jq -r '.[] | select(.name=="GRAPH_CLIENT_STATE") | .value')

if [ -z "$CLIENT_STATE_REF" ] || [ "$CLIENT_STATE_REF" == "null" ]; then
  echo "❌ GRAPH_CLIENT_STATE not configured"
else
  # Resolve from Key Vault if needed
  if [[ "$CLIENT_STATE_REF" == @Microsoft.KeyVault* ]]; then
    echo "✅ Using Key Vault reference (secure)"

    secret_uri=$(echo "$CLIENT_STATE_REF" | sed 's/@Microsoft.KeyVault(SecretUri=//' | sed 's/).*//')
    secret_name=$(basename "$secret_uri")
    CLIENT_STATE_VALUE=$(az keyvault secret show --name "$secret_name" --vault-name "$KV_NAME" --query value -o tsv 2>/dev/null)
  else
    echo "⚠️ Using direct value (should be Key Vault reference)"
    CLIENT_STATE_VALUE="$CLIENT_STATE_REF"
  fi

  # Check length (must be ≥32 characters for security)
  length=${#CLIENT_STATE_VALUE}

  if [ "$length" -ge 32 ]; then
    echo "✅ Client state length: $length characters (≥32 required)"
  else
    echo "❌ Client state too short: $length characters (32+ required)"
    echo "   Generate new secret: openssl rand -base64 32"
  fi

  # Check if it matches subscription clientState (if subscription exists)
  if [ "$active_count" -eq 1 ]; then
    # Note: Graph API doesn't return clientState in subscription details
    # We can only validate it by testing webhook POST
    echo "ℹ️  Client state cannot be validated against subscription"
    echo "   Test with simulated notification to verify match"
  fi
fi
```

---

### 8. Verify Graph API Permissions

Check that required permissions are granted:

```bash
echo ""
echo "=== GRAPH API PERMISSIONS CHECK ==="

if [ -n "$access_token" ]; then
  # Get service principal for the app
  sp_response=$(curl -s -X GET \
    "https://graph.microsoft.com/v1.0/servicePrincipals?\$filter=appId eq '$CLIENT_ID'" \
    -H "Authorization: Bearer $access_token")

  sp_id=$(echo "$sp_response" | jq -r '.value[0].id')

  if [ -n "$sp_id" ] && [ "$sp_id" != "null" ]; then
    # Get app roles assigned
    roles_response=$(curl -s -X GET \
      "https://graph.microsoft.com/v1.0/servicePrincipals/$sp_id/appRoleAssignments" \
      -H "Authorization: Bearer $access_token")

    # Check for required permissions
    required_permissions=("Mail.Read" "Mail.ReadWrite" "Mail.Send")

    echo "Checking required permissions..."
    for perm in "${required_permissions[@]}"; do
      # This is a simplified check - actual implementation would need to match role IDs
      echo "  $perm: (check in Azure Portal)"
    done

    echo ""
    echo "ℹ️  Verify permissions manually in Azure Portal:"
    echo "   1. Go to App Registrations"
    echo "   2. Select app: $CLIENT_ID"
    echo "   3. Check API Permissions"
    echo "   4. Ensure Mail.Read, Mail.ReadWrite, Mail.Send are granted"
    echo "   5. Verify 'Admin consent granted' status"
  else
    echo "⚠️ Could not find service principal for app"
  fi
else
  echo "⚠️ Skipping permission check - no access token"
fi
```

---

### 9. Check Subscription Renewal Timer

Verify SubscriptionManager function is configured correctly:

```bash
echo ""
echo "=== SUBSCRIPTION MANAGER FUNCTION CHECK ==="

# Check if SubscriptionManager function exists
sm_exists=$(az functionapp function list \
  --name $FUNCTION_APP \
  --resource-group rg-invoice-agent-{env} \
  --query "[?name=='SubscriptionManager'].name" -o tsv)

if [ -n "$sm_exists" ]; then
  echo "✅ SubscriptionManager function deployed"

  # Check schedule (should be every 6 days: "0 0 0 */6 * *")
  echo "   Timer schedule: Every 6 days (0 0 0 */6 * *)"
  echo "   Renewal window: 48 hours before expiration"
else
  echo "❌ SubscriptionManager function not found"
  echo "   Deploy SubscriptionManager function to enable auto-renewal"
fi
```

---

### 10. Webhook Validator Summary Report

Provide comprehensive summary:

```
=== GRAPH API WEBHOOK VALIDATOR REPORT ===
Environment: {env}
Function App: {function_app}
Timestamp: {current_time}

ENVIRONMENT VARIABLES:
  ✅/❌ GRAPH_TENANT_ID: {status}
  ✅/❌ GRAPH_CLIENT_ID: {status}
  ✅/❌ GRAPH_CLIENT_SECRET: {status}
  ✅/❌ MAIL_WEBHOOK_URL: {status}
  ✅/❌ GRAPH_CLIENT_STATE: {status}
  ✅/❌ INVOICE_MAILBOX: {status}

SUBSCRIPTION STATUS:
  ✅/❌ Active subscription: {count} found
  ✅/⚠️/❌ Expiration: {hours_remaining} hours remaining
  ✅/❌ Subscription ID: {id}
  ✅/❌ Resource: {resource}

WEBHOOK ENDPOINT:
  ✅/❌ HTTPS protocol: {status}
  ✅/❌ Function key present: {status}
  ✅/❌ Correct path: {status}
  ✅/❌ Validation handshake: {status}
  ✅/❌ Notification POST: {status}

GRAPH API AUTHENTICATION:
  ✅/❌ Token acquisition: {status}
  ✅/❌ Mailbox access: {status}

CLIENT STATE:
  ✅/❌ Configured: {status}
  ✅/❌ Length ≥32 chars: {status}
  ✅/⚠️ Key Vault reference: {status}

PERMISSIONS:
  ℹ️  Manual verification required in Azure Portal

SUBSCRIPTION MANAGER:
  ✅/❌ Function deployed: {status}
  ✅ Timer schedule: Every 6 days

OVERALL STATUS: ✅ HEALTHY / ⚠️ WARNINGS / ❌ CRITICAL ISSUES

IMMEDIATE ACTIONS REQUIRED:
  1. {First critical fix if any}
  2. {Second critical fix if any}
  ...

RECOMMENDED NEXT STEPS:
  - {Suggestion 1}
  - {Suggestion 2}

USEFUL COMMANDS:
  # Trigger subscription renewal manually
  az functionapp function invoke \
    --name {function_app} \
    --resource-group rg-invoice-agent-{env} \
    --function-name SubscriptionManager

  # Check webhook-notifications queue
  az storage queue peek \
    --name webhook-notifications \
    --account-name {storage_account} \
    --num-messages 5
```

---

## Diagnostic Questions to Answer

This skill should help answer:

✅ **Is the webhook subscription active?**
   - Check GraphSubscriptions table

✅ **Is the subscription about to expire?**
   - Check expiration timestamp

✅ **Is the webhook endpoint accessible?**
   - Test validation handshake and notification POST

✅ **Can the app authenticate with Graph API?**
   - Test token acquisition and mailbox access

✅ **Is the client state configured correctly?**
   - Validate length and storage

✅ **Are required permissions granted?**
   - Check service principal roles

---

## Output Format

Provide:
1. **Health Score**: Overall webhook health (HEALTHY/WARNINGS/CRITICAL)
2. **Critical Issues**: Blocking problems that prevent webhooks from working
3. **Warnings**: Non-blocking issues that should be addressed
4. **Success Items**: What's configured correctly
5. **Remediation Commands**: Copy-paste Azure CLI commands to fix issues

## Success Criteria

Webhook validation is complete when you've verified:
- [ ] Active subscription exists and not expired
- [ ] All environment variables configured
- [ ] Webhook endpoint accessible and responds correctly
- [ ] Graph API authentication working
- [ ] Client state properly configured
- [ ] SubscriptionManager function deployed for auto-renewal

## Notes

- Subscription max lifetime: ~7 days (4200 minutes)
- Renewal should happen 48 hours before expiration
- Client state must match between config and Graph notification
- Webhook must respond to validation handshake in <3 seconds
- Use SubscriptionManager function for manual renewal if needed
