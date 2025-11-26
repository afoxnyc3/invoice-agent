"""
Unit tests for PDF vendor extraction using pdfplumber + Azure OpenAI.

Tests PDF download, text extraction, LLM-based vendor identification,
and error handling with mocked dependencies.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
from shared.pdf_extractor import (
    extract_vendor_from_pdf,
    _download_pdf_from_blob,
    _extract_text_from_pdf,
    _extract_vendor_with_llm,
    _extract_amount_from_text,
    _extract_currency_from_text,
    _extract_due_date_from_text,
    _extract_payment_terms_from_text,
    _parse_date_string,
    extract_invoice_fields_from_pdf,
)


# =============================================================================
# PDF DOWNLOAD TESTS
# =============================================================================


class TestDownloadPDFFromBlob:
    """Test PDF download from Azure Blob Storage."""

    @patch("shared.pdf_extractor.BlobServiceClient")
    def test_download_success(self, mock_blob_service, mock_environment):
        """Test successful PDF download from blob storage."""
        # Mock blob download
        mock_blob_data = b"%PDF-1.4 fake pdf content"
        mock_download = MagicMock()
        mock_download.readall.return_value = mock_blob_data

        mock_blob_client = MagicMock()
        mock_blob_client.download_blob.return_value = mock_download

        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob_client

        mock_service = MagicMock()
        mock_service.get_blob_client.return_value = mock_blob_client
        mock_blob_service.from_connection_string.return_value = mock_service

        # Test download
        blob_url = "https://storage.blob.core.windows.net/invoices/tx123/invoice.pdf"
        result = _download_pdf_from_blob(blob_url)

        assert result == mock_blob_data
        mock_blob_service.from_connection_string.assert_called_once()

    @patch("shared.pdf_extractor.BlobServiceClient")
    def test_download_failure(self, mock_blob_service, mock_environment):
        """Test PDF download failure handling."""
        mock_blob_service.from_connection_string.side_effect = Exception("Blob not found")

        blob_url = "https://storage.blob.core.windows.net/invoices/invalid/file.pdf"

        with pytest.raises(Exception, match="Blob not found"):
            _download_pdf_from_blob(blob_url)


# =============================================================================
# PDF TEXT EXTRACTION TESTS
# =============================================================================


class TestExtractTextFromPDF:
    """Test PDF text extraction using pdfplumber."""

    @patch("shared.pdf_extractor.pdfplumber")
    def test_extract_text_success(self, mock_pdfplumber):
        """Test successful text extraction from PDF."""
        # Mock PDF with text content
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Invoice\nAdobe Inc\nAmount: $1000"

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = Mock(return_value=mock_pdf)
        mock_pdf.__exit__ = Mock(return_value=False)

        mock_pdfplumber.open.return_value = mock_pdf

        # Test extraction
        pdf_bytes = b"%PDF-1.4 fake content"
        result = _extract_text_from_pdf(pdf_bytes)

        assert result == "Invoice\nAdobe Inc\nAmount: $1000"
        mock_page.extract_text.assert_called_once()

    @patch("shared.pdf_extractor.pdfplumber")
    def test_extract_text_max_chars(self, mock_pdfplumber):
        """Test text extraction respects max_chars limit."""
        # Mock PDF with long text
        long_text = "A" * 5000
        mock_page = MagicMock()
        mock_page.extract_text.return_value = long_text

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = Mock(return_value=mock_pdf)
        mock_pdf.__exit__ = Mock(return_value=False)

        mock_pdfplumber.open.return_value = mock_pdf

        # Test with max_chars=100
        pdf_bytes = b"%PDF-1.4"
        result = _extract_text_from_pdf(pdf_bytes, max_chars=100)

        assert len(result) == 100
        assert result == "A" * 100

    @patch("shared.pdf_extractor.pdfplumber")
    def test_extract_text_empty_pdf(self, mock_pdfplumber):
        """Test extraction from PDF with no pages."""
        mock_pdf = MagicMock()
        mock_pdf.pages = []
        mock_pdf.__enter__ = Mock(return_value=mock_pdf)
        mock_pdf.__exit__ = Mock(return_value=False)

        mock_pdfplumber.open.return_value = mock_pdf

        pdf_bytes = b"%PDF-1.4"
        result = _extract_text_from_pdf(pdf_bytes)

        assert result is None

    @patch("shared.pdf_extractor.pdfplumber")
    def test_extract_text_no_text(self, mock_pdfplumber):
        """Test extraction from PDF with no extractable text."""
        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = Mock(return_value=mock_pdf)
        mock_pdf.__exit__ = Mock(return_value=False)

        mock_pdfplumber.open.return_value = mock_pdf

        pdf_bytes = b"%PDF-1.4"
        result = _extract_text_from_pdf(pdf_bytes)

        assert result is None

    @patch("shared.pdf_extractor.pdfplumber")
    def test_extract_text_exception(self, mock_pdfplumber):
        """Test extraction handles exceptions gracefully."""
        mock_pdfplumber.open.side_effect = Exception("Corrupt PDF")

        pdf_bytes = b"INVALID PDF"
        result = _extract_text_from_pdf(pdf_bytes)

        assert result is None


# =============================================================================
# LLM VENDOR EXTRACTION TESTS
# =============================================================================


class TestExtractVendorWithLLM:
    """Test Azure OpenAI vendor name extraction."""

    @patch("shared.pdf_extractor.AzureOpenAI")
    def test_llm_extraction_success(self, mock_openai_client, mock_environment):
        """Test successful vendor extraction using Azure OpenAI."""
        # Mock OpenAI response
        mock_message = MagicMock()
        mock_message.content = "Adobe Inc"

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_client.return_value = mock_client

        # Test extraction
        pdf_text = "Invoice from Adobe Inc\nAmount: $1000"
        result = _extract_vendor_with_llm(pdf_text)

        assert result == "Adobe Inc"
        mock_client.chat.completions.create.assert_called_once()

    @patch("shared.pdf_extractor.AzureOpenAI")
    def test_llm_extraction_unknown_vendor(self, mock_openai_client, mock_environment):
        """Test LLM returns UNKNOWN when vendor not found."""
        mock_message = MagicMock()
        mock_message.content = "UNKNOWN"

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_client.return_value = mock_client

        pdf_text = "Some random text without vendor"
        result = _extract_vendor_with_llm(pdf_text)

        assert result is None

    @patch("shared.pdf_extractor.AzureOpenAI")
    def test_llm_extraction_empty_response(self, mock_openai_client, mock_environment):
        """Test LLM returns empty response."""
        mock_message = MagicMock()
        mock_message.content = ""

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_client.return_value = mock_client

        result = _extract_vendor_with_llm("some text")

        assert result is None

    def test_llm_extraction_missing_env_vars(self, monkeypatch):
        """Test LLM extraction fails gracefully without Azure OpenAI config."""
        # Remove Azure OpenAI environment variables
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
        monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)

        result = _extract_vendor_with_llm("Invoice from Adobe")

        assert result is None

    @patch("shared.pdf_extractor.AzureOpenAI")
    def test_llm_extraction_api_error(self, mock_openai_client, mock_environment):
        """Test LLM extraction handles API errors gracefully."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API rate limit exceeded")
        mock_openai_client.return_value = mock_client

        result = _extract_vendor_with_llm("Invoice text")

        assert result is None


