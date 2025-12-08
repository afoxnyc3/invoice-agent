#!/usr/bin/env python3
"""
Force recreate Graph API webhook subscription for the correct mailbox.

Usage:
    python scripts/recreate_subscription.py

This script:
1. Deletes any existing Graph subscriptions
2. Creates a new subscription for INVOICE_MAILBOX
3. Saves the subscription to GraphSubscriptions table
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from shared.graph_client import GraphAPIClient
from shared.config import config


def main():
    print("=== Recreating Graph API Webhook Subscription ===\n")

    # Get required config
    mailbox = os.environ.get("INVOICE_MAILBOX")
    webhook_url = os.environ.get("MAIL_WEBHOOK_URL")
    client_state = os.environ.get("GRAPH_CLIENT_STATE")

    if not all([mailbox, webhook_url, client_state]):
        print("ERROR: Missing required environment variables:")
        print(f"  INVOICE_MAILBOX: {'SET' if mailbox else 'MISSING'}")
        print(f"  MAIL_WEBHOOK_URL: {'SET' if webhook_url else 'MISSING'}")
        print(f"  GRAPH_CLIENT_STATE: {'SET' if client_state else 'MISSING'}")
        sys.exit(1)

    print(f"Mailbox: {mailbox}")
    print(f"Webhook URL: {webhook_url}")
    print(f"Client State: {client_state[:8]}...")
    print()

    # Initialize clients
    print("Initializing Graph API client...")
    graph = GraphAPIClient()
    print("Graph API client initialized\n")

    # Get table client
    print("Connecting to Table Storage...")
    table_service = config.table_service
    if not table_service:
        print("ERROR: Cannot connect to Table Storage")
        sys.exit(1)

    table_client = table_service.get_table_client("GraphSubscriptions")
    print("Connected to GraphSubscriptions table\n")

    # Query existing subscriptions
    print("Checking existing subscriptions...")
    try:
        entities = list(table_client.query_entities("PartitionKey eq 'GraphSubscription'"))
        print(f"Found {len(entities)} subscription records in table")

        for entity in entities:
            sub_id = entity.get("SubscriptionId", "unknown")
            is_active = entity.get("IsActive", False)
            print(f"  - {sub_id[:20]}... (Active: {is_active})")

            if is_active:
                # Try to delete from Graph API
                print(f"    Attempting to delete from Graph API...")
                try:
                    graph.delete_subscription(sub_id)
                    print(f"    Deleted from Graph API")
                except Exception as e:
                    print(f"    Could not delete (may already be expired): {e}")

                # Mark as inactive in table
                entity["IsActive"] = False
                table_client.update_entity(entity)
                print(f"    Marked as inactive in table")
    except Exception as e:
        print(f"  Error querying subscriptions: {e}")

    print()

    # Create new subscription
    print("Creating new Graph API subscription...")
    print(f"  Mailbox: {mailbox}")
    print(f"  Webhook: {webhook_url}")

    try:
        result = graph.create_subscription(mailbox=mailbox, webhook_url=webhook_url, client_state=client_state)

        new_id = result.get("id", "")
        expiration = result.get("expirationDateTime", "")

        print(f"\n  SUCCESS!")
        print(f"  Subscription ID: {new_id}")
        print(f"  Expires: {expiration}")

        # Save to table
        print("\nSaving subscription to table...")
        entity = {
            "PartitionKey": "GraphSubscription",
            "RowKey": new_id,
            "SubscriptionId": new_id,
            "ExpirationDateTime": expiration,
            "CreatedAt": datetime.now(timezone.utc).isoformat(),
            "LastRenewed": datetime.now(timezone.utc).isoformat(),
            "IsActive": True,
        }
        table_client.upsert_entity(entity)
        print("  Saved to GraphSubscriptions table")

        print("\n=== Subscription Created Successfully ===")
        print(f"Mailbox being monitored: {mailbox}")
        print(f"Webhook endpoint: {webhook_url}")
        print(f"Subscription expires: {expiration}")

    except Exception as e:
        print(f"\nERROR creating subscription: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
