"""
Unit tests for Notify queue function.
"""

from unittest.mock import Mock, patch
import azure.functions as func
from Notify import main


class TestNotify:
    """Test suite for Notify function."""

    @patch.dict("os.environ", {"TEAMS_WEBHOOK_URL": "https://outlook.office.com/webhook/test"})
    @patch("Notify.requests")
    def test_notify_success_message(self, mock_requests):
        """Test posting success notification to Teams."""
        # Mock requests.post
        mock_response = Mock()
        mock_response.status_code = 200
        mock_requests.post.return_value = mock_response

        # Mock queue message
        notification_json = """
        {
            "type": "success",
            "message": "Processed: Adobe Inc - GL 6100",
            "details": {
                "vendor": "Adobe Inc",
                "gl_code": "6100",
                "transaction_id": "01JCK3Q7H8ZVXN3BARC9GWAEZM"
            }
        }
        """
        msg = Mock(spec=func.QueueMessage)
        msg.get_body.return_value = notification_json.encode()

        # Execute function
        main(msg)

        # Assertions
        mock_requests.post.assert_called_once()
        call_args = mock_requests.post.call_args
        assert call_args[0][0] == "https://outlook.office.com/webhook/test"

        # Verify MessageCard structure
        card_data = call_args[1]["json"]
        assert card_data["@type"] == "MessageCard"
        assert card_data["@context"] == "http://schema.org/extensions"
        assert card_data["themeColor"] == "00FF00"  # Green for success
        assert card_data["summary"] == "Processed: Adobe Inc - GL 6100"

        # Verify sections
        assert "sections" in card_data
        assert len(card_data["sections"]) == 1
        section = card_data["sections"][0]
        assert "✅ Processed: Adobe Inc - GL 6100" in section["activityTitle"]

        # Verify facts
        facts = section["facts"]
        assert len(facts) == 3

    @patch.dict("os.environ", {"TEAMS_WEBHOOK_URL": "https://outlook.office.com/webhook/test"})
    @patch("Notify.requests")
    def test_notify_unknown_vendor_message(self, mock_requests):
        """Test posting unknown vendor notification to Teams."""
        # Mock requests.post
        mock_response = Mock()
        mock_response.status_code = 200
        mock_requests.post.return_value = mock_response

        notification_json = """
        {
            "type": "unknown",
            "message": "Unknown vendor: test-vendor.com",
            "details": {
                "vendor_domain": "test-vendor.com",
                "transaction_id": "01JCK3Q7H8ZVXN3BARC9GWAEZM"
            }
        }
        """
        msg = Mock(spec=func.QueueMessage)
        msg.get_body.return_value = notification_json.encode()

        # Execute function
        main(msg)

        # Verify warning color for unknown vendor (orange hex)
        card_data = mock_requests.post.call_args[1]["json"]
        assert card_data["themeColor"] == "FFA500"  # Orange for warning

    @patch.dict("os.environ", {"TEAMS_WEBHOOK_URL": "https://outlook.office.com/webhook/test"})
    @patch("Notify.requests")
    def test_notify_error_message(self, mock_requests):
        """Test posting error notification to Teams."""
        # Mock requests.post
        mock_response = Mock()
        mock_response.status_code = 200
        mock_requests.post.return_value = mock_response

        notification_json = """
        {
            "type": "error",
            "message": "Failed to process invoice",
            "details": {
                "error": "Graph API connection failed",
                "transaction_id": "01JCK3Q7H8ZVXN3BARC9GWAEZM"
            }
        }
        """
        msg = Mock(spec=func.QueueMessage)
        msg.get_body.return_value = notification_json.encode()

        # Execute function
        main(msg)

        # Verify red color for error
        card_data = mock_requests.post.call_args[1]["json"]
        assert card_data["themeColor"] == "FF0000"  # Red for error

    @patch.dict("os.environ", {})  # No webhook URL configured
    @patch("Notify.requests")
    def test_notify_no_webhook_configured(self, mock_requests):
        """Test handling when webhook URL is not configured."""
        notification_json = """
        {
            "type": "success",
            "message": "Test",
            "details": {"transaction_id": "TEST123"}
        }
        """
        msg = Mock(spec=func.QueueMessage)
        msg.get_body.return_value = notification_json.encode()

        # Execute function - should not raise exception
        main(msg)

        # Verify no webhook call was made
        mock_requests.post.assert_not_called()

    @patch.dict("os.environ", {"TEAMS_WEBHOOK_URL": "https://outlook.office.com/webhook/test"})
    @patch("Notify.requests")
    def test_notify_webhook_failure(self, mock_requests):
        """Test handling of webhook POST failures (non-critical)."""
        # Mock requests.post to raise exception
        mock_requests.post.side_effect = Exception("Webhook unavailable")

        notification_json = """
        {
            "type": "success",
            "message": "Test",
            "details": {"transaction_id": "TEST123"}
        }
        """
        msg = Mock(spec=func.QueueMessage)
        msg.get_body.return_value = notification_json.encode()

        # Execute function - should not raise exception (non-critical)
        main(msg)

        # Verify it attempted to post
        mock_requests.post.assert_called_once()

    @patch.dict("os.environ", {"TEAMS_WEBHOOK_URL": "https://outlook.office.com/webhook/test"})
    @patch("Notify.requests")
    def test_notify_card_facts_formatting(self, mock_requests):
        """Test that notification details are correctly formatted as facts."""
        # Mock requests.post
        mock_response = Mock()
        mock_response.status_code = 200
        mock_requests.post.return_value = mock_response

        notification_json = """
        {
            "type": "success",
            "message": "Test message",
            "details": {
                "transaction_id": "TEST123",
                "vendor": "Test Vendor",
                "gl_code": "6100",
                "department": "IT",
                "amount": "1250.00"
            }
        }
        """
        msg = Mock(spec=func.QueueMessage)
        msg.get_body.return_value = notification_json.encode()

        # Execute function
        main(msg)

        # Verify facts are properly formatted in MessageCard
        card_data = mock_requests.post.call_args[1]["json"]
        section = card_data["sections"][0]
        facts = section["facts"]
        assert len(facts) == 5  # transaction_id + vendor + gl_code + department + amount

        # Verify fact names are titlecased with underscores replaced by spaces
        # (MessageCard uses "name" not "title")
        fact_names = [f["name"] for f in facts]
        assert "Vendor" in fact_names
        assert "Gl Code" in fact_names
        assert "Department" in fact_names
        assert "Transaction Id" in fact_names

    def test_notify_invalid_message(self):
        """Test handling of invalid queue message."""
        # Invalid JSON message
        msg = Mock(spec=func.QueueMessage)
        msg.get_body.return_value = b"invalid json{"

        # Execute function - should not raise exception (non-critical)
        main(msg)