# =============================================================================
# END-TO-END EXTRACTION TESTS
# =============================================================================


class TestExtractVendorFromPDF:
    """Test complete PDF vendor extraction flow."""

    @patch("shared.pdf_extractor._extract_vendor_with_llm")
    @patch("shared.pdf_extractor._extract_text_from_pdf")
    @patch("shared.pdf_extractor._download_pdf_from_blob")
    def test_end_to_end_success(self, mock_download, mock_extract_text, mock_extract_llm, mock_environment):
        """Test successful end-to-end vendor extraction."""
        # Mock each step
        mock_download.return_value = b"%PDF-1.4"
        mock_extract_text.return_value = "Invoice from Adobe Inc"
        mock_extract_llm.return_value = "Adobe Inc"

        blob_url = "https://storage.blob.core.windows.net/invoices/tx123/invoice.pdf"
        result = extract_vendor_from_pdf(blob_url)

        assert result == "Adobe Inc"
        mock_download.assert_called_once_with(blob_url)
        mock_extract_text.assert_called_once()
        mock_extract_llm.assert_called_once_with("Invoice from Adobe Inc")

    @patch("shared.pdf_extractor._extract_text_from_pdf")
    @patch("shared.pdf_extractor._download_pdf_from_blob")
    def test_end_to_end_no_text_extracted(self, mock_download, mock_extract_text, mock_environment):
        """Test graceful handling when no text can be extracted."""
        mock_download.return_value = b"%PDF-1.4"
        mock_extract_text.return_value = None  # No text extracted

        blob_url = "https://storage.blob.core.windows.net/invoices/tx123/scanned.pdf"
        result = extract_vendor_from_pdf(blob_url)

        assert result is None

    @patch("shared.pdf_extractor._extract_vendor_with_llm")
    @patch("shared.pdf_extractor._extract_text_from_pdf")
    @patch("shared.pdf_extractor._download_pdf_from_blob")
    def test_end_to_end_llm_fails(self, mock_download, mock_extract_text, mock_extract_llm, mock_environment):
        """Test graceful handling when LLM extraction fails."""
        mock_download.return_value = b"%PDF-1.4"
        mock_extract_text.return_value = "Invoice text"
        mock_extract_llm.return_value = None  # LLM couldn't find vendor

        blob_url = "https://storage.blob.core.windows.net/invoices/tx123/invoice.pdf"
        result = extract_vendor_from_pdf(blob_url)

        assert result is None

    @patch("shared.pdf_extractor._download_pdf_from_blob")
    def test_end_to_end_download_fails(self, mock_download, mock_environment):
        """Test graceful handling when PDF download fails."""
        mock_download.side_effect = Exception("Blob not found")

        blob_url = "https://storage.blob.core.windows.net/invoices/invalid/file.pdf"
        result = extract_vendor_from_pdf(blob_url)

        assert result is None  # Should not raise, returns None

    @patch("shared.pdf_extractor._extract_vendor_with_llm")
    @patch("shared.pdf_extractor._extract_text_from_pdf")
    @patch("shared.pdf_extractor._download_pdf_from_blob")
    def test_end_to_end_partial_failure(self, mock_download, mock_extract_text, mock_extract_llm, mock_environment):
        """Test that partial failures don't crash the system."""
        mock_download.return_value = b"%PDF-1.4"
        mock_extract_text.side_effect = Exception("pdfplumber error")

        blob_url = "https://storage.blob.core.windows.net/invoices/tx123/invoice.pdf"
        result = extract_vendor_from_pdf(blob_url)

        # Should handle exception and return None gracefully
        assert result is None
        # Should not call LLM since text extraction failed
        mock_extract_llm.assert_not_called()


