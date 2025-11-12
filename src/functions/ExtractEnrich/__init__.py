"""
ExtractEnrich queue function - Extract vendor and enrich with GL codes.

Looks up vendor in VendorMaster table. If found, enriches and queues for AP posting.
If unknown, emails requestor with vendor registration instructions and stops processing.
"""

import os
import logging
import json
import azure.functions as func
from azure.data.tables import TableServiceClient
from shared.models import RawMail, EnrichedInvoice
from shared.email_parser import extract_domain
from shared.graph_client import GraphAPIClient
from shared.email_composer import compose_unknown_vendor_email

logger = logging.getLogger(__name__)


def _send_vendor_registration_email(
    vendor_domain: str, transaction_id: str, sender: str
):
    """Send vendor registration instructions to requestor."""
    api_url = os.environ.get(
        "FUNCTION_APP_URL", "https://func-invoice-agent.azurewebsites.net"
    )
    subject, body = compose_unknown_vendor_email(vendor_domain, transaction_id, api_url)
    graph = GraphAPIClient()
    graph.send_email(
        from_address=os.environ["INVOICE_MAILBOX"],
        to_address=sender,
        subject=subject,
        body=body,
        is_html=True,
    )
    logger.warning(
        f"Unknown vendor: {vendor_domain} - sent registration email to {sender}"
    )


def main(msg: func.QueueMessage, toPost: func.Out[str]):
    """Extract vendor and enrich invoice data."""
    try:
        raw_mail = RawMail.model_validate_json(msg.get_body().decode())
        vendor_domain = extract_domain(raw_mail.sender)
        table_client = TableServiceClient.from_connection_string(
            os.environ["AzureWebJobsStorage"]
        ).get_table_client("VendorMaster")

        try:
            vendor = table_client.get_entity(
                partition_key="Vendor", row_key=vendor_domain
            )
            enriched = EnrichedInvoice(
                id=raw_mail.id,
                vendor_name=vendor["VendorName"],
                expense_dept=vendor["ExpenseDept"],
                gl_code=vendor["GLCode"],
                allocation_schedule=vendor["AllocationScheduleNumber"],
                billing_party=vendor["BillingParty"],
                blob_url=raw_mail.blob_url,
                status="enriched",
            )
            toPost.set(enriched.model_dump_json())
            logger.info(f"Enriched: {raw_mail.id} - {vendor['VendorName']}")
        except Exception:
            _send_vendor_registration_email(vendor_domain, raw_mail.id, raw_mail.sender)
    except Exception as e:
        logger.error(f"ExtractEnrich failed: {str(e)}")
        raise
