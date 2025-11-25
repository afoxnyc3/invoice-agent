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
from typing import Optional
from urllib.parse import unquote
import pdfplumber
from openai import AzureOpenAI
from azure.storage.blob import BlobServiceClient

logger = logging.getLogger(__name__)


def _download_pdf_from_blob(blob_url: str) -> bytes:
    """
    Download PDF bytes from Azure Blob Storage.

    Args:
        blob_url: Full URL to blob (e.g., https://storage.../invoices/txn123/invoice.pdf)

    Returns:
        bytes: PDF file contents

    Raises:
        Exception: If download fails
    """
    try:
        # Extract blob name from URL
        # URL format: https://{account}.blob.core.windows.net/{container}/{blob_name}
        parts = blob_url.split("/")
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

        vendor_name = response.choices[0].message.content.strip()

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
