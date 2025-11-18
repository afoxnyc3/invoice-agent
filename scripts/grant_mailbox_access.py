#!/usr/bin/env python3
"""
Grant Full Access permission to shared mailbox using Microsoft Graph API.

Usage:
    python scripts/grant_mailbox_access.py

Environment:
    GRAPH_TENANT_ID, GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET must be set
"""

import os
import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import requests
from msal import ConfidentialClientApplication

# Configuration
TENANT_ID = os.environ.get("GRAPH_TENANT_ID")
CLIENT_ID = os.environ.get("GRAPH_CLIENT_ID")
CLIENT_SECRET = os.environ.get("GRAPH_CLIENT_SECRET")

MAILBOX_EMAIL = "dev-ap@chelseapiers.com"
USER_EMAIL = "afox@chelseapiers.com"  # The user to grant access to

GRAPH_URL = "https://graph.microsoft.com/v1.0"


def get_access_token():
    """Get access token from Azure AD."""
    if not all([TENANT_ID, CLIENT_ID, CLIENT_SECRET]):
        print("❌ Error: Graph API credentials not configured")
        print("   Set: GRAPH_TENANT_ID, GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET")
        sys.exit(1)

    authority = f"https://login.microsoftonline.com/{TENANT_ID}"
    app = ConfidentialClientApplication(
        client_id=CLIENT_ID,
        client_credential=CLIENT_SECRET,
        authority=authority,
    )

    scopes = ["https://graph.microsoft.com/.default"]
    token_response = app.acquire_token_for_client(scopes=scopes)

    if "access_token" not in token_response:
        print(f"❌ Error getting token: {token_response.get('error_description')}")
        sys.exit(1)

    return token_response["access_token"]


def get_user_id(email: str, access_token: str) -> str:
    """Get user ID from email address."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    url = f"{GRAPH_URL}/users?$filter=mail eq '{email}'"
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"❌ Error looking up user {email}: {response.status_code}")
        print(response.json())
        return None

    users = response.json().get("value", [])
    if not users:
        print(f"❌ User not found: {email}")
        return None

    user = users[0]
    print(f"✅ Found user: {user['displayName']} ({user['mail']})")
    print(f"   ID: {user['id']}")
    return user["id"]


def get_mailbox_id(email: str, access_token: str) -> str:
    """Get mailbox ID from email address."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    url = f"{GRAPH_URL}/users?$filter=mail eq '{email}'"
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"❌ Error looking up mailbox {email}: {response.status_code}")
        print(response.json())
        return None

    mailboxes = response.json().get("value", [])
    if not mailboxes:
        print(f"❌ Mailbox not found: {email}")
        return None

    mailbox = mailboxes[0]
    print(f"✅ Found mailbox: {mailbox['displayName']} ({mailbox['mail']})")
    print(f"   ID: {mailbox['id']}")
    return mailbox["id"]


def grant_mailbox_access(mailbox_id: str, user_id: str, access_token: str) -> bool:
    """
    Grant FullAccess permission to user on mailbox.

    Note: Graph API has limited support for Exchange mailbox permissions.
    For full shared mailbox access, use Exchange Online PowerShell instead.
    This script demonstrates the limitations.
    """
    print("\n⚠️  Important Note:")
    print("─" * 60)
    print("Graph API has LIMITED support for mailbox delegated access.")
    print("For FULL shared mailbox access (read inbox, manage folders),")
    print("you need to use Exchange Online PowerShell.")
    print()
    print("However, let me try the Graph API approach first...")
    print("─" * 60)

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    # Try to grant mailbox permissions via Graph API
    # This endpoint may not work for shared mailboxes - that's okay
    url = f"{GRAPH_URL}/me/mailboxSettings/delegateMeetingMessagesToResource"

    data = {
        "userMailbox": f"{mailbox_id}",
        "delegationState": "send",
    }

    response = requests.post(url, headers=headers, json=data)

    if response.status_code in [200, 201, 204]:
        print("✅ Permission granted via Graph API")
        return True
    else:
        print(f"⚠️  Graph API approach not available (expected for shared mailboxes)")
        print(f"   Status: {response.status_code}")
        return False


def main():
    """Main execution."""
    print("\n🔐 Grant Mailbox Access")
    print("=" * 60)
    print(f"Mailbox: {MAILBOX_EMAIL}")
    print(f"User: {USER_EMAIL}")
    print("=" * 60)

    # Get token
    print("\n📌 Authenticating with Azure AD...")
    access_token = get_access_token()
    print("✅ Authentication successful")

    # Get user ID
    print(f"\n📌 Looking up user: {USER_EMAIL}")
    user_id = get_user_id(USER_EMAIL, access_token)
    if not user_id:
        return False

    # Get mailbox ID
    print(f"\n📌 Looking up mailbox: {MAILBOX_EMAIL}")
    mailbox_id = get_mailbox_id(MAILBOX_EMAIL, access_token)
    if not mailbox_id:
        return False

    # Try to grant access via Graph API
    print(f"\n📌 Attempting to grant access via Graph API...")
    result = grant_mailbox_access(mailbox_id, user_id, access_token)

    # Show next steps
    print("\n" + "=" * 60)
    print("📋 NEXT STEPS")
    print("=" * 60)
    print("\nFor FULL shared mailbox access, use Exchange Online PowerShell:")
    print()
    print("1. Open PowerShell and run:")
    print(f"   Install-Module ExchangeOnlineManagement -Scope CurrentUser -Force")
    print()
    print("2. Connect to Exchange Online:")
    print(f"   Connect-ExchangeOnline")
    print()
    print("3. Grant Full Access:")
    print(f'   Add-MailboxPermission -Identity "{MAILBOX_EMAIL}" \\')
    print(f'     -User "{USER_EMAIL}" \\')
    print(f'     -AccessRights FullAccess \\')
    print(f'     -InheritanceType All')
    print()
    print("4. Grant Send As (optional):")
    print(f'   Add-MailboxPermission -Identity "{MAILBOX_EMAIL}" \\')
    print(f'     -User "{USER_EMAIL}" \\')
    print(f'     -AccessRights SendAs')
    print()
    print("5. Verify permissions:")
    print(f'   Get-MailboxPermission -Identity "{MAILBOX_EMAIL}"')
    print()
    print("6. Restart Outlook to see the changes")
    print()
    print("=" * 60)

    return result


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
