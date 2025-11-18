# Shared Mailbox Permissions Setup

## Problem
You can send emails to the AP mailbox but can't read or manage folders. You need Full Access permission to see the inbox.

## Solution Overview

There are **3 ways** to grant yourself access:
1. **Azure Portal** (easiest, GUI-based)
2. **PowerShell/Exchange Online** (programmatic)
3. **Outlook Web Access** (limited, but worth trying)

---

## Option 1: Azure Portal (RECOMMENDED - Easiest)

### Step 1: Go to Azure Portal

```
https://portal.azure.com
```

### Step 2: Find the Shared Mailbox

1. Search for: `Shared Mailboxes` or `Azure Active Directory`
2. Navigate to: **Azure AD → Users → Shared Mailboxes**
   - OR: **Manage → Users**
3. Find: `dev-ap@chelseapiers.com`

### Step 3: Grant Delegate Access

1. Click on the mailbox: `dev-ap@chelseapiers.com`
2. In left menu: **Manage → Mail Settings**
3. Scroll to: **Mailbox Permissions** or **Delegates**
4. Click: **Add Delegate** or **Grant Permission**
5. Select: Your email address
6. Choose permissions:
   - ☑️ **Read** (see all content)
   - ☑️ **Read and Manage** (delete, move emails)
   - ☑️ **Send As** (send from this mailbox)
7. Click: **Save** or **Add**

### Step 4: Verify in Outlook

1. Sign out of Outlook
2. Sign back in
3. Shared mailbox should now show full inbox access

---

## Option 2: PowerShell/Exchange Online (Most Reliable)

### Prerequisites

```powershell
# Install Exchange Online Management module (run once)
Install-Module ExchangeOnlineManagement -Scope CurrentUser -Force
```

### Step 1: Connect to Exchange Online

```powershell
# Open PowerShell and run:
Connect-ExchangeOnline

# You'll be prompted to sign in with your account
# Use account: alex@chelseapiers.com (or whatever your admin account is)
```

### Step 2: Grant Full Access Permission

```powershell
# Replace email addresses with yours
$YourEmail = "alex@chelseapiers.com"  # ← UPDATE THIS
$MailboxToAccess = "dev-ap@chelseapiers.com"

# Grant Full Access (read all emails)
Add-MailboxPermission -Identity $MailboxToAccess `
  -User $YourEmail `
  -AccessRights FullAccess `
  -InheritanceType All
```

**Expected output:**
```
Identity      : dev-ap@chelseapiers.com
User          : alex@chelseapiers.com
AccessRights  : {FullAccess}
InheritanceType : All
```

### Step 3: Grant "Send As" Permission (Optional but Recommended)

```powershell
# Also grant SendAs so you can send emails FROM this mailbox
Add-MailboxPermission -Identity $MailboxToAccess `
  -User $YourEmail `
  -AccessRights SendAs
```

### Step 4: Verify Permissions

```powershell
# List all permissions on the mailbox
Get-MailboxPermission -Identity $MailboxToAccess
```

**Look for your email with:**
- ✅ `AccessRights: FullAccess`
- ✅ `AccessRights: SendAs`

### Step 5: Refresh Outlook

1. Close Outlook completely (File → Exit)
2. Wait 30 seconds
3. Reopen Outlook
4. You should now see the full inbox for `dev-ap@chelseapiers.com`

---

## Option 3: Outlook Web Access (OWA) - Manual Approach

### If You Still Can't Access via Desktop

1. Go to: `https://outlook.office.com`
2. Sign in with your account
3. Click: Settings (gear icon) → **Open shared mailbox**
4. Search: `dev-ap@chelseapiers.com`
5. If accessible: Click to open
6. If not: You need Option 1 or 2 (need permissions first)

---

## Troubleshooting

### "I still can't see the inbox after permissions are granted"

**Try these steps:**

