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

        # Verify Adaptive Card structure for Power Automate
        card_data = call_args[1]["json"]
        assert card_data["type"] == "message"
        assert "attachments" in card_data
        assert len(card_data["attachments"]) == 1

        attachment = card_data["attachments"][0]
        assert attachment["contentType"] == "application/vnd.microsoft.card.adaptive"
        content = attachment["content"]
        assert content["type"] == "AdaptiveCard"

        # Verify body elements
        body = content["body"]
        text_block = body[0]
        assert text_block["type"] == "TextBlock"
        assert "✅ Processed: Adobe Inc - GL 6100" in text_block["text"]
        assert text_block["color"] == "good"

        # Verify facts
        fact_set = body[1]
        assert fact_set["type"] == "FactSet"
        assert len(fact_set["facts"]) == 3

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

        # Verify warning color for unknown vendor
        card_data = mock_requests.post.call_args[1]["json"]
        content = card_data["attachments"][0]["content"]
        text_block = content["body"][0]
        assert text_block["color"] == "warning"

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

        # Verify attention color for error
        card_data = mock_requests.post.call_args[1]["json"]
        content = card_data["attachments"][0]["content"]
        text_block = content["body"][0]
        assert text_block["color"] == "attention"

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

        # Verify facts are properly formatted in Adaptive Card
        card_data = mock_requests.post.call_args[1]["json"]
        content = card_data["attachments"][0]["content"]
        fact_set = content["body"][1]
        facts = fact_set["facts"]
        assert len(facts) == 5  # transaction_id + vendor + gl_code + department + amount

        # Verify fact titles are titlecased with underscores replaced by spaces
        # (Adaptive Card uses "title" not "name")
        fact_titles = [f["title"] for f in facts]
        assert "Vendor" in fact_titles
        assert "Gl Code" in fact_titles
        assert "Department" in fact_titles
        assert "Transaction Id" in fact_titles

    def test_notify_invalid_message(self):
        """Test handling of invalid queue message."""
        # Invalid JSON message
        msg = Mock(spec=func.QueueMessage)
        msg.get_body.return_value = b"invalid json{"

        # Execute function - should not raise exception (non-critical)
        main(msg)
