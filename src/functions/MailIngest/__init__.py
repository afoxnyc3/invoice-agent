"""
MailIngest timer function - Poll shared mailbox every 5 minutes.

Reads unread emails, downloads attachments to blob storage, and queues
for vendor extraction processing.
"""

import os
import logging
import json
import base64
from datetime import datetime
import azure.functions as func
from azure.storage.blob import BlobServiceClient
from shared.graph_client import GraphAPIClient
from shared.ulid_generator import generate_ulid
from shared.models import RawMail

logger = logging.getLogger(__name__)


def _process_email(email: dict, graph: GraphAPIClient, mailbox: str, blob_container, queue_output):
    """Process single email: download attachments and queue."""
    transaction_id = generate_ulid()
    attachments = graph.get_attachments(mailbox, email["id"])

    for attachment in attachments:
        blob_name = f"{transaction_id}/{attachment['name']}"
        blob_client = blob_container.get_blob_client(blob_name)
        content = base64.b64decode(attachment["contentBytes"])
        blob_client.upload_blob(content, overwrite=True)

        raw_mail = RawMail(
            id=transaction_id,
            sender=email["sender"]["emailAddress"]["address"],
            subject=email["subject"],
            blob_url=blob_client.url,
            received_at=email["receivedDateTime"],
        )
        queue_output.set(raw_mail.model_dump_json())
        logger.info(f"Queued: {transaction_id} from {raw_mail.sender}")


def main(timer: func.TimerRequest, outQueueItem: func.Out[str]):
    """Poll mailbox and queue unread emails with attachments."""
    try:
        mailbox = os.environ["INVOICE_MAILBOX"]
        graph = GraphAPIClient()
        blob_service = BlobServiceClient.from_connection_string(os.environ["AzureWebJobsStorage"])
        blob_container = blob_service.get_container_client("invoices")
        emails = graph.get_unread_emails(mailbox, max_results=50)
        logger.info(f"Found {len(emails)} unread emails")

        for email in emails:
            if not email.get("hasAttachments"):
                logger.warning(f"Skipping email {email['id']} - no attachments")
                graph.mark_as_read(mailbox, email["id"])
                continue
            _process_email(email, graph, mailbox, blob_container, outQueueItem)
            graph.mark_as_read(mailbox, email["id"])
    except Exception as e:
        logger.error(f"MailIngest failed: {str(e)}")
        raise
