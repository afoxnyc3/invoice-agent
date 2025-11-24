#!/usr/bin/env python3
"""Manually initialize Graph API subscription for dev environment."""

import sys
import os

# Add src to path
sys.path.insert(0, '/Users/alex/dev/invoice-agent/src')

from shared.graph_client import GraphAPIClient
from azure.data.tables import TableServiceClient
from datetime import datetime

def main():
    # Get configuration from environment or Key Vault
    print("🔧 Initializing Graph API Subscription...")
    print("=" * 60)

    # Get values from Azure CLI
    import subprocess

    def get_secret(vault, secret_name):
        result = subprocess.run(
            ['az', 'keyvault', 'secret', 'show',
             '--vault-name', vault,
             '--name', secret_name,
             '--query', 'value', '-o', 'tsv'],
            capture_output=True, text=True
        )
        return result.stdout.strip()

    # Get connection string
    result = subprocess.run(
        ['az', 'storage', 'account', 'show-connection-string',
         '--name', 'stinvoiceagentdev',
         '--resource-group', 'rg-invoice-agent-dev',
         '--query', 'connectionString', '-o', 'tsv'],
        capture_output=True, text=True
    )
    storage_conn = result.stdout.strip()

    # Get secrets
    print("📝 Retrieving configuration from Key Vault...")
    mailbox = get_secret('kv-invoice-agent-dev', 'invoice-mailbox')
    webhook_url = get_secret('kv-invoice-agent-dev', 'mail-webhook-url')
    client_state = get_secret('kv-invoice-agent-dev', 'graph-client-state')

    # Get Graph API credentials
    tenant_id = get_secret('kv-invoice-agent-dev', 'graph-tenant-id')
    client_id = get_secret('kv-invoice-agent-dev', 'graph-client-id')
    client_secret = get_secret('kv-invoice-agent-dev', 'graph-client-secret')

    print(f"   Mailbox: {mailbox}")
    print(f"   Webhook URL: {webhook_url[:60]}...")
    print(f"   Client State: {client_state[:20]}...")
    print(f"   Tenant ID: {tenant_id[:20]}...")
    print()

    # Initialize Graph API client
    print("📝 Initializing Graph API client...")
    graph = GraphAPIClient(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret
    )
    print()

    # Create subscription
    print("📝 Creating Graph API subscription...")
    result = graph.create_subscription(
        mailbox=mailbox,
        webhook_url=webhook_url,
        client_state=client_state
    )

    subscription_id = result.get("id")
    expiration = result.get("expirationDateTime")
    resource = result.get("resource")

    print(f"   ✅ Subscription created successfully!")
    print(f"   ID: {subscription_id}")
    print(f"   Expires: {expiration}")
    print(f"   Resource: {resource}")
    print()

    # Save to Table Storage
    print("📝 Saving subscription to Table Storage...")
    table_service = TableServiceClient.from_connection_string(storage_conn)

    # Create table if not exists
    try:
        table_service.create_table("GraphSubscriptions")
        print("   Created GraphSubscriptions table")
    except Exception:
        print("   GraphSubscriptions table already exists")

    table_client = table_service.get_table_client("GraphSubscriptions")

    entity = {
        "PartitionKey": "GraphSubscription",
        "RowKey": subscription_id,
        "SubscriptionId": subscription_id,
        "Resource": resource,
        "ExpirationDateTime": expiration,
        "IsActive": True,
        "CreatedAt": datetime.utcnow().isoformat() + "Z",
        "LastRenewed": datetime.utcnow().isoformat() + "Z"
    }

    table_client.upsert_entity(entity)
    print(f"   ✅ Subscription record saved")
    print()

    print("✅ Subscription initialization complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Verify subscription in GraphSubscriptions table")
    print("2. Send test email to", mailbox)
    print("3. Watch for webhook notification in Application Insights")

if __name__ == "__main__":
    main()
