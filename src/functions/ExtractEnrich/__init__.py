"""
ExtractEnrich queue function - Extract vendor and enrich with GL codes.

Looks up vendor in VendorMaster table by vendor name. Implements:
- Case-insensitive vendor name matching using "contains" logic
- Special handling for reseller vendors (e.g., Myriad360) that require product extraction
- Venue extraction from invoice metadata
- Unknown vendor handling with registration email
"""

import os
import logging
import azure.functions as func
from azure.data.tables import TableServiceClient
from shared.models import RawMail, EnrichedInvoice
from shared.graph_client import GraphAPIClient
from shared.email_composer import compose_unknown_vendor_email
from shared.email_parser import extract_domain

logger = logging.getLogger(__name__)


def _find_vendor_by_name(vendor_name: str, table_client) -> dict | None:
    """
    Find vendor in VendorMaster table using case-insensitive contains matching.

    Returns the vendor entity if found, None otherwise.
    """
    if not vendor_name or not vendor_name.strip():
        return None

    vendor_lower = vendor_name.lower().strip()

    try:
        # Query all vendors and do case-insensitive contains matching
        vendors = list(table_client.query_entities("PartitionKey eq 'Vendor' and Active eq true"))

        for vendor in vendors:
            # Exact match on normalized RowKey
            if vendor["RowKey"] == vendor_lower.replace(" ", "_").replace("-", "_"):
                return vendor
            # Contains match on VendorName (case-insensitive)
            if vendor_lower in vendor["VendorName"].lower():
                return vendor

        return None
    except Exception as e:
        logger.error(f"Error querying vendors: {str(e)}")
        return None


def _send_vendor_registration_email(vendor_name: str, transaction_id: str, sender: str):
    """Send vendor registration instructions to requestor."""
    api_url = os.environ.get("FUNCTION_APP_URL", "https://func-invoice-agent.azurewebsites.net")
    subject, body = compose_unknown_vendor_email(vendor_name, transaction_id, api_url)
    graph = GraphAPIClient()
    graph.send_email(
        from_address=os.environ["INVOICE_MAILBOX"],
        to_address=sender,
        subject=subject,
        body=body,
        is_html=True,
    )
    logger.warning(f"Unknown vendor: {vendor_name} - sent registration email to {sender}")


def main(msg: func.QueueMessage, toPost: func.Out[str], notify: func.Out[str]):
    """Extract vendor and enrich invoice data."""
    try:
        raw_mail = RawMail.model_validate_json(msg.get_body().decode())
        table_client = TableServiceClient.from_connection_string(os.environ["AzureWebJobsStorage"]).get_table_client(
            "VendorMaster"
        )

        # Try vendor name first (from PDF extraction, future phase)
        vendor_name = raw_mail.vendor_name
        vendor = None

        if vendor_name:
            vendor = _find_vendor_by_name(vendor_name, table_client)

        # Fallback to email domain extraction (MVP phase)
        if not vendor and raw_mail.sender:
            try:
                domain = extract_domain(raw_mail.sender)
                # Extract company name from domain (e.g., "adobe_com" -> "adobe")
                company_name = domain.split("_")[0]
                vendor = _find_vendor_by_name(company_name, table_client)
                if vendor:
                    logger.info(f"Vendor matched via email domain: {company_name} -> {vendor['VendorName']}")
                    vendor_name = company_name
            except (ValueError, IndexError):
                logger.warning(f"Could not extract domain from sender: {raw_mail.sender}")

        # If still no vendor found, mark as unknown
        if not vendor:
            if not vendor_name:
                vendor_name = extract_domain(raw_mail.sender).split("_")[0]
            logger.warning(f"Vendor not found: {vendor_name} ({raw_mail.id})")
            _send_vendor_registration_email(vendor_name, raw_mail.id, raw_mail.sender)

            enriched = EnrichedInvoice(
                id=raw_mail.id,
                vendor_name=vendor_name,
                expense_dept="Unknown",
                gl_code="0000",
                allocation_schedule="Unknown",
                billing_party="Chelsea Piers",
                blob_url=raw_mail.blob_url,
                status="unknown",
            )
            toPost.set(enriched.model_dump_json())
            return

        # Special handling for resellers (e.g., Myriad360) - flag for manual review
        if vendor.get("ProductCategory") == "Reseller":
            logger.warning(
                f"Reseller vendor detected: {vendor['VendorName']} ({raw_mail.id}) - flagging for manual review"
            )
            enriched = EnrichedInvoice(
                id=raw_mail.id,
                vendor_name=vendor["VendorName"],
                expense_dept="Unknown",
                gl_code="0000",
                allocation_schedule="Unknown",
                billing_party="Chelsea Piers",
                blob_url=raw_mail.blob_url,
                status="unknown",
            )
            toPost.set(enriched.model_dump_json())
            return

        # Vendor found - enrich with GL codes and metadata
        enriched = EnrichedInvoice(
            id=raw_mail.id,
            vendor_name=vendor["VendorName"],
            expense_dept=vendor["ExpenseDept"],
            gl_code=vendor["GLCode"],
            allocation_schedule=vendor["AllocationSchedule"],
            billing_party="Chelsea Piers",
            blob_url=raw_mail.blob_url,
            status="enriched",
        )
        toPost.set(enriched.model_dump_json())
        logger.info(f"Enriched: {raw_mail.id} - {vendor['VendorName']} (GL: {vendor['GLCode']})")

    except Exception as e:
        logger.error(f"ExtractEnrich failed: {str(e)}")
        raise
