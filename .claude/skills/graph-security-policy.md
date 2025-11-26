# Graph API Security Policy Manager Skill

Implements Application Access Policy to restrict Graph API app to specific mailbox(es).

## Purpose
- Restrict app to ONLY access invoice mailbox
- Re-enable mark_as_read() safely
- Follow Microsoft security best practices
- Document policy configuration

## Usage
Invoke when you need to:
- Implement mailbox-level access restrictions
- Configure Application Access Policies
- Test policy effectiveness
- Document security posture improvements

## Prerequisites

### Required PowerShell Module
```powershell
# Install Exchange Online Management module
Install-Module -Name ExchangeOnlineManagement -Force -AllowClobber

# Connect to Exchange Online
Connect-ExchangeOnline -UserPrincipalName admin@example.com
```

### Required Information
- App Registration Client ID (Application ID)
- Mailbox to restrict access to (invoices@example.com)
- Global Admin or Exchange Admin credentials

## Actions

### 1. Create Application Access Policy
```powershell
# Define variables
$AppId = "12345678-1234-1234-1234-123456789012"  # App Registration ID
$PolicyScopeGroupId = "invoices@example.com"     # Mailbox to allow
$AccessRight = "RestrictAccess"
$Description = "Restrict invoice-agent app to only access invoices@example.com mailbox"

# Create policy
New-ApplicationAccessPolicy `
    -AppId $AppId `
    -PolicyScopeGroupId $PolicyScopeGroupId `
    -AccessRight $AccessRight `
    -Description $Description
```

### 2. Verify Policy Creation
```powershell
# List all application access policies
Get-ApplicationAccessPolicy | Format-Table AppId, PolicyScopeGroupId, AccessRight, Description

# Test policy for specific app and mailbox
Test-ApplicationAccessPolicy `
    -Identity "invoices@example.com" `
    -AppId $AppId
```

**Expected Output:**
```
AccessCheckResult : Granted
```

### 3. Test Policy Enforcement (Negative Test)
```powershell
# Test access to different mailbox (should be DENIED)
Test-ApplicationAccessPolicy `
    -Identity "other-mailbox@example.com" `
    -AppId $AppId
```

**Expected Output:**
```
AccessCheckResult : Denied
```

### 4. Update App Permissions (Add Mail.ReadWrite)
After policy is in place, safely add Mail.ReadWrite permission:

```bash
# Via Azure CLI
az ad app permission add \
  --id $APP_ID \
  --api 00000003-0000-0000-c000-000000000000 \
  --api-permissions e2a3a72e-5f79-4c64-b1b1-878b674786c9=Role  # Mail.ReadWrite

# Grant admin consent
az ad app permission admin-consent --id $APP_ID
```

### 5. Update Code to Re-enable mark_as_read()

**MailIngest/__init__.py:**
```python
# Line 51-52: RE-ENABLE (was commented out)
graph.mark_as_read(mailbox, email["id"])

# Line 56-57: RE-ENABLE (was commented out)
graph.mark_as_read(mailbox, email["id"])

# Line 61-62: RE-ENABLE (was commented out)
graph.mark_as_read(mailbox, email["id"])
```

**MailWebhookProcessor/__init__.py:**
```python
# Line 78: RE-ENABLE (was commented out)
graph.mark_as_read(mailbox, message_id)
```

### 6. Update Tests
Re-enable mark_as_read assertions in tests:
- `tests/unit/test_mail_ingest.py` - Uncomment mark_as_read mock assertions
- `tests/unit/test_mail_webhook_processor.py` - Uncomment mark_as_read mock assertions

## Rollback Procedure

If policy causes issues:

```powershell
# Remove application access policy
Remove-ApplicationAccessPolicy -Identity $AppId -Confirm:$false

# Verify removal
Get-ApplicationAccessPolicy | Where-Object {$_.AppId -eq $AppId}
```

## Validation Steps

### 1. Test Graph API Access After Policy
```bash
# Test via Python script
python << 'EOF'
from shared.graph_client import GraphAPIClient
import os

graph = GraphAPIClient()
mailbox = os.getenv("INVOICE_MAILBOX")

# Should succeed (policy allows invoices@example.com)
emails = graph.get_unread_emails(mailbox, max_results=1)
print(f"✅ Access to {mailbox}: SUCCESS")

# Should fail (policy denies other mailboxes)
try:
    other_emails = graph.get_unread_emails("other@example.com", max_results=1)
    print("❌ Policy NOT working - accessed unauthorized mailbox")
except Exception as e:
    print(f"✅ Access to other@example.com: DENIED (expected)")
EOF
```

### 2. Verify mark_as_read() Works
```bash
# Send test email and verify it's marked as read
python scripts/send_test_emails.py

# Check Application Insights for mark_as_read calls
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "
    traces
    | where timestamp > ago(1h)
    | where message contains 'mark_as_read'
    | project timestamp, message, operation_Name
  "
```

## Security Posture Improvements

**Before:**
- ❌ Mail.Read required (access to ALL mailboxes in org)
- ❌ Emails NOT marked as read (duplicate risk)
- ❌ No granular access control

**After:**
- ✅ Mail.ReadWrite restricted to ONE mailbox only
- ✅ Emails marked as read (duplicate prevention)
- ✅ Least-privilege access implemented
- ✅ Compliant with Microsoft best practices

## Documentation Updates

Update these files after policy implementation:
1. `docs/MAIL_PERMISSIONS_GUIDE.md` - Mark as "IMPLEMENTED"
2. `docs/DEPLOYMENT_GUIDE.md` - Add policy setup steps
3. `docs/ARCHITECTURE.md` - Update security section
4. `CLAUDE.md` - Update current state section

## Success Criteria
- ✅ Policy created and verified
- ✅ Access to invoice mailbox: GRANTED
- ✅ Access to other mailboxes: DENIED
- ✅ mark_as_read() re-enabled in code
- ✅ Tests updated and passing
- ✅ Documentation updated

## Reference
- Microsoft Docs: https://learn.microsoft.com/en-us/graph/auth-limit-mailbox-access
- Exchange Online Management: https://learn.microsoft.com/en-us/powershell/exchange/exchange-online-powershell
