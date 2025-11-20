# Graph API Setup for Invoice Agent

## 🚨 Current Status
- ✅ Mailbox configured: `dev-invoices@chelseapiers.com`
- ✅ AP email configured: `ap@chelseapiers.com`
- ❌ Graph API authentication not configured (required for email access)

## 📋 What You Need

To read and send emails, the Invoice Agent needs Microsoft Graph API credentials. You need to create an Azure AD App Registration.

## 🔧 Step-by-Step Setup

### 1. Create App Registration in Azure Portal

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **Azure Active Directory** > **App registrations**
3. Click **New registration**
4. Configure:
   - Name: `Invoice Agent Graph API`
   - Supported account types: `Single tenant`
   - Redirect URI: Leave blank
5. Click **Register**
6. Copy the **Application (client) ID** - you'll need this

### 2. Create Client Secret

1. In your app registration, go to **Certificates & secrets**
2. Click **New client secret**
3. Description: `Invoice Agent Secret`
4. Expires: Choose your preference
5. Click **Add**
6. **COPY THE SECRET VALUE NOW** (it won't be shown again)

### 3. Grant API Permissions

1. Go to **API permissions**
2. Click **Add a permission**
3. Choose **Microsoft Graph**
4. Choose **Application permissions** (not Delegated)
5. Add these permissions:
   - `Mail.Read` - To read emails from the mailbox
   - `Mail.Send` - To send processed invoices to AP
   - `Mail.ReadWrite` - To mark emails as read
6. Click **Add permissions**
7. **IMPORTANT**: Click **Grant admin consent** (requires admin rights)

### 4. Configure the Secrets

Run this command with your values:

```bash
# Set your Azure AD tenant ID (find in Azure AD overview page)
az keyvault secret set \
  --vault-name kv-invoice-agent-prod \
  --name graph-tenant-id \
  --value "YOUR-TENANT-ID"

# Set the Application ID from step 1
az keyvault secret set \
  --vault-name kv-invoice-agent-prod \
  --name graph-client-id \
  --value "YOUR-CLIENT-ID"

# Set the secret from step 2
az keyvault secret set \
  --vault-name kv-invoice-agent-prod \
  --name graph-client-secret \
  --value "YOUR-CLIENT-SECRET"
```

### 5. Grant Mailbox Access

The app needs permission to access the specific mailbox:

```powershell
# In Exchange Online PowerShell
Add-MailboxPermission -Identity "dev-invoices@chelseapiers.com" \
  -User "YOUR-APP-CLIENT-ID" \
  -AccessRights FullAccess
```

Or grant access via Exchange Admin Center.

### 6. Restart Function App

```bash
az functionapp restart \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod
```

## 🧪 Testing

After setup:
1. Wait for the next 5-minute mark
2. Check logs: `./test-live-system.sh`
3. Your test email should be processed

## 🚀 Quick Setup Script

Once you have the credentials, use this script:

```bash
./configure-graph-api.sh
```

This will prompt for your tenant ID, client ID, and secret, then configure everything.

## ⚠️ Common Issues

1. **"Unauthorized" errors**: Admin consent not granted for API permissions
2. **"Mailbox not found"**: App doesn't have access to the specific mailbox
3. **"Invalid client secret"**: Secret expired or copied incorrectly
4. **"Invalid tenant"**: Wrong tenant ID

## 📞 Alternative: Use Delegated Permissions

If you can't get Application permissions, you can use Delegated permissions with a service account:
1. Create a dedicated user account (e.g., invoice-processor@chelseapiers.com)
2. Grant this account access to dev-invoices@chelseapiers.com
3. Use username/password authentication instead

---

**Current Issue**: Your test email from 10:52 PM is waiting to be processed. Once Graph API is configured, it will be picked up at the next 5-minute interval.