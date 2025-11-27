"""
MailWebhookProcessor queue function - Process Graph API webhook notifications.

Consumes webhook notifications from the webhook-notifications queue,
fetches email details from Graph API, downloads attachments to blob storage,
and queues for vendor extraction processing.

This completes the webhook flow:
MailWebhook → webhook-notifications → MailWebhookProcessor → raw-mail → ExtractEnrich
"""

import logging
import json
import traceback
import azure.functions as func
from shared.graph_client import GraphAPIClient
from shared.email_processor import (
    parse_webhook_resource,
    process_email_attachments,
    should_skip_email,
)
from shared.config import config

logger = logging.getLogger(__name__)


def main(msg: func.QueueMessage, outQueueItem: func.Out[str]):
    """Process webhook notification and fetch email details."""
    try:
        # Parse notification message
        notification = json.loads(msg.get_body().decode("utf-8"))
        logger.info(f"Processing webhook notification: {notification.get('id')}")

        # Extract mailbox and message ID from resource path
        resource = notification.get("resource")
        if not resource:
            logger.error("Notification missing resource field")
            return

        mailbox, message_id = parse_webhook_resource(resource)
        logger.info(f"Fetching email {message_id} from {mailbox}")

        # Initialize Graph API client
        graph = GraphAPIClient()

        # Fetch email details
        email = graph.get_email(mailbox, message_id)
        if not email:
            logger.error(f"Email {message_id} not found")
            return

        # Check email loop prevention
        invoice_mailbox = config.invoice_mailbox
        should_skip, reason = should_skip_email(email, invoice_mailbox)
        if should_skip:
            logger.info(f"Skipping email {message_id}: {reason}")
            graph.mark_as_read(mailbox, message_id)
            return

        # Check for attachments
        if not email.get("hasAttachments"):
            logger.warning(f"Email {message_id} has no attachments - skipping")
            graph.mark_as_read(mailbox, message_id)
            return

        # Initialize blob storage (uses connection pooling via config)
        blob_container = config.get_container_client("invoices")

        # Process attachments and queue
        count = process_email_attachments(email, graph, mailbox, blob_container, outQueueItem)

        logger.info(f"Processed {count} attachments from email {message_id}")

        # Mark as read (requires Application Access Policy for secure mailbox restriction)
        graph.mark_as_read(mailbox, message_id)

        logger.info(f"MailWebhookProcessor completed for {message_id}")

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in notification: {str(e)}")
        logger.debug(traceback.format_exc())
        raise
    except ValueError as e:
        logger.error(f"Invalid notification format: {str(e)}")
        logger.debug(traceback.format_exc())
        raise
    except KeyError as e:
        logger.error(f"Missing environment variable: {str(e)}")
        logger.error("Check Key Vault secrets: INVOICE_MAILBOX, GRAPH_TENANT_ID, GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET")
        logger.debug(traceback.format_exc())
        raise
    except Exception as e:
        logger.error(f"MailWebhookProcessor failed: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(traceback.format_exc())
        raise
