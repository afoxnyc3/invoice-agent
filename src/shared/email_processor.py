"""
Email processing utilities shared across functions.

Provides reusable functions for processing emails, downloading attachments,
and creating RawMail queue messages. Used by both MailIngest and
MailWebhookProcessor to ensure consistent processing logic.

Includes intelligent PDF vendor extraction using pdfplumber + Azure OpenAI.
"""

import logging
import base64
from typing import Dict, Any, Optional
import azure.functions as func
from azure.storage.blob import ContainerClient
from shared.graph_client import GraphAPIClient
from shared.ulid_generator import generate_ulid
from shared.models import RawMail
from shared.pdf_extractor import extract_vendor_from_pdf

logger = logging.getLogger(__name__)


def parse_webhook_resource(resource: str) -> tuple[str, str]:
    """
    Extract mailbox and message ID from webhook resource path.

    Args:
        resource: Graph resource path (e.g., "users/mailbox@company.com/messages/AAMkAD...")

    Returns:
        tuple: (mailbox, message_id)

    Raises:
        ValueError: If resource path is malformed
    """
    parts = resource.split("/")
    if len(parts) < 4 or parts[0] != "users" or parts[2] != "messages":
        raise ValueError(f"Invalid webhook resource path: {resource}")

    mailbox = parts[1]
    message_id = parts[3]

    if not mailbox or not message_id:
        raise ValueError(f"Missing mailbox or message_id in resource: {resource}")

    return mailbox, message_id


def process_email_attachments(
    email: Dict[str, Any],
    graph: GraphAPIClient,
    mailbox: str,
    blob_container: ContainerClient,
    queue_output: func.Out[str],
) -> int:
    """
    Process email attachments and queue RawMail messages.

    Downloads all attachments from an email to blob storage and creates
    a RawMail queue message for each attachment. This is the core email
    processing logic shared by MailIngest and MailWebhookProcessor.

    Args:
        email: Email object from Graph API
        graph: Graph API client
        mailbox: Mailbox email address
        blob_container: Blob container client
        queue_output: Azure Functions queue output binding

    Returns:
        int: Number of attachments processed

    Raises:
        Exception: If email processing fails
    """
    transaction_id = generate_ulid()
    message_id = email["id"]
    attachments = graph.get_attachments(mailbox, message_id)

    if not attachments:
        logger.warning(f"Email {message_id} has no attachments - skipping")
        return 0

    processed_count = 0
    for attachment in attachments:
        blob_name = f"{transaction_id}/{attachment['name']}"
        blob_client = blob_container.get_blob_client(blob_name)
        content = base64.b64decode(attachment["contentBytes"])
        blob_client.upload_blob(content, overwrite=True)

        # Extract vendor from PDF if attachment is PDF
        vendor_name: Optional[str] = None
        attachment_name = attachment["name"].lower()
        if attachment_name.endswith(".pdf"):
            try:
                vendor_name = extract_vendor_from_pdf(blob_client.url)
                if vendor_name:
                    logger.info(f"PDF extraction: {vendor_name} from {attachment['name']}")
                else:
                    logger.info(f"PDF extraction: no vendor found in {attachment['name']}")
            except Exception as e:
                # Don't fail processing if PDF extraction fails - fall back to email domain
                logger.warning(f"PDF extraction failed for {attachment['name']}: {str(e)}")

        raw_mail = RawMail(
            id=transaction_id,
            sender=email["sender"]["emailAddress"]["address"],
            subject=email["subject"],
            blob_url=blob_client.url,
            received_at=email["receivedDateTime"],
            original_message_id=message_id,
            vendor_name=vendor_name,  # Populated from PDF extraction, or None
        )
        queue_output.set(raw_mail.model_dump_json())
        logger.info(f"Queued: {transaction_id} from {raw_mail.sender}")
        processed_count += 1

    return processed_count


def should_skip_email(email: Dict[str, Any], invoice_mailbox: str) -> tuple[bool, str]:
    """
    Determine if email should be skipped to prevent email loops.

    Skips:
    - Emails from the system mailbox (INVOICE_MAILBOX)
    - System-generated invoice emails (Invoice: ... - GL ... pattern)
    - Replies to vendor registration emails

    Args:
        email: Email object from Graph API
        invoice_mailbox: System mailbox address to filter out

    Returns:
        tuple: (should_skip, reason)
    """
    import re

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
