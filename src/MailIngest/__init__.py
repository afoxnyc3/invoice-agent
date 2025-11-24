"""
MailIngest timer function - Poll shared mailbox hourly as fallback.

Reads unread emails, downloads attachments to blob storage, and queues
for vendor extraction processing. Acts as fallback safety net in case
webhook notifications are missed.

Uses shared email_processor module for consistent processing logic
with MailWebhookProcessor.
"""

import os
import logging
import traceback
import azure.functions as func
from azure.storage.blob import BlobServiceClient
from shared.graph_client import GraphAPIClient
from shared.email_processor import should_skip_email, process_email_attachments

logger = logging.getLogger(__name__)


def main(timer: func.TimerRequest, outQueueItem: func.Out[str]):
    """Poll mailbox and queue unread emails with attachments."""
    try:
        # Startup diagnostics
        mailbox = os.environ["INVOICE_MAILBOX"]
        tenant_id = os.environ.get("GRAPH_TENANT_ID", "not-set")
        tenant_display = f"{tenant_id[:8]}..." if tenant_id != "not-set" else "not-set"

        logger.info(f"MailIngest starting - polling mailbox: {mailbox}")
        logger.debug(f"Graph API tenant: {tenant_display}")

        # Initialize Graph API client
        graph = GraphAPIClient()
        logger.debug("Graph API client initialized successfully")

        # Initialize blob storage
        blob_service = BlobServiceClient.from_connection_string(os.environ["AzureWebJobsStorage"])
        blob_container = blob_service.get_container_client("invoices")

        # Retrieve unread emails
        emails = graph.get_unread_emails(mailbox, max_results=50)
        logger.info(f"Found {len(emails)} unread emails in {mailbox}")

        for email in emails:
            # Check if email should be skipped for loop prevention
            skip, reason = should_skip_email(email, mailbox)
            if skip:
                logger.info(f"Skipping email {email['id']}: {reason}")
                # NOTE: Temporarily disabled to avoid Mail.ReadWrite requirement
                # graph.mark_as_read(mailbox, email["id"])
                continue

            if not email.get("hasAttachments"):
                logger.warning(f"Skipping email {email['id']} - no attachments")
                # NOTE: Temporarily disabled to avoid Mail.ReadWrite requirement
                # graph.mark_as_read(mailbox, email["id"])
                continue

            process_email_attachments(email, graph, mailbox, blob_container, outQueueItem)
            # NOTE: Temporarily disabled to avoid Mail.ReadWrite requirement
            # graph.mark_as_read(mailbox, email["id"])

        logger.info(f"MailIngest completed successfully - processed {len(emails)} emails")

    except KeyError as e:
        # Environment variable missing
        logger.error(f"MailIngest failed - missing environment variable: {str(e)}")
        logger.error("Check Key Vault secrets: INVOICE_MAILBOX, GRAPH_TENANT_ID, GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET")
        logger.debug(traceback.format_exc())
        raise
    except ValueError as e:
        # Authentication/credential error
        logger.error(f"MailIngest failed - invalid configuration: {str(e)}")
        logger.error("Check Graph API credentials in Key Vault")
        logger.debug(traceback.format_exc())
        raise
    except Exception as e:
        # Unexpected error
        logger.error(f"MailIngest failed with unexpected error: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(traceback.format_exc())
        raise
