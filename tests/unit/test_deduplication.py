"""Unit tests for shared deduplication module."""

from unittest.mock import patch, MagicMock


class TestDeduplication:
    """Test suite for deduplication utilities."""

    @patch("shared.deduplication.config")
    def test_returns_true_when_processed_message_exists(self, mock_config):
        """Test duplicate detection when processed message exists in table."""
        from shared.deduplication import is_message_already_processed

        mock_table_client = MagicMock()
        mock_config.get_table_client.return_value = mock_table_client
        mock_table_client.query_entities.return_value = [
            {
                "RowKey": "01JCK3Q7H8",
                "ProcessedAt": "2025-11-24T10:05:00Z",
                "Status": "processed",
            }
        ]

        result = is_message_already_processed("AAMkAGNmOTU5YzI5...")

        assert result is True
        mock_table_client.query_entities.assert_called_once()

    @patch("shared.deduplication.config")
    def test_returns_false_when_message_not_found(self, mock_config):
        """Test no duplicate when message not in table."""
        from shared.deduplication import is_message_already_processed

        mock_table_client = MagicMock()
        mock_config.get_table_client.return_value = mock_table_client
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

    @patch("shared.deduplication.config")
    def test_fails_open_on_error(self, mock_config):
        """Test graceful handling of errors (fail open)."""
        from shared.deduplication import is_message_already_processed

        mock_table_client = MagicMock()
        mock_config.get_table_client.return_value = mock_table_client
        mock_table_client.query_entities.side_effect = Exception("Connection failed")

        result = is_message_already_processed("some-message-id")

        assert result is False  # Fail open - process anyway

    @patch("shared.deduplication.config")
    def test_detects_processed_status(self, mock_config):
        """Test that processed status invoices are detected as duplicates."""
        from shared.deduplication import is_message_already_processed

        mock_table_client = MagicMock()
        mock_config.get_table_client.return_value = mock_table_client
        mock_table_client.query_entities.return_value = [
            {
                "RowKey": "01JCK3Q7H8",
                "ProcessedAt": "2025-11-24T10:05:00Z",
                "Status": "processed",
            }
        ]

        result = is_message_already_processed("processed-message-id")

        assert result is True

    @patch("shared.deduplication.config")
    def test_allows_unknown_status_to_proceed(self, mock_config):
        """Test that unknown status invoices are NOT blocked - allows notifications.

        Unknown vendor invoices need to proceed to PostToAP for Teams notification.
        Only Status='processed' should block as a duplicate.
        """
        from shared.deduplication import is_message_already_processed

        mock_table_client = MagicMock()
        mock_config.get_table_client.return_value = mock_table_client
        # Query for Status='processed' returns empty (only unknown exists)
        mock_table_client.query_entities.return_value = []

        result = is_message_already_processed("unknown-vendor-message-id")

        assert result is False  # Unknown status does NOT block processing

    @patch("shared.deduplication.config")
    def test_queries_invoice_transactions_table(self, mock_config):
        """Test that correct table is queried."""
        from shared.deduplication import is_message_already_processed

        mock_table_client = MagicMock()
        mock_config.get_table_client.return_value = mock_table_client
        mock_table_client.query_entities.return_value = []

        is_message_already_processed("test-message-id")

        mock_config.get_table_client.assert_called_with("InvoiceTransactions")

    @patch("shared.deduplication.config")
    def test_query_filter_uses_message_id_and_processed_status(self, mock_config):
        """Test that query filter uses message ID and Status='processed' filter."""
        from shared.deduplication import is_message_already_processed

        mock_table_client = MagicMock()
        mock_config.get_table_client.return_value = mock_table_client
        mock_table_client.query_entities.return_value = []

        is_message_already_processed("my-unique-message-id")

        mock_table_client.query_entities.assert_called_once_with(
            "OriginalMessageId eq 'my-unique-message-id' and Status eq 'processed'"
        )


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

    @patch("shared.deduplication.config")
    def test_returns_none_when_no_duplicate(self, mock_config):
        """Test returns None when no duplicate found."""
        from shared.deduplication import check_duplicate_invoice

        mock_table_client = MagicMock()
        mock_config.get_table_client.return_value = mock_table_client
        mock_table_client.query_entities.return_value = []

        result = check_duplicate_invoice("abc123")

        assert result is None

    @patch("shared.deduplication.config")
    def test_returns_existing_transaction_when_duplicate(self, mock_config):
        """Test returns existing transaction when duplicate found."""
        from shared.deduplication import check_duplicate_invoice
        from datetime import datetime

        mock_table_client = MagicMock()
        mock_config.get_table_client.return_value = mock_table_client

        # Use dynamic ProcessedAt within lookback period (now uses ProcessedAt, not partition key)
        recent_date = datetime.utcnow().isoformat() + "Z"
        existing_tx = {
            "PartitionKey": datetime.utcnow().strftime("%Y%m"),
            "RowKey": "01JCK3Q7H8",
            "InvoiceHash": "abc123",
            "ProcessedAt": recent_date,
        }
        mock_table_client.query_entities.return_value = [existing_tx]

        result = check_duplicate_invoice("abc123")

        assert result is not None
        assert result["RowKey"] == "01JCK3Q7H8"

    @patch("shared.deduplication.config")
    def test_filters_by_processed_at_not_partition_key(self, mock_config):
        """Test that date filtering uses ProcessedAt timestamp, not partition key.

        Regression test for P1 bug: Records in partial months at lookback
        boundary were incorrectly excluded when using partition key.
        """
        from shared.deduplication import check_duplicate_invoice
        from datetime import datetime, timedelta

        mock_table_client = MagicMock()
        mock_config.get_table_client.return_value = mock_table_client

        # Create record with ProcessedAt 30 days ago (within 90-day lookback)
        # but partition key that might be at month boundary
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        existing_tx = {
            "PartitionKey": thirty_days_ago.strftime("%Y%m"),
            "RowKey": "01BOUNDARY",
            "InvoiceHash": "boundary-hash",
            "ProcessedAt": thirty_days_ago.isoformat() + "Z",
        }
        mock_table_client.query_entities.return_value = [existing_tx]

        result = check_duplicate_invoice("boundary-hash")

        # Should find duplicate based on ProcessedAt, not partition key
        assert result is not None
        assert result["RowKey"] == "01BOUNDARY"

    @patch("shared.deduplication.config")
    def test_excludes_records_outside_lookback_period(self, mock_config):
        """Test that records outside lookback period are excluded."""
        from shared.deduplication import check_duplicate_invoice
        from datetime import datetime, timedelta

        mock_table_client = MagicMock()
        mock_config.get_table_client.return_value = mock_table_client

        # Create record with ProcessedAt 100 days ago (outside 90-day lookback)
        old_date = datetime.utcnow() - timedelta(days=100)
        old_tx = {
            "PartitionKey": old_date.strftime("%Y%m"),
            "RowKey": "01OLD",
            "InvoiceHash": "old-hash",
            "ProcessedAt": old_date.isoformat() + "Z",
        }
        mock_table_client.query_entities.return_value = [old_tx]

        result = check_duplicate_invoice("old-hash")

        # Should NOT find duplicate - outside lookback period
        assert result is None

    @patch("shared.deduplication.config")
    def test_fails_open_on_error(self, mock_config):
        """Test graceful handling of errors (fail open)."""
        from shared.deduplication import check_duplicate_invoice

        mock_table_client = MagicMock()
        mock_config.get_table_client.return_value = mock_table_client
        mock_table_client.query_entities.side_effect = Exception("Connection failed")

        result = check_duplicate_invoice("abc123")

        assert result is None  # Fail open - return None to proceed

    @patch("shared.deduplication.config")
    def test_queries_by_invoice_hash(self, mock_config):
        """Test that query uses InvoiceHash filter."""
        from shared.deduplication import check_duplicate_invoice

        mock_table_client = MagicMock()
        mock_config.get_table_client.return_value = mock_table_client
        mock_table_client.query_entities.return_value = []

        check_duplicate_invoice("my-hash-value")

        mock_table_client.query_entities.assert_called_once_with("InvoiceHash eq 'my-hash-value'")
