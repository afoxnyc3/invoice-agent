# Grant Full Access to shared mailbox

$MailboxEmail = "dev-ap@chelseapiers.com"
$UserEmail = "afox@chelseapiers.com"

Write-Host "🔐 Granting Mailbox Access" -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
Write-Host "Mailbox: $MailboxEmail"
Write-Host "User:    $UserEmail"
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
Write-Host ""

# Step 1: Check if module is installed
Write-Host "📌 Checking for ExchangeOnlineManagement module..."
$module = Get-Module -Name ExchangeOnlineManagement -ListAvailable

if ($module) {
    Write-Host "✅ Module found (version $($module.Version))"
} else {
    Write-Host "⚠️  Module not found. Installing..."
    try {
        Install-Module -Name ExchangeOnlineManagement -Scope CurrentUser -Force -AllowClobber
        Write-Host "✅ Module installed"
    } catch {
        Write-Host "❌ Error installing module: $_" -ForegroundColor Red
        Write-Host ""
        Write-Host "Try running PowerShell as Administrator and running:"
        Write-Host "   Install-Module ExchangeOnlineManagement -Scope CurrentUser -Force"
        exit 1
    }
}

# Step 2: Import the module
Write-Host ""
Write-Host "📌 Importing ExchangeOnlineManagement..."
try {
    Import-Module ExchangeOnlineManagement -ErrorAction Stop
    Write-Host "✅ Module imported"
} catch {
    Write-Host "❌ Error importing module: $_" -ForegroundColor Red
    exit 1
}

# Step 3: Connect to Exchange Online
Write-Host ""
Write-Host "📌 Connecting to Exchange Online..."
Write-Host "   (You'll be prompted to sign in with your Azure account)"
Write-Host ""
try {
    Connect-ExchangeOnline -ErrorAction Stop
    Write-Host "✅ Connected to Exchange Online"
} catch {
    Write-Host "❌ Error connecting to Exchange Online: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Make sure:"
    Write-Host "  1. You have Office 365 admin credentials"
    Write-Host "  2. You have permission to manage mailbox permissions"
    exit 1
}

# Step 4: Grant FullAccess permission
Write-Host ""
Write-Host "📌 Granting FullAccess permission..."
try {
    Add-MailboxPermission -Identity $MailboxEmail `
        -User $UserEmail `
        -AccessRights FullAccess `
        -InheritanceType All `
        -Confirm:$false `
        -ErrorAction Stop

    Write-Host "✅ FullAccess permission granted"
} catch {
    Write-Host "❌ Error granting FullAccess: $_" -ForegroundColor Red
    exit 1
}

# Step 5: Grant SendAs permission (optional but useful)
Write-Host ""
Write-Host "📌 Granting SendAs permission..."
try {
    Add-MailboxPermission -Identity $MailboxEmail `
        -User $UserEmail `
        -AccessRights SendAs `
        -Confirm:$false `
        -ErrorAction Stop

    Write-Host "✅ SendAs permission granted"
} catch {
    Write-Host "⚠️  SendAs already granted or error: $_"
}

# Step 6: Verify permissions
Write-Host ""
Write-Host "📌 Verifying permissions..."
try {
    $perms = Get-MailboxPermission -Identity $MailboxEmail | Where-Object { $_.User -eq $UserEmail }

    if ($perms) {
        Write-Host "✅ Permissions verified:"
        Write-Host ""
        $perms | ForEach-Object {
            Write-Host "   Identity: $($_.Identity)"
            Write-Host "   User: $($_.User)"
            Write-Host "   AccessRights: $($_.AccessRights -join ', ')"
        }
    } else {
        Write-Host "⚠️  Permissions not yet visible (may take 30-60 seconds to sync)"
    }
} catch {
    Write-Host "⚠️  Could not verify: $_"
}

# Step 7: Disconnect
Write-Host ""
Write-Host "📌 Disconnecting from Exchange Online..."
Disconnect-ExchangeOnline -Confirm:$false
Write-Host "✅ Disconnected"

# Final message
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
Write-Host "✅ Setup Complete!" -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
Write-Host ""
Write-Host "📌 Next steps:"
Write-Host "   1. Close Outlook completely (File → Exit)"
Write-Host "   2. Wait 30-60 seconds for Azure AD to sync"
Write-Host "   3. Reopen Outlook"
Write-Host "   4. You should now see dev-ap@chelseapiers.com with full inbox access"
Write-Host ""
Write-Host "💡 If still not visible:"
Write-Host "   - Close Outlook and clear cache: rm -r ~/Library/Group\\ Containers/UBF8T346G9.Office/"
Write-Host "   - Wait 2-3 minutes"
Write-Host "   - Reopen Outlook"
Write-Host ""