```powershell
# 1. Verify permission was actually granted
Get-MailboxPermission -Identity dev-ap@chelseapiers.com | grep $YourEmail

# 2. If not showing, re-add it
Remove-MailboxPermission -Identity dev-ap@chelseapiers.com `
  -User $YourEmail `
  -AccessRights FullAccess `
  -Confirm:$false

# 3. Add again
Add-MailboxPermission -Identity dev-ap@chelseapiers.com `
  -User $YourEmail `
  -AccessRights FullAccess `
  -InheritanceType All

# 4. Wait 30-60 seconds for Azure AD sync
# Then close and reopen Outlook
```

### "I don't have admin permissions to run these commands"

**You need a tenant admin to run these commands.** Contact your Azure/Office 365 admin and provide them with:

```
Email to grant access: [your-email]
Mailbox to access: dev-ap@chelseapiers.com
Permissions needed: FullAccess, SendAs
```

**Admin can run:**
```powershell
Connect-ExchangeOnline
Add-MailboxPermission -Identity dev-ap@chelseapiers.com `
  -User [your-email] -AccessRights FullAccess -InheritanceType All
```

### "Permissions work in PowerShell but not in Outlook"

**This is usually a caching issue:**

1. Close Outlook completely
2. Clear Office cache: `C:\Users\[YOU]\AppData\Local\Microsoft\Office\16.0\`
3. Wait 2 minutes
4. Reopen Outlook
5. May take 5-10 minutes to fully sync

---

## What Each Permission Level Means

| Permission | Read Inbox | Delete Emails | Move Emails | Send As | Send On Behalf |
|------------|-----------|----------------|-----------|---------|-----------------|
| **Reviewer** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Editor** | ✅ | ✅ | ✅ | ❌ | ✅ |
| **FullAccess** | ✅ | ✅ | ✅ | ✅ | ✅ |

**For testing, you need: FullAccess**

---

## For Testing: Minimum Permissions Needed

To verify emails are being routed correctly:

```powershell
# Run this command to grant exactly what you need for testing:
Add-MailboxPermission -Identity dev-ap@chelseapiers.com `
  -User alex@chelseapiers.com `
  -AccessRights FullAccess `
  -InheritanceType All `
  -Confirm:$false
```

This gives you:
- ✅ Read all emails in the inbox
- ✅ See when new emails arrive
- ✅ Count emails to detect loops
- ✅ Delete test emails after testing
- ✅ Move emails to folders

---

## Quick Checklist

After granting permissions, verify:

- [ ] Can open `dev-ap@chelseapiers.com` in Outlook
- [ ] Can see **Inbox** folder
- [ ] Can see **unread email count**
- [ ] Can open individual emails
- [ ] Can move emails to folders (or delete)
- [ ] Permission shows in PowerShell: `Get-MailboxPermission`

If all checked: **You're ready for testing!** ✅

---

## For the Testing Phase

Once you have access, use these tools:

```bash
# Quick check - see unread counts
python scripts/verify_test_emails.py

# Manual Outlook - watch inbox
# Open both dev-invoices and dev-ap in separate browser tabs
# Watch unread counts in real-time

# After test - analyze results
python scripts/analyze_test_results.py
```

---

## Reference: PowerShell One-Liner

If you just want to copy-paste:

```powershell
# 1. Install module (first time only)
Install-Module ExchangeOnlineManagement -Scope CurrentUser -Force

# 2. Connect
Connect-ExchangeOnline

# 3. Grant access (update email addresses)
Add-MailboxPermission -Identity "dev-ap@chelseapiers.com" -User "alex@chelseapiers.com" -AccessRights FullAccess -InheritanceType All

# 4. Verify
Get-MailboxPermission -Identity "dev-ap@chelseapiers.com"

# 5. Close PowerShell, restart Outlook
exit
```

---

**Document Version:** 1.0
**Last Updated:** 2024-11-17
**Status:** Ready for use
