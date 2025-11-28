"""
Unit tests for MailWebhook HTTP function.

Tests cover:
- Validation handshake mode (Graph subscription verification)
- Notification processing mode (queueing for downstream)
- Client state validation (security)
- Invalid request handling
- Error cases
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
import azure.functions as func
from MailWebhook import main


# Common environment variables for tests
ENV_VARS = {
    "GRAPH_CLIENT_STATE": "test-client-state-secret",
    "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test",
}


def _create_http_request(
    method: str = "POST",
    params: dict = None,
    body: dict = None,
) -> Mock:
    """Create a mock HTTP request with given parameters."""
    req = Mock(spec=func.HttpRequest)
    req.method = method
    req.params = params or {}

    if body is not None:
        req.get_json.return_value = body
    else:
        req.get_json.side_effect = ValueError("No JSON body")

    return req


def _create_valid_notification(
    client_state: str = "test-client-state-secret",
) -> dict:
    """Create a valid Graph API notification payload."""
    return {
        "value": [
            {
                "subscriptionId": "sub-123",
                "clientState": client_state,
                "changeType": "created",
                "resource": "users/invoices@example.com/messages/msg-456",
                "subscriptionExpirationDateTime": "2024-11-24T10:00:00Z",
            }
        ]
    }


class TestMailWebhookValidation:
    """Test suite for validation handshake mode."""

    @patch.dict("os.environ", ENV_VARS)
    def test_validation_token_returned(self):
        """Test that validation token is returned during subscription setup."""
        req = _create_http_request(params={"validationToken": "test-token-12345"})
        mock_queue = Mock(spec=func.Out)

        response = main(req, mock_queue)

        assert response.status_code == 200
        assert response.get_body().decode() == "test-token-12345"
        assert response.mimetype == "text/plain"
        mock_queue.set.assert_not_called()

    @patch.dict("os.environ", ENV_VARS)
    def test_validation_token_url_decoded(self):
        """Test that URL-encoded validation token is decoded."""
        req = _create_http_request(params={"validationToken": "test%20token%2B123"})
        mock_queue = Mock(spec=func.Out)

        response = main(req, mock_queue)

        assert response.status_code == 200
        assert response.get_body().decode() == "test token+123"

    @patch.dict("os.environ", ENV_VARS)
    def test_validation_empty_token(self):
        """Test that empty validation token triggers notification mode."""
        req = _create_http_request(
            params={"validationToken": ""},
            body=_create_valid_notification(),
        )
        mock_queue = Mock(spec=func.Out)

        response = main(req, mock_queue)

        # Empty string is falsy, so falls through to notification mode
        assert response.status_code == 202


class TestMailWebhookNotifications:
    """Test suite for notification processing mode."""

    @patch.dict("os.environ", ENV_VARS)
    @patch("MailWebhook.generate_ulid")
    def test_valid_notification_queued(self, mock_ulid):
        """Test that valid notification is queued for processing."""
        mock_ulid.return_value = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
        req = _create_http_request(body=_create_valid_notification())
        mock_queue = Mock(spec=func.Out)

        response = main(req, mock_queue)

        assert response.status_code == 202
        mock_queue.set.assert_called_once()

        # Verify queued message format
        queued_data = json.loads(mock_queue.set.call_args[0][0])
        assert queued_data["id"] == "01ARZ3NDEKTSV4RRFFQ69G5FAV"
        assert queued_data["type"] == "webhook"
        assert queued_data["subscription_id"] == "sub-123"
        assert queued_data["resource"] == "users/invoices@example.com/messages/msg-456"
        assert queued_data["change_type"] == "created"

    @patch.dict("os.environ", ENV_VARS)
    @patch("MailWebhook.generate_ulid")
    def test_multiple_notifications_all_queued(self, mock_ulid):
        """Test that multiple valid notifications are all queued."""
        mock_ulid.side_effect = ["ulid-1", "ulid-2", "ulid-3"]
        body = {
            "value": [
                {
                    "subscriptionId": "sub-1",
                    "clientState": "test-client-state-secret",
                    "changeType": "created",
                    "resource": "users/inbox/messages/msg-1",
                },
                {
                    "subscriptionId": "sub-2",
                    "clientState": "test-client-state-secret",
                    "changeType": "created",
                    "resource": "users/inbox/messages/msg-2",
                },
                {
                    "subscriptionId": "sub-3",
                    "clientState": "test-client-state-secret",
                    "changeType": "created",
                    "resource": "users/inbox/messages/msg-3",
                },
            ]
        }
        req = _create_http_request(body=body)
        mock_queue = Mock(spec=func.Out)

        response = main(req, mock_queue)

        assert response.status_code == 202
        assert mock_queue.set.call_count == 3

    @patch.dict("os.environ", ENV_VARS)
    def test_empty_notifications_returns_202(self):
        """Test that empty notification array returns 202."""
        req = _create_http_request(body={"value": []})
        mock_queue = Mock(spec=func.Out)

        response = main(req, mock_queue)

        assert response.status_code == 202
        mock_queue.set.assert_not_called()


class TestMailWebhookSecurity:
    """Test suite for security validation."""

    @patch.dict("os.environ", ENV_VARS)
    def test_invalid_client_state_skipped(self):
        """Test that notifications with invalid clientState are skipped."""
        notification = _create_valid_notification(client_state="wrong-state")
        req = _create_http_request(body=notification)
        mock_queue = Mock(spec=func.Out)

        response = main(req, mock_queue)

        assert response.status_code == 202
        mock_queue.set.assert_not_called()

    @patch.dict("os.environ", ENV_VARS)
    @patch("MailWebhook.generate_ulid")
    def test_mixed_valid_invalid_client_state(self, mock_ulid):
        """Test that only valid clientState notifications are queued."""
        mock_ulid.return_value = "ulid-valid"
        body = {
            "value": [
                {
                    "subscriptionId": "sub-valid",
                    "clientState": "test-client-state-secret",
                    "changeType": "created",
                    "resource": "users/inbox/messages/msg-valid",
                },
                {
                    "subscriptionId": "sub-invalid",
                    "clientState": "wrong-state",
                    "changeType": "created",
                    "resource": "users/inbox/messages/msg-invalid",
                },
            ]
        }
        req = _create_http_request(body=body)
        mock_queue = Mock(spec=func.Out)

        response = main(req, mock_queue)

        assert response.status_code == 202
        assert mock_queue.set.call_count == 1

        # Verify only valid notification was queued
        queued_data = json.loads(mock_queue.set.call_args[0][0])
        assert queued_data["subscription_id"] == "sub-valid"

    @patch.dict("os.environ", {"AzureWebJobsStorage": "test"})
    def test_missing_client_state_env_returns_500(self):
        """Test that missing GRAPH_CLIENT_STATE returns 500."""
        req = _create_http_request(body=_create_valid_notification())
        mock_queue = Mock(spec=func.Out)

        response = main(req, mock_queue)

        assert response.status_code == 500
        mock_queue.set.assert_not_called()

    @patch.dict("os.environ", {**ENV_VARS, "GRAPH_CLIENT_STATE": ""})
    def test_empty_client_state_env_returns_500(self):
        """Test that empty GRAPH_CLIENT_STATE returns 500."""
        req = _create_http_request(body=_create_valid_notification())
        mock_queue = Mock(spec=func.Out)

        response = main(req, mock_queue)

        assert response.status_code == 500

    @patch.dict("os.environ", ENV_VARS)
    def test_missing_client_state_in_notification_skipped(self):
        """Test that notification without clientState field is skipped."""
        body = {
            "value": [
                {
                    "subscriptionId": "sub-123",
                    # clientState field missing
                    "changeType": "created",
                    "resource": "users/inbox/messages/msg-456",
                }
            ]
        }
        req = _create_http_request(body=body)
        mock_queue = Mock(spec=func.Out)

        response = main(req, mock_queue)

        assert response.status_code == 202
        mock_queue.set.assert_not_called()


class TestMailWebhookErrorHandling:
    """Test suite for error handling."""

    @patch.dict("os.environ", ENV_VARS)
    def test_invalid_json_returns_400(self):
        """Test that invalid JSON body returns 400."""
        req = _create_http_request()  # No body, get_json raises ValueError
        mock_queue = Mock(spec=func.Out)

        response = main(req, mock_queue)

        assert response.status_code == 400

    @patch.dict("os.environ", ENV_VARS)
    def test_missing_value_field_returns_202(self):
        """Test that missing 'value' field returns 202 (empty notifications)."""
        req = _create_http_request(body={})
        mock_queue = Mock(spec=func.Out)

        response = main(req, mock_queue)

        assert response.status_code == 202
        mock_queue.set.assert_not_called()

    @patch.dict("os.environ", ENV_VARS)
    @patch("MailWebhook.generate_ulid")
    def test_queue_error_returns_500(self, mock_ulid):
        """Test that queue errors return 500 for retry."""
        mock_ulid.return_value = "test-ulid"
        req = _create_http_request(body=_create_valid_notification())
        mock_queue = Mock(spec=func.Out)
        mock_queue.set.side_effect = Exception("Queue connection failed")

        response = main(req, mock_queue)

        assert response.status_code == 500

    @patch.dict("os.environ", ENV_VARS)
    @patch("MailWebhook.generate_ulid")
    def test_ulid_generation_error_returns_500(self, mock_ulid):
        """Test that ULID generation errors return 500."""
        mock_ulid.side_effect = Exception("ULID generation failed")
        req = _create_http_request(body=_create_valid_notification())
        mock_queue = Mock(spec=func.Out)

        response = main(req, mock_queue)

        assert response.status_code == 500
        mock_queue.set.assert_not_called()


class TestMailWebhookEdgeCases:
    """Test suite for edge cases."""

    @patch.dict("os.environ", ENV_VARS)
    @patch("MailWebhook.generate_ulid")
    def test_notification_with_missing_optional_fields(self, mock_ulid):
        """Test notification processing with minimal required fields."""
        mock_ulid.return_value = "test-ulid"
        body = {
            "value": [
                {
                    "clientState": "test-client-state-secret",
                    # subscriptionId, changeType, resource are optional for queueing
                }
            ]
        }
        req = _create_http_request(body=body)
        mock_queue = Mock(spec=func.Out)

        response = main(req, mock_queue)

        assert response.status_code == 202
        mock_queue.set.assert_called_once()

        queued_data = json.loads(mock_queue.set.call_args[0][0])
        assert queued_data["subscription_id"] is None
        assert queued_data["resource"] is None
        assert queued_data["change_type"] is None

    @patch.dict("os.environ", ENV_VARS)
    @patch("MailWebhook.generate_ulid")
    def test_notification_preserves_all_fields(self, mock_ulid):
        """Test that all notification fields are preserved in queue message."""
        mock_ulid.return_value = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
        req = _create_http_request(body=_create_valid_notification())
        mock_queue = Mock(spec=func.Out)

        response = main(req, mock_queue)

        queued_data = json.loads(mock_queue.set.call_args[0][0])

        # Verify all expected fields are present
        assert "id" in queued_data
        assert "type" in queued_data
        assert "subscription_id" in queued_data
        assert "resource" in queued_data
        assert "change_type" in queued_data
        assert "timestamp" in queued_data

    @patch.dict("os.environ", ENV_VARS)
    def test_validation_takes_precedence_over_body(self):
        """Test that validation mode takes precedence even with body."""
        req = _create_http_request(
            params={"validationToken": "my-token"},
            body=_create_valid_notification(),
        )
        mock_queue = Mock(spec=func.Out)

        response = main(req, mock_queue)

        # Should return validation token, not process notifications
        assert response.status_code == 200
        assert response.get_body().decode() == "my-token"
        mock_queue.set.assert_not_called()
