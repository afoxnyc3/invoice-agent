"""
PDF text extraction and vendor name identification using Azure OpenAI.

This module provides intelligent vendor extraction from invoice PDFs by:
1. Downloading PDF from blob storage
2. Extracting text from first page using pdfplumber
3. Using Azure OpenAI (gpt-4o-mini) to identify vendor name
4. Returning normalized vendor name for lookup

Cost: ~$0.001 per invoice (~$1.50/month at 50 invoices/day)
Latency: ~500ms per PDF (extraction + API call)
"""

import os
import logging
import io
import re
from typing import Optional, Dict, Any
from urllib.parse import unquote
from datetime import datetime, timedelta
import pdfplumber
from openai import AzureOpenAI
from azure.storage.blob import BlobServiceClient

logger = logging.getLogger(__name__)


def _download_pdf_from_blob(blob_url: str) -> bytes:
    """
    Download PDF bytes from Azure Blob Storage.

    Supports both production and local development (Azurite) storage URLs:
    - Production: https://{account}.blob.core.windows.net/{container}/{blob_name}
    - Dev: http://127.0.0.1:10000/devstoreaccount1/{container}/{blob_name}

    Args:
        blob_url: Full URL to blob

    Returns:
        bytes: PDF file contents

    Raises:
        Exception: If download fails
    """
    try:
        # Extract container and blob name from URL
        parts = blob_url.split("/")

        # Handle dev storage vs production storage URL formats
        if len(parts) > 3 and parts[3] == "devstoreaccount1":
            # Dev storage: http://127.0.0.1:10000/devstoreaccount1/{container}/{blob}
            container = parts[4]
            blob_name = "/".join(parts[5:])
        else:
            # Production: https://{account}.blob.core.windows.net/{container}/{blob}
            container = parts[3]
            blob_name = "/".join(parts[4:])

        # Decode URL-encoded characters (e.g., %20 -> space) to prevent double-encoding
        blob_name = unquote(blob_name)

        # Download using connection string
        blob_service = BlobServiceClient.from_connection_string(os.environ["AzureWebJobsStorage"])
        blob_client = blob_service.get_blob_client(container=container, blob=blob_name)
        return blob_client.download_blob().readall()

    except Exception as e:
        logger.error(f"Failed to download PDF from {blob_url}: {str(e)}")
        raise


def _extract_text_from_pdf(pdf_bytes: bytes, max_chars: int = 2000) -> Optional[str]:
    """
    Extract text from first page of PDF using pdfplumber.

    Args:
        pdf_bytes: PDF file contents as bytes
        max_chars: Maximum characters to extract (optimize cost)

    Returns:
        str: Extracted text (up to max_chars), or None if extraction fails
    """
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            if not pdf.pages:
                logger.warning("PDF has no pages")
                return None

            # Extract text from first page only (vendor name usually at top)
            first_page = pdf.pages[0]
            text = first_page.extract_text()

            if not text or not text.strip():
                logger.warning("PDF text extraction returned empty string")
                return None

            # Limit text length to optimize API cost/latency
            return text[:max_chars]

    except Exception as e:
        logger.error(f"Failed to extract text from PDF: {str(e)}")
        return None


