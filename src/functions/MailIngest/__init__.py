"""
MailIngest timer function - Poll shared mailbox every 5 minutes.

Reads unread emails, downloads attachments to blob storage, and queues
for vendor extraction processing.

Implements email loop prevention by filtering:
- Emails from the system mailbox (INVOICE_MAILBOX)
- System-generated invoice emails (subject pattern matching)
- Replies to vendor registration emails
"""

import os
import logging
import re
import base64
import azure.functions as func
from azure.storage.blob import BlobServiceClient
from shared.graph_client import GraphAPIClient
from shared.ulid_generator import generate_ulid
from shared.models import RawMail

logger = logging.getLogger(__name__)


def _should_skip_email(email: dict, invoice_mailbox: str) -> tuple[bool, str]:
    """
    Determine if email should be skipped to prevent email loops.

    Skips:
    - Emails from the system mailbox (INVOICE_MAILBOX)
    - System-generated invoice emails (Invoice: ... - GL ... pattern)
    - Replies to vendor registration emails

    Returns: (should_skip, reason)
    """
    sender = email.get("sender", {}).get("emailAddress", {}).get("address", "").lower()
    subject = email.get("subject", "")

    # Skip emails from the system mailbox (critical loop prevention)
    if sender == invoice_mailbox.lower():
        return True, f"sender is system mailbox ({sender})"

    # Skip system-generated invoice email patterns
    if re.match(r"^Invoice:\s+.+\s+-\s+GL\s+\d{4}$", subject):
        return True, f"system-generated invoice pattern ({subject})"

    # Skip replies to vendor registration emails
    if subject.lower().startswith("re:") and "vendor registration" in subject.lower():
        return True, f"reply to registration email ({subject})"

    return False, ""


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
            # Check if email should be skipped for loop prevention
            should_skip, reason = _should_skip_email(email, mailbox)
            if should_skip:
                logger.info(f"Skipping email {email['id']}: {reason}")
                graph.mark_as_read(mailbox, email["id"])
                continue

            if not email.get("hasAttachments"):
                logger.warning(f"Skipping email {email['id']} - no attachments")
                graph.mark_as_read(mailbox, email["id"])
                continue

            _process_email(email, graph, mailbox, blob_container, outQueueItem)
            graph.mark_as_read(mailbox, email["id"])
    except Exception as e:
        logger.error(f"MailIngest failed: {str(e)}")
        raise