# =============================================================================
# INVOICE AMOUNT EXTRACTION TESTS
# =============================================================================


class TestExtractAmountFromText:
    """Test invoice amount extraction from text."""

    def test_extract_amount_with_total_label(self):
        """Test amount extraction with 'Total:' label."""
        text = "Invoice Details\nTotal: $1,234.56\nThank you"
        result = _extract_amount_from_text(text)
        assert result == 1234.56

    def test_extract_amount_with_amount_label(self):
        """Test amount extraction with 'Amount:' label."""
        text = "Amount: $999.99"
        result = _extract_amount_from_text(text)
        assert result == 999.99

    def test_extract_amount_with_due_label(self):
        """Test amount extraction with 'Due:' label."""
        text = "Amount Due: 5000.00"
        result = _extract_amount_from_text(text)
        assert result == 5000.00

    def test_extract_amount_with_currency_prefix(self):
        """Test amount extraction with currency prefix."""
        text = "Total Amount: USD 1500.50"
        result = _extract_amount_from_text(text)
        assert result == 1500.50

    def test_extract_amount_no_decimals(self):
        """Test amount extraction without decimal places."""
        text = "Total: $1000"
        result = _extract_amount_from_text(text)
        assert result == 1000.0

    def test_extract_amount_invalid_range(self):
        """Test amount extraction rejects out-of-range values."""
        text = "Total: $99999999999.99"
        result = _extract_amount_from_text(text)
        assert result is None

    def test_extract_amount_empty_text(self):
        """Test amount extraction with empty text."""
        result = _extract_amount_from_text("")
        assert result is None


