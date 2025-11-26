<#
.SYNOPSIS
    Sets up Application Access Policy to restrict Graph API app to invoice mailbox only.

.DESCRIPTION
    This script creates an Exchange Online Application Access Policy that restricts
    the Invoice Agent app to ONLY access the invoice processing mailbox. This enables
    safe use of Mail.ReadWrite permission with least-privilege access.

    After running this script:
    - App can read/write emails ONLY in the invoice mailbox
    - App CANNOT access any other mailboxes in the tenant
    - mark_as_read() can be safely re-enabled

.PARAMETER AppId
    The Application (client) ID of the Invoice Agent app registration in Azure AD.

.PARAMETER InvoiceMailbox
    The email address of the invoice processing mailbox (e.g., invoices@example.com).

.PARAMETER PolicyName
    Optional. Name for the Application Access Policy. Defaults to "Invoice Agent Mailbox Restriction".

.EXAMPLE
    .\setup_application_access_policy.ps1 -AppId "12345678-1234-1234-1234-123456789012" -InvoiceMailbox "invoices@chelseapiers.com"

.NOTES
    Prerequisites:
    - Exchange Online Management module: Install-Module ExchangeOnlineManagement
    - Global Admin or Exchange Administrator role
    - Azure AD app registration with Mail.ReadWrite permission

    Reference: https://learn.microsoft.com/en-us/graph/auth-limit-mailbox-access
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$AppId,

    [Parameter(Mandatory=$true)]
    [string]$InvoiceMailbox,

    [Parameter(Mandatory=$false)]
    [string]$PolicyName = "Invoice Agent Mailbox Restriction"
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Application Access Policy Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check for Exchange Online Management module
Write-Host "[1/6] Checking for Exchange Online Management module..." -ForegroundColor Yellow
$module = Get-Module -ListAvailable -Name ExchangeOnlineManagement
if (-not $module) {
    Write-Host "Installing Exchange Online Management module..." -ForegroundColor Yellow
    Install-Module ExchangeOnlineManagement -Force -Scope CurrentUser
}
Import-Module ExchangeOnlineManagement
Write-Host "Module loaded successfully" -ForegroundColor Green

# Step 2: Connect to Exchange Online
Write-Host ""
Write-Host "[2/6] Connecting to Exchange Online..." -ForegroundColor Yellow
Write-Host "You will be prompted to sign in with your admin credentials." -ForegroundColor Gray
Connect-ExchangeOnline -ShowBanner:$false
Write-Host "Connected to Exchange Online" -ForegroundColor Green

# Step 3: Create mail-enabled security group for the mailbox
Write-Host ""
Write-Host "[3/6] Creating mail-enabled security group for policy scope..." -ForegroundColor Yellow

$groupName = "Invoice Agent Restricted Mailboxes"
$existingGroup = Get-DistributionGroup -Identity $groupName -ErrorAction SilentlyContinue

if ($existingGroup) {
    Write-Host "Group '$groupName' already exists" -ForegroundColor Gray
} else {
    New-DistributionGroup -Name $groupName -Type Security -Notes "Mailboxes accessible by Invoice Agent app"
    Write-Host "Created security group: $groupName" -ForegroundColor Green
}

# Step 4: Add invoice mailbox to the security group
Write-Host ""
Write-Host "[4/6] Adding invoice mailbox to security group..." -ForegroundColor Yellow

try {
    Add-DistributionGroupMember -Identity $groupName -Member $InvoiceMailbox -ErrorAction Stop
    Write-Host "Added $InvoiceMailbox to group" -ForegroundColor Green
} catch {
    if ($_.Exception.Message -like "*already a member*") {
        Write-Host "$InvoiceMailbox is already a member of the group" -ForegroundColor Gray
    } else {
        throw
    }
}

# Step 5: Create Application Access Policy
Write-Host ""
Write-Host "[5/6] Creating Application Access Policy..." -ForegroundColor Yellow

$existingPolicy = Get-ApplicationAccessPolicy -Identity $PolicyName -ErrorAction SilentlyContinue

if ($existingPolicy) {
    Write-Host "Policy '$PolicyName' already exists - removing and recreating..." -ForegroundColor Yellow
    Remove-ApplicationAccessPolicy -Identity $PolicyName -Confirm:$false
}

New-ApplicationAccessPolicy `
    -AppId $AppId `
    -PolicyScopeGroupId $groupName `
    -AccessRight RestrictAccess `
    -Description "Restricts Invoice Agent app to invoice mailbox only"

Write-Host "Application Access Policy created successfully" -ForegroundColor Green

# Step 6: Verify the policy
Write-Host ""
Write-Host "[6/6] Verifying policy configuration..." -ForegroundColor Yellow
Write-Host ""

# Test access to invoice mailbox (should be GRANTED)
Write-Host "Testing access to $InvoiceMailbox..." -ForegroundColor Gray
$testInvoice = Test-ApplicationAccessPolicy -Identity $InvoiceMailbox -AppId $AppId
if ($testInvoice.AccessCheckResult -eq "Granted") {
    Write-Host "Access to ${InvoiceMailbox}: GRANTED" -ForegroundColor Green
} else {
    Write-Host "Access to ${InvoiceMailbox}: $($testInvoice.AccessCheckResult)" -ForegroundColor Red
    Write-Host "WARNING: Policy may not be configured correctly!" -ForegroundColor Red
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Wait 30-60 minutes for policy to propagate" -ForegroundColor White
Write-Host "2. Add Mail.ReadWrite permission to app registration in Azure Portal" -ForegroundColor White
Write-Host "3. Grant admin consent for the new permission" -ForegroundColor White
Write-Host "4. Test with a non-invoice mailbox to verify access is DENIED" -ForegroundColor White
Write-Host "5. Deploy updated code with mark_as_read() enabled" -ForegroundColor White
Write-Host ""
Write-Host "To test access to other mailboxes:" -ForegroundColor Gray
Write-Host "  Test-ApplicationAccessPolicy -Identity other@example.com -AppId $AppId" -ForegroundColor Gray
Write-Host ""

# Disconnect
Disconnect-ExchangeOnline -Confirm:$false
Write-Host "Disconnected from Exchange Online" -ForegroundColor Gray
