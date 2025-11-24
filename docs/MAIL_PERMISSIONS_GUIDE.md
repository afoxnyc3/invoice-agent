# Mail Permissions Security Guide

## Current State (Temporary)

The application currently uses `Mail.Read` permission only, which allows reading emails but not marking them as read. This is a temporary security improvement over granting `Mail.ReadWrite` for all mailboxes.

**Trade-off:** Emails remain unread after processing, potentially causing duplicate processing if the system restarts.

## Production Solution: Application Access Policies

For production, implement Exchange Online Application Access Policies to grant granular permissions to specific mailboxes only.

### Why This Approach?

- **Principle of Least Privilege**: Only access mailboxes that need processing
- **Security Compliance**: Meets SOC2 and other compliance requirements
- **Audit Trail**: Clear visibility of which mailboxes the app can access
- **No Code Changes**: Works with existing Mail.ReadWrite permission

### Implementation Steps

#### 1. Prerequisites

- Exchange Online PowerShell module installed
- Exchange Administrator or Global Administrator role
- Application already registered in Azure AD

#### 2. Create Mail-Enabled Security Group

```powershell
# Connect to Exchange Online
Connect-ExchangeOnline

# Create security group for invoice processing mailboxes
New-DistributionGroup -Name "InvoiceProcessingMailboxes" `
  -Type "Security" `
  -PrimarySmtpAddress "invoice-processing-group@chelseapiers.com"

# Add specific mailboxes to the group
Add-DistributionGroupMember -Identity "InvoiceProcessingMailboxes" `
  -Member "invoices@chelseapiers.com"

Add-DistributionGroupMember -Identity "InvoiceProcessingMailboxes" `
  -Member "dev-invoices@chelseapiers.com"
```

#### 3. Create Application Access Policy

```powershell
# Grant the Azure AD app access ONLY to mailboxes in the security group
New-ApplicationAccessPolicy -AppId "YOUR_CLIENT_ID" `
  -PolicyScopeGroupId "invoice-processing-group@chelseapiers.com" `
  -AccessRight "RestrictAccess" `
  -Description "Invoice Agent - Access to invoice processing mailboxes only"

# Verify the policy was created
Get-ApplicationAccessPolicy | Where-Object {$_.AppId -eq "YOUR_CLIENT_ID"}
```

#### 4. Test Access Restrictions

```powershell
# Test that the app can access allowed mailbox
Test-ApplicationAccessPolicy -Identity "invoices@chelseapiers.com" `
  -AppId "YOUR_CLIENT_ID"
# Expected: AccessGranted

# Test that the app CANNOT access other mailboxes
Test-ApplicationAccessPolicy -Identity "ceo@chelseapiers.com" `
  -AppId "YOUR_CLIENT_ID"
# Expected: AccessDenied
```

#### 5. Re-enable mark_as_read in Code

Once the Application Access Policy is in place:

1. Uncomment the `mark_as_read()` calls in:
   - `src/MailIngest/__init__.py`
   - `src/MailWebhookProcessor/__init__.py`

2. Grant `Mail.ReadWrite` permission in Azure AD (now safe with policy)

3. Deploy the updated code

### Security Benefits

| Approach | Risk Level | Mailbox Access |
|----------|------------|---------------|
| Mail.ReadWrite (No Policy) | HIGH | All mailboxes in organization |
| Mail.Read Only (Current) | LOW | Read-only to one mailbox, can't mark as read |
| Mail.ReadWrite + Policy | LOW | Full access to specified mailboxes only |

### Monitoring and Compliance

#### Audit Policy Usage

```powershell
# View all application access policies
Get-ApplicationAccessPolicy

# Check specific app's access
Get-ApplicationAccessPolicy | Where-Object {$_.AppId -eq "YOUR_CLIENT_ID"}
```

#### Update Policy

```powershell
# Add new mailbox to allowed list
Add-DistributionGroupMember -Identity "InvoiceProcessingMailboxes" `
  -Member "new-invoice-mailbox@chelseapiers.com"

# Remove mailbox from allowed list
Remove-DistributionGroupMember -Identity "InvoiceProcessingMailboxes" `
  -Member "old-mailbox@chelseapiers.com"
```

#### Remove Policy (if needed)

```powershell
Remove-ApplicationAccessPolicy -Identity "POLICY_GUID"
```

## Alternative: Shared Mailbox Delegation

If Application Access Policies aren't available in your Exchange Online plan:

1. Convert invoice mailbox to a shared mailbox
2. Use delegated permissions with specific user consent
3. Grant `Mail.ReadWrite.Shared` scope (less broad than `Mail.ReadWrite`)

## Security Checklist

- [ ] Never grant Mail.ReadWrite without Application Access Policy
- [ ] Document all mailboxes with app access
- [ ] Regular audit of access policies (quarterly)
- [ ] Remove access when mailboxes are decommissioned
- [ ] Monitor Graph API audit logs for unusual access patterns
- [ ] Use separate app registrations for dev/staging/production

## Rollback Procedure

If issues occur after implementing Application Access Policy:

1. Keep Mail.Read permission as fallback
2. Comment out mark_as_read() calls (current state)
3. Deploy without marking emails as read
4. Investigate and fix policy issues
5. Re-enable when resolved

## References

- [Microsoft Docs: Limiting application permissions to specific mailboxes](https://docs.microsoft.com/en-us/graph/auth-limit-mailbox-access)
- [Exchange Online PowerShell Documentation](https://docs.microsoft.com/en-us/powershell/exchange/exchange-online-powershell)
- [Security Best Practices for Microsoft Graph](https://docs.microsoft.com/en-us/graph/security-best-practices)

---

**Last Updated:** 2024-11-23
**Security Review:** Required before production deployment
**Contact:** Engineering Team