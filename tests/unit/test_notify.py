"""
Unit tests for Notify queue function.
"""

import json
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

        # Verify message envelope with Adaptive Card in attachments
        # Now using data= with explicit JSON serialization to avoid chunked encoding
        payload = json.loads(call_args[1]["data"])
        assert payload["type"] == "message"
        assert len(payload["attachments"]) == 1
        assert payload["attachments"][0]["contentType"] == "application/vnd.microsoft.card.adaptive"
        assert payload["attachments"][0]["contentUrl"] is None

        card_data = payload["attachments"][0]["content"]
        assert card_data["type"] == "AdaptiveCard"
        assert card_data["$schema"] == "http://adaptivecards.io/schemas/adaptive-card.json"
        assert card_data["version"] == "1.4"

        # Verify body elements
        body = card_data["body"]
        text_block = body[0]
        assert text_block["type"] == "TextBlock"
        assert "✅ Processed: Adobe Inc - GL 6100" in text_block["text"]

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

        # Verify Adaptive Card wrapped in message envelope with warning emoji
        payload = json.loads(mock_requests.post.call_args[1]["data"])
        assert payload["type"] == "message"
        card_data = payload["attachments"][0]["content"]
        text_block = card_data["body"][0]
        assert "⚠️" in text_block["text"]

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

        # Verify Adaptive Card wrapped in message envelope with error emoji
        payload = json.loads(mock_requests.post.call_args[1]["data"])
        assert payload["type"] == "message"
        card_data = payload["attachments"][0]["content"]
        text_block = card_data["body"][0]
        assert "❌" in text_block["text"]

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
        payload = json.loads(mock_requests.post.call_args[1]["data"])
        assert payload["type"] == "message"
        card_data = payload["attachments"][0]["content"]
        fact_set = card_data["body"][1]
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

    @patch.dict("os.environ", {"TEAMS_WEBHOOK_URL": "https://outlook.office.com/webhook/test"})
    @patch("Notify.requests")
    @patch("Notify.logger")
    def test_notify_timeout_error(self, mock_logger, mock_requests):
        """Test handling of timeout errors with specific logging."""
        from requests.exceptions import Timeout

        mock_requests.post.side_effect = Timeout("Connection timed out")

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

        # Verify timeout-specific warning logged
        mock_logger.warning.assert_called()
        log_call = mock_logger.warning.call_args[0][0]
        assert "timeout" in log_call.lower()
        assert "success" in log_call  # notification type included

    @patch.dict("os.environ", {"TEAMS_WEBHOOK_URL": "https://outlook.office.com/webhook/test"})
    @patch("Notify.requests")
    @patch("Notify.logger")
    def test_notify_connection_error(self, mock_logger, mock_requests):
        """Test handling of connection errors with specific logging."""
        from requests.exceptions import ConnectionError

        mock_requests.post.side_effect = ConnectionError("Failed to connect")

        notification_json = """
        {
            "type": "error",
            "message": "Test error",
            "details": {"transaction_id": "TEST123"}
        }
        """
        msg = Mock(spec=func.QueueMessage)
        msg.get_body.return_value = notification_json.encode()

        # Execute function - should not raise exception
        main(msg)

        # Verify connection-specific warning logged
        mock_logger.warning.assert_called()
        log_call = mock_logger.warning.call_args[0][0]
        assert "connection" in log_call.lower()
        assert "error" in log_call  # notification type included

    @patch.dict("os.environ", {"TEAMS_WEBHOOK_URL": "https://outlook.office.com/webhook/test"})
    @patch("Notify.requests")
    @patch("Notify.logger")
    def test_notify_http_error_logs_response_body(self, mock_logger, mock_requests):
        """Test that HTTP errors log the response body for debugging."""
        from requests.exceptions import HTTPError

        # Create mock response with error details
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.ok = False
        mock_response.text = "Bad Request: Invalid JSON schema"
        mock_response.raise_for_status.side_effect = HTTPError("400 Client Error", response=mock_response)
        mock_requests.post.return_value = mock_response

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

        # Verify response body was logged (critical for debugging)
        warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
        combined_logs = " ".join(warning_calls)
        assert "400" in combined_logs
        assert "Bad Request" in combined_logs or "Invalid JSON" in combined_logs

    @patch.dict("os.environ", {"TEAMS_WEBHOOK_URL": "https://outlook.office.com/webhook/test"})
    @patch("Notify.requests")
    def test_notify_success_logs_status_code(self, mock_requests):
        """Test that successful posts log the status code."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_requests.post.return_value = mock_response

        notification_json = """
        {
            "type": "success",
            "message": "Test",
            "details": {"transaction_id": "TEST123"}
        }
        """
        msg = Mock(spec=func.QueueMessage)
        msg.get_body.return_value = notification_json.encode()

        # Execute function
        with patch("Notify.logger") as mock_logger:
            main(msg)

            # Verify success log includes status code
            mock_logger.info.assert_called()
            log_call = mock_logger.info.call_args[0][0]
            assert "200" in log_call
            assert "success" in log_call