# =============================================================================
# CURRENCY EXTRACTION TESTS
# =============================================================================


class TestExtractCurrencyFromText:
    """Test currency extraction from text."""

    def test_extract_currency_usd(self):
        """Test USD currency extraction."""
        text = "Total: USD 1000.00"
        result = _extract_currency_from_text(text)
        assert result == "USD"

    def test_extract_currency_eur(self):
        """Test EUR currency extraction."""
        text = "Amount: EUR 500.00"
        result = _extract_currency_from_text(text)
        assert result == "EUR"

    def test_extract_currency_cad(self):
        """Test CAD currency extraction."""
        text = "Total: CAD 750.00"
        result = _extract_currency_from_text(text)
        assert result == "CAD"

    def test_extract_currency_dollar_sign(self):
        """Test currency extraction with dollar sign defaults to USD."""
        text = "Total: $1000.00"
        result = _extract_currency_from_text(text)
        assert result == "USD"

    def test_extract_currency_default(self):
        """Test currency extraction defaults to USD when not found."""
        text = "Invoice total 1000"
        result = _extract_currency_from_text(text)
        assert result == "USD"


# =============================================================================
# DATE PARSING TESTS
# =============================================================================


class TestParseDateString:
    """Test date string parsing."""

    def test_parse_iso_date(self):
        """Test parsing ISO 8601 date format."""
        result = _parse_date_string("2024-01-15")
        assert result == datetime(2024, 1, 15)

    def test_parse_us_date_format(self):
        """Test parsing US date format (MM/DD/YYYY)."""
        result = _parse_date_string("01/15/2024")
        assert result == datetime(2024, 1, 15)

    def test_parse_long_month_name(self):
        """Test parsing date with full month name."""
        result = _parse_date_string("January 15, 2024")
        assert result == datetime(2024, 1, 15)

    def test_parse_short_month_name(self):
        """Test parsing date with abbreviated month name."""
        result = _parse_date_string("Jan 15, 2024")
        assert result == datetime(2024, 1, 15)

    def test_parse_invalid_date(self):
        """Test parsing invalid date returns None."""
        result = _parse_date_string("not a date")
        assert result is None


# =============================================================================
# DUE DATE EXTRACTION TESTS
# =============================================================================


class TestExtractDueDateFromText:
    """Test due date extraction from text."""

    def test_extract_due_date_iso_format(self):
        """Test due date extraction with ISO format."""
        text = "Invoice\nDue Date: 2024-12-31\nThank you"
        result = _extract_due_date_from_text(text)
        assert result == "2024-12-31T00:00:00"

    def test_extract_due_date_us_format(self):
        """Test due date extraction with US format."""
        text = "Payment Due: 12/31/2024"
        result = _extract_due_date_from_text(text)
        assert result == "2024-12-31T00:00:00"

    def test_extract_due_date_long_format(self):
        """Test due date extraction with long format."""
        text = "Due by: December 31, 2024"
        result = _extract_due_date_from_text(text)
        assert result == "2024-12-31T00:00:00"

    def test_extract_due_date_fallback(self):
        """Test due date falls back to received_date + 30 days."""
        text = "No due date in this text"
        received = "2024-01-01T00:00:00Z"
        result = _extract_due_date_from_text(text, received)
        expected = (datetime(2024, 1, 1) + timedelta(days=30)).isoformat()
        assert result == expected


# =============================================================================
# PAYMENT TERMS EXTRACTION TESTS
# =============================================================================


