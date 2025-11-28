"""
Unit tests for MailWebhook HTTP function.

Tests cover:
- Validation handshake (subscription creation)
- Notification processing and queuing
- Security validation (clientState)
- Error handling paths
"""

import json
from unittest.mock import Mock, patch
import azure.functions as func

from MailWebhook import main


class TestMailWebhook:
    """Unit tests for MailWebhook HTTP function."""

    def test_validation_handshake_returns_decoded_token(self):
        """Test validation handshake returns URL-decoded token."""
        # URL-encoded token with special characters
        encoded_token = "abc%20def%2B123"
        req = func.HttpRequest(
            method="POST",
            url="/api/MailWebhook",
            params={"validationToken": encoded_token},
            body=b"",
        )
        mock_queue = Mock(spec=func.Out)

        response = main(req, mock_queue)

        assert response.status_code == 200
        assert response.get_body().decode() == "abc def+123"  # URL decoded
        assert response.mimetype == "text/plain"
        mock_queue.set.assert_not_called()

    @patch.dict("os.environ", {"GRAPH_CLIENT_STATE": "test-secret-state"})
    def test_invalid_client_state_rejection(self):
        """Test notification with invalid clientState is skipped."""
        req_body = {
            "value": [
                {
                    "subscriptionId": "sub-123",
                    "clientState": "wrong-state",
                    "changeType": "created",
                    "resource": "me/mailFolders('Inbox')/messages/msg-123",
                }
            ]
        }
        req = func.HttpRequest(
            method="POST",
            url="/api/MailWebhook",
            body=json.dumps(req_body).encode("utf-8"),
        )
        mock_queue = Mock(spec=func.Out)

        response = main(req, mock_queue)

        assert response.status_code == 202
        mock_queue.set.assert_not_called()  # Invalid state = not queued

    @patch.dict("os.environ", {"GRAPH_CLIENT_STATE": "test-secret-state"})
    @patch("MailWebhook.generate_ulid", return_value="01TESTULID000000000000000")
    def test_valid_notification_queuing(self, mock_ulid):
        """Test valid notification is queued with correct format."""
        req_body = {
            "value": [
                {
                    "subscriptionId": "sub-123",
                    "clientState": "test-secret-state",
                    "changeType": "created",
                    "resource": "me/mailFolders('Inbox')/messages/msg-456",
                }
            ]
        }
        req = func.HttpRequest(
            method="POST",
            url="/api/MailWebhook",
            body=json.dumps(req_body).encode("utf-8"),
        )
        queued_messages = []
        mock_queue = Mock(spec=func.Out)
        mock_queue.set = lambda msg: queued_messages.append(msg)

        response = main(req, mock_queue)

        assert response.status_code == 202
        assert len(queued_messages) == 1

        queued = json.loads(queued_messages[0])
        assert queued["id"] == "01TESTULID000000000000000"
        assert queued["type"] == "webhook"
        assert queued["subscription_id"] == "sub-123"
        assert queued["resource"] == "me/mailFolders('Inbox')/messages/msg-456"
        assert queued["change_type"] == "created"

    @patch.dict("os.environ", {"GRAPH_CLIENT_STATE": "test-secret-state"})
    @patch("MailWebhook.generate_ulid", side_effect=["ULID1", "ULID2", "ULID3"])
    def test_multiple_notifications_handling(self, mock_ulid):
        """Test multiple notifications are all queued."""
        req_body = {
            "value": [
                {
                    "subscriptionId": "sub-1",
                    "clientState": "test-secret-state",
                    "changeType": "created",
                    "resource": "messages/msg-1",
                },
                {
                    "subscriptionId": "sub-2",
                    "clientState": "test-secret-state",
                    "changeType": "created",
                    "resource": "messages/msg-2",
                },
                {
                    "subscriptionId": "sub-3",
                    "clientState": "test-secret-state",
                    "changeType": "updated",
                    "resource": "messages/msg-3",
                },
            ]
        }
        req = func.HttpRequest(
            method="POST",
            url="/api/MailWebhook",
            body=json.dumps(req_body).encode("utf-8"),
        )
        queued_messages = []
        mock_queue = Mock(spec=func.Out)
        mock_queue.set = lambda msg: queued_messages.append(msg)

        response = main(req, mock_queue)

        assert response.status_code == 202
        assert len(queued_messages) == 3

        # Verify each message has unique ID and correct data
        for i, msg in enumerate(queued_messages, 1):
            queued = json.loads(msg)
            assert queued["subscription_id"] == f"sub-{i}"
            assert queued["resource"] == f"messages/msg-{i}"

    @patch.dict("os.environ", {"GRAPH_CLIENT_STATE": "test-secret-state"})
    def test_empty_notifications_array(self):
        """Test empty notifications array returns 202."""
        req_body = {"value": []}
        req = func.HttpRequest(
            method="POST",
            url="/api/MailWebhook",
            body=json.dumps(req_body).encode("utf-8"),
        )
        mock_queue = Mock(spec=func.Out)

        response = main(req, mock_queue)

        assert response.status_code == 202
        mock_queue.set.assert_not_called()

    @patch.dict("os.environ", {"GRAPH_CLIENT_STATE": ""}, clear=False)
    def test_missing_graph_client_state_env_var(self):
        """Test missing GRAPH_CLIENT_STATE returns 500."""
        req_body = {
            "value": [
                {
                    "subscriptionId": "sub-123",
                    "clientState": "any-state",
                    "changeType": "created",
                    "resource": "messages/msg-123",
                }
            ]
        }
        req = func.HttpRequest(
            method="POST",
            url="/api/MailWebhook",
            body=json.dumps(req_body).encode("utf-8"),
        )
        mock_queue = Mock(spec=func.Out)

        response = main(req, mock_queue)

        assert response.status_code == 500
        mock_queue.set.assert_not_called()

    def test_malformed_json_handling(self):
        """Test malformed JSON returns 400."""
        req = func.HttpRequest(
            method="POST",
            url="/api/MailWebhook",
            body=b"not valid json {{{",
        )
        mock_queue = Mock(spec=func.Out)

        response = main(req, mock_queue)

        assert response.status_code == 400
        mock_queue.set.assert_not_called()

    @patch.dict("os.environ", {"GRAPH_CLIENT_STATE": "test-secret-state"})
    @patch("MailWebhook.generate_ulid", side_effect=Exception("ULID generation failed"))
    def test_exception_returns_500(self, mock_ulid):
        """Test unhandled exception returns 500."""
        req_body = {
            "value": [
                {
                    "subscriptionId": "sub-123",
                    "clientState": "test-secret-state",
                    "changeType": "created",
                    "resource": "messages/msg-123",
                }
            ]
        }
        req = func.HttpRequest(
            method="POST",
            url="/api/MailWebhook",
            body=json.dumps(req_body).encode("utf-8"),
        )
        mock_queue = Mock(spec=func.Out)

        response = main(req, mock_queue)

        assert response.status_code == 500

    @patch.dict("os.environ", {"GRAPH_CLIENT_STATE": "test-secret-state"})
    @patch("MailWebhook.generate_ulid", side_effect=["VALID1", "VALID2"])
    def test_mixed_valid_invalid_notifications(self, mock_ulid):
        """Test mix of valid/invalid clientState - only valid ones queued."""
        req_body = {
            "value": [
                {
                    "subscriptionId": "sub-valid-1",
                    "clientState": "test-secret-state",
                    "changeType": "created",
                    "resource": "messages/valid-1",
                },
                {
                    "subscriptionId": "sub-invalid",
                    "clientState": "wrong-state",
                    "changeType": "created",
                    "resource": "messages/invalid",
                },
                {
                    "subscriptionId": "sub-valid-2",
                    "clientState": "test-secret-state",
                    "changeType": "created",
                    "resource": "messages/valid-2",
                },
            ]
        }
        req = func.HttpRequest(
            method="POST",
            url="/api/MailWebhook",
            body=json.dumps(req_body).encode("utf-8"),
        )
        queued_messages = []
        mock_queue = Mock(spec=func.Out)
        mock_queue.set = lambda msg: queued_messages.append(msg)

        response = main(req, mock_queue)

        assert response.status_code == 202
        assert len(queued_messages) == 2  # Only valid ones

        # Verify only valid notifications queued
        resources = [json.loads(m)["resource"] for m in queued_messages]
        assert "messages/valid-1" in resources
        assert "messages/valid-2" in resources
        assert "messages/invalid" not in resources