def _extract_vendor_with_llm(pdf_text: str) -> Optional[str]:
    """
    Use Azure OpenAI to extract vendor name from PDF text.

    Args:
        pdf_text: Extracted text from PDF

    Returns:
        str: Vendor name, or None if extraction fails

    Raises:
        Exception: If Azure OpenAI API call fails
    """
    try:
        # Initialize Azure OpenAI client
        client = AzureOpenAI(
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-01"),
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        )

        # Call GPT-4o-mini with vendor extraction prompt
        response = client.chat.completions.create(
            model=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini"),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a vendor name extractor. Extract the vendor/company name from this invoice text. "
                        "Return ONLY the company name, nothing else. Be concise. "
                        "Examples: 'Adobe Inc', 'Microsoft', 'Amazon Web Services'. "
                        "If you cannot find a vendor name, return 'UNKNOWN'."
                    ),
                },
                {"role": "user", "content": pdf_text},
            ],
            max_tokens=20,
            temperature=0,  # Deterministic output
        )

        content = response.choices[0].message.content
        if not content:
            logger.warning("LLM returned empty content")
            return None
        vendor_name = content.strip()

        # Validate response
        if not vendor_name or vendor_name.upper() == "UNKNOWN":
            logger.warning("LLM could not extract vendor name from PDF")
            return None

        logger.info(f"LLM extracted vendor: {vendor_name}")
        return vendor_name

    except KeyError as e:
        logger.error(f"Missing Azure OpenAI environment variable: {str(e)}")
        logger.error("Required: AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT (optional)")
        return None
    except Exception as e:
        logger.error(f"Azure OpenAI API call failed: {str(e)}")
        return None


def extract_vendor_from_pdf(blob_url: str) -> Optional[str]:
    """
    Extract vendor name from invoice PDF using pdfplumber + Azure OpenAI.

    This is the main entry point for PDF vendor extraction. It:
    1. Downloads PDF from blob storage
    2. Extracts text from first page
    3. Uses Azure OpenAI to identify vendor name
    4. Returns vendor name for lookup in VendorMaster table

    Args:
        blob_url: Full URL to invoice PDF in blob storage

    Returns:
        str: Vendor name extracted from PDF, or None if extraction fails

    Example:
        >>> extract_vendor_from_pdf("https://storage.../invoices/tx123/invoice.pdf")
        "Adobe Inc"
    """
    try:
        logger.info(f"Starting PDF vendor extraction for {blob_url}")

        # Step 1: Download PDF from blob storage
        pdf_bytes = _download_pdf_from_blob(blob_url)
        logger.debug(f"Downloaded PDF: {len(pdf_bytes)} bytes")

        # Step 2: Extract text from first page
        pdf_text = _extract_text_from_pdf(pdf_bytes, max_chars=2000)
        if not pdf_text:
            logger.warning("PDF text extraction failed - no text extracted")
            return None

        logger.debug(f"Extracted {len(pdf_text)} characters from PDF")

        # Step 3: Use LLM to extract vendor name
        vendor_name = _extract_vendor_with_llm(pdf_text)

        if vendor_name:
            logger.info(f"Successfully extracted vendor from PDF: {vendor_name}")
        else:
            logger.warning("Failed to extract vendor from PDF")

        return vendor_name

    except Exception as e:
        logger.error(f"PDF vendor extraction failed for {blob_url}: {str(e)}")
        # Don't raise - gracefully degrade to email domain extraction
        return None