class TestExtractPaymentTermsFromText:
    """Test payment terms extraction from text."""

    def test_extract_payment_terms_net_30(self):
        """Test extraction of Net 30 payment terms."""
        text = "Payment Terms: Net 30"
        result = _extract_payment_terms_from_text(text)
        assert result == "Net 30"

    def test_extract_payment_terms_net_60(self):
        """Test extraction of Net 60 payment terms."""
        text = "Terms: Net 60 days"
        result = _extract_payment_terms_from_text(text)
        assert result == "Net 60"

    def test_extract_payment_terms_due_on_receipt(self):
        """Test extraction of Due on receipt payment terms."""
        text = "Payment: Due on receipt"
        result = _extract_payment_terms_from_text(text)
        assert result == "Due On Receipt"

    def test_extract_payment_terms_cod(self):
        """Test extraction of COD payment terms."""
        text = "Terms: COD"
        result = _extract_payment_terms_from_text(text)
        assert result == "Cod"

    def test_extract_payment_terms_default(self):
        """Test default payment terms when not found."""
        text = "No payment terms in this text"
        result = _extract_payment_terms_from_text(text)
        assert result == "Net 30"


# =============================================================================
# END-TO-END INVOICE FIELDS EXTRACTION TESTS
# =============================================================================


class TestExtractInvoiceFieldsFromPDF:
    """Test complete invoice fields extraction flow."""

    @patch("shared.pdf_extractor._extract_text_from_pdf")
    @patch("shared.pdf_extractor._download_pdf_from_blob")
    def test_extract_all_fields_success(self, mock_download, mock_extract_text, mock_environment):
        """Test successful extraction of all invoice fields."""
        mock_download.return_value = b"%PDF-1.4"
        mock_extract_text.return_value = """
        Invoice #12345
        Adobe Inc
        Total: $1,250.50
        Due Date: 2024-12-31
        Payment Terms: Net 30
        """

        blob_url = "https://storage.blob.core.windows.net/invoices/tx123/invoice.pdf"
        result = extract_invoice_fields_from_pdf(blob_url)

        assert result["invoice_amount"] == 1250.50
        assert result["currency"] == "USD"
        assert result["due_date"] == "2024-12-31T00:00:00"
        assert result["payment_terms"] == "Net 30"
        assert result["confidence"]["amount"] == 1.0

    @patch("shared.pdf_extractor._extract_text_from_pdf")
    @patch("shared.pdf_extractor._download_pdf_from_blob")
    def test_extract_fields_with_eur_currency(self, mock_download, mock_extract_text, mock_environment):
        """Test extraction with EUR currency."""
        mock_download.return_value = b"%PDF-1.4"
        mock_extract_text.return_value = "Total: EUR 500.00\nDue Date: 2024-12-31"

        blob_url = "https://storage.blob.core.windows.net/invoices/tx123/invoice.pdf"
        result = extract_invoice_fields_from_pdf(blob_url)

        assert result["invoice_amount"] == 500.00
        assert result["currency"] == "EUR"

    @patch("shared.pdf_extractor._extract_text_from_pdf")
    @patch("shared.pdf_extractor._download_pdf_from_blob")
    def test_extract_fields_no_text_uses_defaults(self, mock_download, mock_extract_text, mock_environment):
        """Test extraction uses defaults when no text extracted."""
        mock_download.return_value = b"%PDF-1.4"
        mock_extract_text.return_value = None

        blob_url = "https://storage.blob.core.windows.net/invoices/tx123/invoice.pdf"
        received = "2024-01-01T00:00:00Z"
        result = extract_invoice_fields_from_pdf(blob_url, received)

        assert result["invoice_amount"] is None
        assert result["currency"] == "USD"
        assert result["payment_terms"] == "Net 30"
        assert result["confidence"]["amount"] == 0.0

    @patch("shared.pdf_extractor._download_pdf_from_blob")
    def test_extract_fields_exception_returns_defaults(self, mock_download, mock_environment):
        """Test extraction returns defaults on exception."""
        mock_download.side_effect = Exception("Blob not found")

        blob_url = "https://storage.blob.core.windows.net/invoices/invalid/file.pdf"
        result = extract_invoice_fields_from_pdf(blob_url)

        assert result["invoice_amount"] is None
        assert result["currency"] == "USD"
        assert result["payment_terms"] == "Net 30"
