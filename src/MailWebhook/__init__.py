"""
MailWebhook HTTP function - Receive Graph API change notifications.

Handles:
- Validation handshake during subscription creation
- Notification processing when emails arrive in the mailbox

Graph sends a POST request when new mail arrives. This function validates
the request and queues the email for processing by existing pipeline.
"""

import os
import logging
import json
import urllib.parse
import azure.functions as func
from shared.ulid_generator import generate_ulid

logger = logging.getLogger(__name__)


def main(req: func.HttpRequest, outQueueItem: func.Out[str]) -> func.HttpResponse:
    """
    Handle Microsoft Graph webhook validation and email notifications.

    Two modes:
    1. Validation: Graph sends validationToken param, respond with token
    2. Notification: Graph sends notification payload, queue for processing
    """
    try:
        # MODE 1: VALIDATION HANDSHAKE
        # Graph sends this during subscription creation to verify endpoint
        validation_token = req.params.get("validationToken")
        if validation_token:
            logger.info("Webhook validation request received")
            # Must respond with URL-decoded token as plain text
            decoded_token = urllib.parse.unquote(validation_token)
            return func.HttpResponse(decoded_token, status_code=200, mimetype="text/plain")

        # MODE 2: NOTIFICATION PROCESSING
        # Graph sends notification when email arrives
        try:
            req_body = req.get_json()
        except ValueError:
            logger.error("Invalid JSON in webhook request")
            return func.HttpResponse(status_code=400)

        # Validate client state for security
        expected_state = os.environ.get("GRAPH_CLIENT_STATE", "")
        if not expected_state:
            logger.error("GRAPH_CLIENT_STATE not configured")
            return func.HttpResponse(status_code=500)

        notifications = req_body.get("value", [])
        if not notifications:
            logger.warning("Webhook received empty notifications")
            return func.HttpResponse(status_code=202)

        logger.info(f"Received {len(notifications)} notification(s)")

        for notification in notifications:
            # Security: Verify client state matches what we set
            client_state = notification.get("clientState", "")
            if client_state != expected_state:
                logger.error(
                    f"Invalid clientState in notification. "
                    f"Expected: {expected_state[:8]}..., Got: {client_state[:8] if client_state else 'None'}..."
                )
                continue

            # Extract notification details
            subscription_id = notification.get("subscriptionId")
            resource = notification.get("resource")
            change_type = notification.get("changeType")

            logger.info(
                f"Processing notification: type={change_type}, " f"subscription={subscription_id}, resource={resource}"
            )

            # Queue message for processing
            # Use same format as MailIngest for compatibility
            webhook_message = {
                "id": generate_ulid(),
                "type": "webhook",
                "subscription_id": subscription_id,
                "resource": resource,
                "change_type": change_type,
                "timestamp": notification.get("clientState"),
            }

            outQueueItem.set(json.dumps(webhook_message))
            logger.info(f"Queued webhook notification: {webhook_message['id']}")

        # Return 202 Accepted to Graph
        return func.HttpResponse(status_code=202)

    except Exception as e:
        logger.error(f"MailWebhook error: {str(e)}", exc_info=True)
        # Return 500 so Graph retries
        return func.HttpResponse(status_code=500)