def _extract_amount_from_text(text: str) -> Optional[float]:
    """Extract invoice amount from text using regex patterns."""
    if not text:
        return None

    patterns = [
        r"(?:total|amount|due|balance)[:\s]+\$?\s*([\d,]+\.?\d*)",
        r"\$\s*([\d,]+\.\d{2})",
        r"(?:USD|EUR|CAD)\s*([\d,]+\.?\d*)",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            try:
                amount_str = matches[0].replace(",", "")
                amount = float(amount_str)
                if 0 < amount < 10_000_000:
                    return amount
            except (ValueError, IndexError):
                continue
    return None


def _extract_currency_from_text(text: str) -> str:
    """Extract currency code from text."""
    if not text:
        return "USD"

    # Try currency codes first
    currency_match = re.search(r"\b(USD|EUR|CAD)\b", text, re.IGNORECASE)
    if currency_match:
        return currency_match.group(1).upper()

    # Check for dollar sign (default to USD)
    if "$" in text:
        return "USD"

    return "USD"


def _parse_date_string(date_str: str) -> Optional[datetime]:
    """Parse date string in various formats."""
    date_formats = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
    ]

    for fmt in date_formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def _extract_due_date_from_text(text: str, fallback_date: str | None = None) -> Optional[str]:
    """Extract due date from text or use fallback."""
    if not text:
        return _calculate_fallback_due_date(fallback_date)

    patterns = [
        r"(?:due date|payment due|due by)[:\s]+(\d{4}-\d{2}-\d{2})",
        r"(?:due date|payment due|due by)[:\s]+(\d{1,2}/\d{1,2}/\d{4})",
        r"(?:due date|payment due|due by)[:\s]+([A-Za-z]+\s+\d{1,2},?\s+\d{4})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            parsed = _parse_date_string(match.group(1))
            if parsed:
                return parsed.isoformat()
    return _calculate_fallback_due_date(fallback_date)


def _calculate_fallback_due_date(received_date: str | None = None) -> Optional[str]:
    """Calculate due date as received_date + 30 days."""
    try:
        if received_date:
            base_date = datetime.fromisoformat(received_date.replace("Z", ""))
        else:
            base_date = datetime.now()
        due_date = base_date + timedelta(days=30)
        return due_date.isoformat()
    except (ValueError, AttributeError):
        return None


def _extract_payment_terms_from_text(text: str) -> str:
    """Extract payment terms from text."""
    if not text:
        return "Net 30"

    patterns = [
        r"\b(Net\s+\d+)\b",
        r"\b(Due\s+on\s+receipt)\b",
        r"\b(COD)\b",
        r"\b(Prepaid)\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).title()
    return "Net 30"


def extract_invoice_fields_from_pdf(blob_url: str, received_at: str | None = None) -> Dict[str, Any]:
    """
    Extract invoice fields from PDF (amount, currency, due date, payment terms).

    This function extracts structured invoice fields using regex patterns on
    the PDF text. Returns a dict with extracted values and confidence scores.

    Args:
        blob_url: Full URL to invoice PDF in blob storage
        received_at: ISO 8601 timestamp of when email received (for fallback due date)

    Returns:
        dict: Extracted fields with confidence scores
            {
                'invoice_amount': float or None,
                'currency': str,
                'due_date': str (ISO 8601) or None,
                'payment_terms': str,
                'confidence': {'amount': float, 'due_date': float, 'payment_terms': float}
            }
    """
    try:
        logger.info(f"Starting invoice field extraction for {blob_url}")

        pdf_bytes = _download_pdf_from_blob(blob_url)
        pdf_text = _extract_text_from_pdf(pdf_bytes, max_chars=4000)

        if not pdf_text:
            logger.warning("No text extracted from PDF - using defaults")
            return _default_invoice_fields(received_at)

        amount = _extract_amount_from_text(pdf_text)
        currency = _extract_currency_from_text(pdf_text)
        due_date = _extract_due_date_from_text(pdf_text, received_at)
        payment_terms = _extract_payment_terms_from_text(pdf_text)

        confidence = {
            "amount": 1.0 if amount else 0.0,
            "due_date": 1.0 if "due date" in pdf_text.lower() else 0.5,
            "payment_terms": 1.0 if re.search(r"\bnet\s+\d+\b", pdf_text, re.I) else 0.5,
        }

        logger.info(
            f"Extracted fields - Amount: {amount}, Currency: {currency}, Due: {due_date}, Terms: {payment_terms}"
        )
        logger.debug(f"Extraction confidence: {confidence}")

        return {
            "invoice_amount": amount,
            "currency": currency,
            "due_date": due_date,
            "payment_terms": payment_terms,
            "confidence": confidence,
        }

    except Exception as e:
        logger.error(f"Invoice field extraction failed: {str(e)}")
        return _default_invoice_fields(received_at)


def _default_invoice_fields(received_at: str | None = None) -> Dict[str, Any]:
    """Return default invoice fields when extraction fails."""
    return {
        "invoice_amount": None,
        "currency": "USD",
        "due_date": _calculate_fallback_due_date(received_at),
        "payment_terms": "Net 30",
        "confidence": {"amount": 0.0, "due_date": 0.0, "payment_terms": 0.0},
    }
