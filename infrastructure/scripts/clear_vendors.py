#!/usr/bin/env python3
"""
Clear all vendors from the VendorMaster table.

Usage:
    python3 infrastructure/scripts/clear_vendors.py [--env prod|dev]

This script removes all vendor entries from the VendorMaster table.
Use with caution - this is destructive and cannot be undone.
After clearing, run seed_vendors.py to repopulate.
"""

import argparse
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from azure.data.tables import TableServiceClient
from azure.identity import DefaultAzureCredential


def get_connection_string(env: str) -> str:
    """Get storage connection string for environment."""
    # Try environment variable first
    conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if conn_str:
        return conn_str

    # Fall back to constructing from account name
    account_name = f"stinvoiceagent{env}"
    print(f"Using storage account: {account_name}")
    return f"https://{account_name}.table.core.windows.net"


def clear_vendors(env: str, dry_run: bool = False) -> int:
    """Clear all vendors from VendorMaster table."""
    table_name = "VendorMaster"

    try:
        conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        if conn_str:
            service = TableServiceClient.from_connection_string(conn_str)
        else:
            account_url = f"https://stinvoiceagent{env}.table.core.windows.net"
            credential = DefaultAzureCredential()
            service = TableServiceClient(endpoint=account_url, credential=credential)

        table_client = service.get_table_client(table_name)

        # Query all entities
        entities = list(table_client.query_entities("PartitionKey eq 'Vendor'"))
        count = len(entities)

        if count == 0:
            print(f"No vendors found in {table_name}")
            return 0

        if dry_run:
            print(f"[DRY RUN] Would delete {count} vendors:")
            for entity in entities[:10]:
                print(f"  - {entity['RowKey']}")
            if count > 10:
                print(f"  ... and {count - 10} more")
            return count

        # Delete each entity
        print(f"Deleting {count} vendors from {table_name}...")
        deleted = 0
        for entity in entities:
            table_client.delete_entity(
                partition_key=entity["PartitionKey"], row_key=entity["RowKey"]
            )
            deleted += 1
            if deleted % 10 == 0:
                print(f"  Deleted {deleted}/{count}...")

        print(f"Successfully deleted {deleted} vendors")
        return deleted

    except Exception as e:
        print(f"Error clearing vendors: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Clear all vendors from VendorMaster table"
    )
    parser.add_argument(
        "--env",
        choices=["prod", "dev"],
        default="prod",
        help="Environment (default: prod)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt",
    )

    args = parser.parse_args()

    if not args.dry_run and not args.force:
        response = input(
            f"Are you sure you want to delete ALL vendors from {args.env}? [y/N] "
        )
        if response.lower() != "y":
            print("Aborted")
            sys.exit(0)

    clear_vendors(args.env, args.dry_run)


if __name__ == "__main__":
    main()
