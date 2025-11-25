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
