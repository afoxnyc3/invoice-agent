"""Unit tests for shared deduplication module."""

from unittest.mock import patch, MagicMock


class TestDeduplication:
    """Test suite for deduplication utilities."""

    @patch.dict(
        "os.environ",
        {"AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test"},
    )
    @patch("shared.deduplication.TableServiceClient")
    def test_returns_true_when_message_exists(self, mock_table_service):
        """Test duplicate detection when message exists in table."""
        from shared.deduplication import is_message_already_processed

        mock_table_client = MagicMock()
        mock_table_service.from_connection_string.return_value.get_table_client.return_value = mock_table_client
        mock_table_client.query_entities.return_value = [
            {
                "RowKey": "01JCK3Q7H8",
                "ProcessedAt": "2025-11-24T10:05:00Z",
                "Status": "unknown",
            }
        ]

        result = is_message_already_processed("AAMkAGNmOTU5YzI5...")

        assert result is True
        mock_table_client.query_entities.assert_called_once()

    @patch.dict(
        "os.environ",
        {"AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test"},
    )
    @patch("shared.deduplication.TableServiceClient")
    def test_returns_false_when_message_not_found(self, mock_table_service):
        """Test no duplicate when message not in table."""
        from shared.deduplication import is_message_already_processed

        mock_table_client = MagicMock()
        mock_table_service.from_connection_string.return_value.get_table_client.return_value = mock_table_client
        mock_table_client.query_entities.return_value = []

        result = is_message_already_processed("new-message-id")

        assert result is False

    def test_returns_false_when_message_id_is_none(self):
        """Test returns False when message_id is None."""
        from shared.deduplication import is_message_already_processed

        assert is_message_already_processed(None) is False

    def test_returns_false_when_message_id_is_empty(self):
        """Test returns False when message_id is empty string."""
        from shared.deduplication import is_message_already_processed

        assert is_message_already_processed("") is False

    @patch.dict(
        "os.environ",
        {"AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test"},
    )
    @patch("shared.deduplication.TableServiceClient")
    def test_fails_open_on_error(self, mock_table_service):
        """Test graceful handling of errors (fail open)."""
        from shared.deduplication import is_message_already_processed

        mock_table_service.from_connection_string.side_effect = Exception("Connection failed")

        result = is_message_already_processed("some-message-id")

        assert result is False  # Fail open - process anyway

    @patch.dict(
        "os.environ",
        {"AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test"},
    )
    @patch("shared.deduplication.TableServiceClient")
    def test_detects_processed_status(self, mock_table_service):
        """Test that processed status invoices are detected as duplicates."""
        from shared.deduplication import is_message_already_processed

        mock_table_client = MagicMock()
        mock_table_service.from_connection_string.return_value.get_table_client.return_value = mock_table_client
        mock_table_client.query_entities.return_value = [
            {
                "RowKey": "01JCK3Q7H8",
                "ProcessedAt": "2025-11-24T10:05:00Z",
                "Status": "processed",
            }
        ]

        result = is_message_already_processed("processed-message-id")

        assert result is True

    @patch.dict(
        "os.environ",
        {"AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test"},
    )
    @patch("shared.deduplication.TableServiceClient")
    def test_detects_unknown_status(self, mock_table_service):
        """Test that unknown status invoices are also detected as duplicates."""
        from shared.deduplication import is_message_already_processed

        mock_table_client = MagicMock()
        mock_table_service.from_connection_string.return_value.get_table_client.return_value = mock_table_client
        mock_table_client.query_entities.return_value = [
            {
                "RowKey": "01JCK3Q7H8",
                "ProcessedAt": "2025-11-24T10:05:00Z",
                "Status": "unknown",
            }
        ]

        result = is_message_already_processed("unknown-vendor-message-id")

        assert result is True

    @patch.dict(
        "os.environ",
        {"AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test"},
    )
    @patch("shared.deduplication.TableServiceClient")
    def test_queries_invoice_transactions_table(self, mock_table_service):
        """Test that correct table is queried."""
        from shared.deduplication import is_message_already_processed

        mock_table_client = MagicMock()
        mock_table_service.from_connection_string.return_value.get_table_client.return_value = mock_table_client
        mock_table_client.query_entities.return_value = []

        is_message_already_processed("test-message-id")

        mock_table_service.from_connection_string.return_value.get_table_client.assert_called_with(
            "InvoiceTransactions"
        )

    @patch.dict(
        "os.environ",
        {"AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test"},
    )
    @patch("shared.deduplication.TableServiceClient")
    def test_query_filter_uses_original_message_id(self, mock_table_service):
        """Test that query filter uses the correct message ID."""
        from shared.deduplication import is_message_already_processed

        mock_table_client = MagicMock()
        mock_table_service.from_connection_string.return_value.get_table_client.return_value = mock_table_client
        mock_table_client.query_entities.return_value = []

        is_message_already_processed("my-unique-message-id")

        mock_table_client.query_entities.assert_called_once_with("OriginalMessageId eq 'my-unique-message-id'")


