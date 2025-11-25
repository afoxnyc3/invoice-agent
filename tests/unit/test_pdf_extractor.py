"""
Unit tests for PDF vendor extraction using pdfplumber + Azure OpenAI.

Tests PDF download, text extraction, LLM-based vendor identification,
and error handling with mocked dependencies.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, mock_open
from shared.pdf_extractor import (
    extract_vendor_from_pdf,
    _download_pdf_from_blob,
    _extract_text_from_pdf,
    _extract_vendor_with_llm,
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
    def test_end_to_end_success(
        self, mock_download, mock_extract_text, mock_extract_llm, mock_environment
    ):
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
    def test_end_to_end_no_text_extracted(
        self, mock_download, mock_extract_text, mock_environment
    ):
        """Test graceful handling when no text can be extracted."""
        mock_download.return_value = b"%PDF-1.4"
        mock_extract_text.return_value = None  # No text extracted

        blob_url = "https://storage.blob.core.windows.net/invoices/tx123/scanned.pdf"
        result = extract_vendor_from_pdf(blob_url)

        assert result is None

    @patch("shared.pdf_extractor._extract_vendor_with_llm")
    @patch("shared.pdf_extractor._extract_text_from_pdf")
    @patch("shared.pdf_extractor._download_pdf_from_blob")
    def test_end_to_end_llm_fails(
        self, mock_download, mock_extract_text, mock_extract_llm, mock_environment
    ):
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
    def test_end_to_end_partial_failure(
        self, mock_download, mock_extract_text, mock_extract_llm, mock_environment
    ):
        """Test that partial failures don't crash the system."""
        mock_download.return_value = b"%PDF-1.4"
        mock_extract_text.side_effect = Exception("pdfplumber error")

        blob_url = "https://storage.blob.core.windows.net/invoices/tx123/invoice.pdf"
        result = extract_vendor_from_pdf(blob_url)

        # Should handle exception and return None gracefully
        assert result is None
        # Should not call LLM since text extraction failed
        mock_extract_llm.assert_not_called()
