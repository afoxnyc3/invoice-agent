#!/usr/bin/env python3
"""Test script to verify Graph API subscription creation."""

import os
import sys

# Set up path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from shared.graph_client import GraphAPIClient

def main():
    """Test creating a Graph API subscription."""
    print("🧪 Testing Graph API Subscription Creation")
    print("=" * 50)
    print()

    # Get configuration from environment
    mailbox = os.environ.get("INVOICE_MAILBOX")
    webhook_url = os.environ.get("MAIL_WEBHOOK_URL")
    client_state = os.environ.get("GRAPH_CLIENT_STATE")

    if not all([mailbox, webhook_url, client_state]):
        print("❌ Missing environment variables:")
        print(f"   INVOICE_MAILBOX: {'✓' if mailbox else '✗'}")
        print(f"   MAIL_WEBHOOK_URL: {'✓' if webhook_url else '✗'}")
        print(f"   GRAPH_CLIENT_STATE: {'✓' if client_state else '✗'}")
        print()
        print("Run: export $(az functionapp config appsettings list \\")
        print("  --name func-invoice-agent-dev \\")
        print("  --resource-group rg-invoice-agent-dev \\")
        print("  --query \"[].{name:name, value:value}\" \\")
        print("  -o tsv | awk '{print $1\"=\"$2}')")
        return 1

    print(f"📧 Mailbox: {mailbox}")
    print(f"🔗 Webhook URL: {webhook_url[:50]}...")
    print(f"🔐 Client State: {client_state[:20]}...")
    print()

    try:
        print("Creating Graph API client...")
        graph = GraphAPIClient()
        print("✅ Client created")
        print()

        print("Creating subscription...")
        result = graph.create_subscription(
            mailbox=mailbox,
            webhook_url=webhook_url,
            client_state=client_state
        )

        subscription_id = result.get("id")
        expiration = result.get("expirationDateTime")

        print("✅ Subscription created successfully!")
        print()
        print(f"Subscription ID: {subscription_id}")
        print(f"Expiration: {expiration}")
        print()
        print("🎉 Test passed! Webhook is ready to receive notifications.")
        return 0

    except Exception as e:
        print(f"❌ Failed to create subscription: {str(e)}")
        import traceback
        print()
        print("Traceback:")
        print(traceback.format_exc())
        return 1

if __name__ == "__main__":
    sys.exit(main())