class TestInvoiceHashGeneration:
    """Test suite for invoice hash generation."""

    def test_generates_consistent_hash(self):
        """Test that same inputs produce same hash."""
        from shared.deduplication import generate_invoice_hash

        hash1 = generate_invoice_hash("Microsoft", "invoice@microsoft.com", "2025-11-25T10:00:00Z")
        hash2 = generate_invoice_hash("Microsoft", "invoice@microsoft.com", "2025-11-25T10:00:00Z")

        assert hash1 == hash2
        assert len(hash1) == 32  # MD5 hash length

    def test_normalizes_vendor_name(self):
        """Test that vendor name is normalized (lowercase, underscores)."""
        from shared.deduplication import generate_invoice_hash

        hash1 = generate_invoice_hash("Microsoft", "test@test.com", "2025-11-25T10:00:00Z")
        hash2 = generate_invoice_hash("MICROSOFT", "test@test.com", "2025-11-25T10:00:00Z")
        hash3 = generate_invoice_hash("  microsoft  ", "test@test.com", "2025-11-25T10:00:00Z")

        assert hash1 == hash2
        assert hash1 == hash3

    def test_normalizes_sender_email(self):
        """Test that sender email is normalized (lowercase)."""
        from shared.deduplication import generate_invoice_hash

        hash1 = generate_invoice_hash("Vendor", "Test@Example.com", "2025-11-25T10:00:00Z")
        hash2 = generate_invoice_hash("Vendor", "test@example.com", "2025-11-25T10:00:00Z")

        assert hash1 == hash2

    def test_uses_date_portion_only(self):
        """Test that only date portion of timestamp is used."""
        from shared.deduplication import generate_invoice_hash

        # Same date, different times should produce same hash
        hash1 = generate_invoice_hash("Vendor", "test@test.com", "2025-11-25T10:00:00Z")
        hash2 = generate_invoice_hash("Vendor", "test@test.com", "2025-11-25T23:59:59Z")

        assert hash1 == hash2

    def test_different_dates_produce_different_hash(self):
        """Test that different dates produce different hashes."""
        from shared.deduplication import generate_invoice_hash

        hash1 = generate_invoice_hash("Vendor", "test@test.com", "2025-11-25T10:00:00Z")
        hash2 = generate_invoice_hash("Vendor", "test@test.com", "2025-11-26T10:00:00Z")

        assert hash1 != hash2

    def test_different_vendors_produce_different_hash(self):
        """Test that different vendors produce different hashes."""
        from shared.deduplication import generate_invoice_hash

        hash1 = generate_invoice_hash("Microsoft", "test@test.com", "2025-11-25T10:00:00Z")
        hash2 = generate_invoice_hash("Amazon", "test@test.com", "2025-11-25T10:00:00Z")

        assert hash1 != hash2


class TestCheckDuplicateInvoice:
    """Test suite for duplicate invoice checking."""

    @patch.dict(
        "os.environ",
        {"AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test"},
    )
    @patch("shared.deduplication.TableServiceClient")
    def test_returns_none_when_no_duplicate(self, mock_table_service):
        """Test returns None when no duplicate found."""
        from shared.deduplication import check_duplicate_invoice

        mock_table_client = MagicMock()
        mock_table_service.from_connection_string.return_value.get_table_client.return_value = mock_table_client
        mock_table_client.query_entities.return_value = []

        result = check_duplicate_invoice("abc123")

        assert result is None

    @patch.dict(
        "os.environ",
        {"AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test"},
    )
    @patch("shared.deduplication.TableServiceClient")
    def test_returns_existing_transaction_when_duplicate(self, mock_table_service):
        """Test returns existing transaction when duplicate found."""
        from shared.deduplication import check_duplicate_invoice
        from datetime import datetime

        mock_table_client = MagicMock()
        mock_table_service.from_connection_string.return_value.get_table_client.return_value = mock_table_client

        # Use current month's partition key so date filtering passes
        current_partition = datetime.utcnow().strftime("%Y%m")
        existing_tx = {
            "PartitionKey": current_partition,
            "RowKey": "01JCK3Q7H8",
            "InvoiceHash": "abc123",
            "ProcessedAt": "2025-11-24T10:05:00Z",
        }
        mock_table_client.query_entities.return_value = [existing_tx]

        result = check_duplicate_invoice("abc123")

        assert result is not None
        assert result["RowKey"] == "01JCK3Q7H8"

    @patch.dict(
        "os.environ",
        {"AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test"},
    )
    @patch("shared.deduplication.TableServiceClient")
    def test_fails_open_on_error(self, mock_table_service):
        """Test graceful handling of errors (fail open)."""
        from shared.deduplication import check_duplicate_invoice

        mock_table_service.from_connection_string.side_effect = Exception("Connection failed")

        result = check_duplicate_invoice("abc123")

        assert result is None  # Fail open - return None to proceed

    @patch.dict(
        "os.environ",
        {"AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test"},
    )
    @patch("shared.deduplication.TableServiceClient")
    def test_queries_by_invoice_hash(self, mock_table_service):
        """Test that query uses InvoiceHash filter."""
        from shared.deduplication import check_duplicate_invoice

        mock_table_client = MagicMock()
        mock_table_service.from_connection_string.return_value.get_table_client.return_value = mock_table_client
        mock_table_client.query_entities.return_value = []

        check_duplicate_invoice("my-hash-value")

        mock_table_client.query_entities.assert_called_once_with("InvoiceHash eq 'my-hash-value'")
