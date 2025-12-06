"""
SubscriptionManager timer function - Manage Microsoft Graph subscriptions.

Runs every 6 days to renew email change notification subscriptions.
Graph subscriptions expire after a maximum of 7 days (4230 minutes) for
mail resources, so this timer ensures subscriptions stay active.

Subscription lifecycle:
1. On first run: Create new subscription
2. On subsequent runs: Renew existing subscription
3. Store subscription ID in Table Storage for tracking
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
import azure.functions as func
from azure.data.tables import TableServiceClient, TableClient
from shared.graph_client import GraphAPIClient
from shared.ulid_generator import generate_ulid
from shared.config import config

logger = logging.getLogger(__name__)


def _get_subscription_record(table_client: TableClient) -> dict[str, Any] | None:
    """Retrieve current subscription from Table Storage."""
    try:
        # Query for active subscriptions
        query_filter = "PartitionKey eq 'GraphSubscription' and IsActive eq true"
        entities = list(table_client.query_entities(query_filter))

        if entities:
            return entities[0]  # Return first active subscription
        return None
    except Exception as e:
        logger.error(f"Error querying subscriptions: {str(e)}")
        return None


def _save_subscription_record(table_client: TableClient, subscription_id: str, expiration: str) -> None:
    """Save subscription details to Table Storage."""
    entity = {
        "PartitionKey": "GraphSubscription",
        "RowKey": subscription_id,
        "SubscriptionId": subscription_id,
        "ExpirationDateTime": expiration,
        "CreatedAt": datetime.now(timezone.utc).isoformat(),
        "LastRenewed": datetime.now(timezone.utc).isoformat(),
        "IsActive": True,
    }
    try:
        table_client.upsert_entity(entity)
        logger.info(f"Saved subscription record: {subscription_id}")
    except Exception as e:
        logger.error(f"Error saving subscription: {str(e)}")
        raise


def _deactivate_old_subscriptions(table_client: TableClient, current_subscription_id: str) -> None:
    """Mark old subscriptions as inactive."""
    try:
        query_filter = "PartitionKey eq 'GraphSubscription' and IsActive eq true"
        entities = list(table_client.query_entities(query_filter))

        for entity in entities:
            if entity["RowKey"] != current_subscription_id:
                entity["IsActive"] = False
                table_client.update_entity(entity)
                logger.info(f"Deactivated old subscription: {entity['RowKey']}")
    except Exception as e:
        logger.error(f"Error deactivating subscriptions: {str(e)}")


def main(timer: func.TimerRequest) -> None:
    """Create or renew Graph API subscription for email notifications."""
    try:
        # Check storage availability first (may be unavailable during slot swaps)
        if not config.is_storage_available:
            logger.warning(
                "AzureWebJobsStorage not available - skipping execution. "
                "This may occur during slot swaps and will resolve automatically."
            )
            return

        # Get configuration (these are required - fail loudly if missing)
        mailbox = os.environ.get("INVOICE_MAILBOX")
        webhook_url = os.environ.get("MAIL_WEBHOOK_URL")
        client_state = os.environ.get("GRAPH_CLIENT_STATE")

        if not mailbox:
            logger.error("INVOICE_MAILBOX not configured")
            raise ValueError("Missing INVOICE_MAILBOX configuration")

        if not webhook_url:
            logger.error("MAIL_WEBHOOK_URL not configured")
            raise ValueError("Missing MAIL_WEBHOOK_URL configuration")

        if not client_state:
            logger.error("GRAPH_CLIENT_STATE not configured")
            raise ValueError("Missing GRAPH_CLIENT_STATE configuration")

        logger.info(f"SubscriptionManager starting for mailbox: {mailbox}")

        # Initialize clients using centralized config
        graph = GraphAPIClient()
        table_service = config.table_service
        if not table_service:
            logger.warning("Table service unavailable - skipping execution")
            return
        table_client = table_service.get_table_client("GraphSubscriptions")

        # Ensure table exists
        try:
            table_service.create_table("GraphSubscriptions")
            logger.info("Created GraphSubscriptions table")
        except Exception:
            pass  # Table already exists

        # Check for existing subscription
        existing_subscription = _get_subscription_record(table_client)

        if existing_subscription:
            # Renew existing subscription
            subscription_id = existing_subscription["SubscriptionId"]
            logger.info(f"Renewing subscription: {subscription_id}")

            try:
                result = graph.renew_subscription(subscription_id)
                expiration = result.get("expirationDateTime")

                # Update record
                existing_subscription["LastRenewed"] = datetime.now(timezone.utc).isoformat()
                existing_subscription["ExpirationDateTime"] = expiration
                table_client.update_entity(existing_subscription)

                logger.info(f"✅ Subscription renewed successfully. " f"Expires: {expiration}")

            except Exception as e:
                logger.error(f"Failed to renew subscription {subscription_id}: {str(e)}")
                logger.info("Creating new subscription instead...")
                existing_subscription = None  # Force creation of new subscription

        if not existing_subscription:
            # Create new subscription
            logger.info("Creating new Graph API subscription...")

            result = graph.create_subscription(mailbox=mailbox, webhook_url=webhook_url, client_state=client_state)

            new_subscription_id: str = result.get("id", "")
            new_expiration: str = result.get("expirationDateTime", "")

            if not new_subscription_id or not new_expiration:
                raise ValueError("Subscription response missing required fields")

            logger.info(
                f"✅ Subscription created successfully. " f"ID: {new_subscription_id}, Expires: {new_expiration}"
            )

            # Save to Table Storage
            _save_subscription_record(table_client, new_subscription_id, new_expiration)

            # Deactivate any old subscriptions
            _deactivate_old_subscriptions(table_client, new_subscription_id)

        logger.info("SubscriptionManager completed successfully")

    except Exception as e:
        logger.error(f"SubscriptionManager failed: {str(e)}", exc_info=True)
        raise
