"""
MailIngest timer function - Poll shared mailbox hourly as fallback.

Reads unread emails, downloads attachments to blob storage, and queues
for vendor extraction processing. Acts as fallback safety net in case
webhook notifications are missed.

Uses shared email_processor module for consistent processing logic
with MailWebhookProcessor.
"""

import logging
import os
import traceback
import azure.functions as func
from shared.graph_client import GraphAPIClient
from shared.email_processor import should_skip_email, process_email_attachments
from shared.config import config

logger = logging.getLogger(__name__)


def _is_disabled_via_flag() -> bool:
    """Return True if MAIL_INGEST_ENABLED explicitly disables the timer."""

    flag = os.getenv("MAIL_INGEST_ENABLED", "true").lower()
    return flag in {"0", "false", "no"}


def _missing_required_settings() -> list[str]:
    """List required settings that are not configured."""

    missing = []

    # Check Graph API settings
    graph_settings = ["INVOICE_MAILBOX", "GRAPH_TENANT_ID", "GRAPH_CLIENT_ID", "GRAPH_CLIENT_SECRET"]
    for key in graph_settings:
        if not os.getenv(key):
            missing.append(key)

    # Check storage - supports both connection string and MSI formats
    has_connection_string = bool(os.getenv("AzureWebJobsStorage"))
    has_msi_config = bool(os.getenv("AzureWebJobsStorage__accountName"))
    if not has_connection_string and not has_msi_config:
        missing.append("AzureWebJobsStorage (or AzureWebJobsStorage__accountName)")

    return missing


def main(timer: func.TimerRequest, outQueueItem: func.Out[str]) -> None:
    """Poll mailbox and queue unread emails with attachments."""
    if _is_disabled_via_flag():
        logger.info("MailIngest disabled via MAIL_INGEST_ENABLED flag - skipping execution")
        return

    missing_settings = _missing_required_settings()
    if missing_settings:
        logger.warning(
            "MailIngest skipped - missing required settings: %s",
            ", ".join(sorted(missing_settings)),
        )
        return

    try:
        # Startup diagnostics
        mailbox = config.invoice_mailbox
        tenant_id = config.graph_tenant_id
        tenant_display = f"{tenant_id[:8]}..." if tenant_id else "not-set"

        logger.info(f"MailIngest starting - polling mailbox: {mailbox}")
        logger.debug(f"Graph API tenant: {tenant_display}")

        # Initialize Graph API client
        graph = GraphAPIClient()
        logger.debug("Graph API client initialized successfully")

        # Initialize blob storage (uses connection pooling via config)
        blob_container = config.get_container_client("invoices")

        # Retrieve unread emails
        emails = graph.get_unread_emails(mailbox, max_results=50)
        logger.info(f"Found {len(emails)} unread emails in {mailbox}")

        for email in emails:
            # Check if email should be skipped for loop prevention
            skip, reason = should_skip_email(email, mailbox)
            if skip:
                logger.info(f"Skipping email {email['id']}: {reason}")
                graph.mark_as_read(mailbox, email["id"])
                continue

            if not email.get("hasAttachments"):
                logger.warning(f"Skipping email {email['id']} - no attachments")
                graph.mark_as_read(mailbox, email["id"])
                continue

            process_email_attachments(email, graph, mailbox, blob_container, outQueueItem)
            graph.mark_as_read(mailbox, email["id"])

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
