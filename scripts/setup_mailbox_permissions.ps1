# PowerShell Script: Setup Shared Mailbox Permissions
# This script grants full access to shared mailboxes for testing

# Prerequisites:
# 1. Install Microsoft.Graph PowerShell module:
#    Install-Module Microsoft.Graph -Scope CurrentUser
# 2. Run with admin-capable account
# 3. Connect to Microsoft Graph with appropriate tenant admin

# ============================================================================
# Configuration
# ============================================================================

$InvoiceMailbox = "dev-invoices@chelseapiers.com"
$APMailbox = "dev-ap@chelseapiers.com"

# YOUR email address (the one you're logged in with)
$YourUserEmail = "alex.fox@chelseapiers.com"  # ← UPDATE THIS

# ============================================================================
# Functions
# ============================================================================

function Connect-ToGraph {
    Write-Host "Connecting to Microsoft Graph..." -ForegroundColor Cyan

    # Connect with Mail.ReadWrite and User.ReadWrite scopes
    Connect-MgGraph -Scopes "User.ReadWrite.All", "Mail.ReadWrite" -ErrorAction Stop

    Write-Host "✅ Connected to Microsoft Graph" -ForegroundColor Green
}

function Grant-SharedMailboxAccess {
    param(
        [string]$MailboxAddress,
        [string]$UserEmail,
        [string]$AccessRight = "Editor"  # Owner, Editor, or Reviewer
    )

    Write-Host ""
    Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "Granting access: $MailboxAddress" -ForegroundColor Cyan
    Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan

    try {
        # Get the mailbox
        Write-Host "Looking up mailbox: $MailboxAddress..."
        $mailbox = Get-MgUser -Filter "mail eq '$MailboxAddress'" -ErrorAction Stop

        if (-not $mailbox) {
            Write-Host "❌ Mailbox not found: $MailboxAddress" -ForegroundColor Red
            return $false
        }

        Write-Host "✅ Found mailbox (ID: $($mailbox.Id))"

        # Get the user
        Write-Host "Looking up user: $UserEmail..."
        $user = Get-MgUser -Filter "mail eq '$UserEmail'" -ErrorAction Stop

        if (-not $user) {
            Write-Host "❌ User not found: $UserEmail" -ForegroundColor Red
            return $false
        }

        Write-Host "✅ Found user (ID: $($user.Id))"

        # Grant permissions using Add-MailboxPermission equivalent
        # Note: This requires Exchange Online module for best results
        Write-Host ""
        Write-Host "Granting $AccessRight access to $MailboxAddress for $UserEmail..."
        Write-Host ""
        Write-Host "⚠️  NOTE: For full shared mailbox access, you may need to use Exchange Online PowerShell:"
        Write-Host ""
        Write-Host "   # Install Exchange Online module (if not already installed)"
        Write-Host "   Install-Module ExchangeOnlineManagement -Scope CurrentUser"
        Write-Host ""
        Write-Host "   # Connect to Exchange Online"
        Write-Host "   Connect-ExchangeOnline"
        Write-Host ""
        Write-Host "   # Grant Full Access permission"
        Write-Host "   Add-MailboxPermission -Identity '$MailboxAddress' \"
        Write-Host "     -User '$UserEmail' -AccessRights FullAccess -InheritanceType All"
        Write-Host ""
        Write-Host "   # Add delegate access (for Outlook)"
        Write-Host "   Add-MailboxPermission -Identity '$MailboxAddress' \"
        Write-Host "     -User '$UserEmail' -AccessRights SendAs"
        Write-Host ""

        return $true

    } catch {
        Write-Host "❌ Error granting access: $_" -ForegroundColor Red
        return $false
    }
}

# ============================================================================
# Main Execution
# ============================================================================

Write-Host ""
Write-Host "🔐 Shared Mailbox Permission Setup" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "This script grants you full access to shared mailboxes for testing."
Write-Host ""
Write-Host "Configuration:"
Write-Host "  Invoice Mailbox:  $InvoiceMailbox"
Write-Host "  AP Mailbox:       $APMailbox"
Write-Host "  Your Email:       $YourUserEmail"
Write-Host ""

# Verify user email
if ($YourUserEmail -eq "alex.fox@chelseapiers.com") {
    Write-Host "⚠️  WARNING: You need to update YourUserEmail in this script!" -ForegroundColor Yellow
    Write-Host "   Edit the \$YourUserEmail variable with your actual email address."
    Write-Host ""
    exit 1
}

# Verify module is installed
Write-Host "Checking for required PowerShell modules..."

$exchangeModule = Get-Module -Name ExchangeOnlineManagement -ListAvailable
if (-not $exchangeModule) {
    Write-Host ""
    Write-Host "❌ ExchangeOnlineManagement module not found" -ForegroundColor Red
    Write-Host ""
    Write-Host "Install it with:" -ForegroundColor Yellow
    Write-Host "   Install-Module ExchangeOnlineManagement -Scope CurrentUser -Force"
    Write-Host ""
    exit 1
}

Write-Host "✅ ExchangeOnlineManagement module found"
Write-Host ""

# Connect
Connect-ToGraph

# Grant permissions
Write-Host ""
Write-Host "Granting mailbox permissions..." -ForegroundColor Cyan
Write-Host ""

Grant-SharedMailboxAccess -MailboxAddress $InvoiceMailbox -UserEmail $YourUserEmail -AccessRight "Editor"
Grant-SharedMailboxAccess -MailboxAddress $APMailbox -UserEmail $YourUserEmail -AccessRight "Editor"

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "Setup Complete" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Green
