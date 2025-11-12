"""
Unit tests for Microsoft Graph API client.

Tests authentication, email operations, throttling handling,
and retry logic with mocked Graph API responses.
"""

import pytest
import time
from unittest.mock import Mock, MagicMock, patch
from shared.graph_client import GraphAPIClient


# =============================================================================
# GRAPH API CLIENT INITIALIZATION TESTS
# =============================================================================


class TestGraphAPIClientInit:
    """Test Graph API client initialization."""

    @patch("shared.graph_client.ConfidentialClientApplication")
    def test_init_with_env_vars(self, mock_msal, mock_environment):
        """Test initialization with environment variables."""
        mock_app = MagicMock()
        mock_msal.return_value = mock_app

        client = GraphAPIClient()

        assert client.tenant_id == "test-tenant-id"
        assert client.client_id == "test-client-id"
        assert client.client_secret == "test-client-secret"
        assert client.graph_url == "https://graph.microsoft.com/v1.0"

    @patch("shared.graph_client.ConfidentialClientApplication")
    def test_init_with_explicit_params(self, mock_msal):
        """Test initialization with explicit parameters."""
        mock_app = MagicMock()
        mock_msal.return_value = mock_app

        client = GraphAPIClient(tenant_id="custom-tenant", client_id="custom-client", client_secret="custom-secret")

        assert client.tenant_id == "custom-tenant"
        assert client.client_id == "custom-client"
        assert client.client_secret == "custom-secret"

    def test_init_missing_credentials(self, monkeypatch):
        """Test initialization fails without credentials."""
        # Clear environment variables
        monkeypatch.delenv("GRAPH_TENANT_ID", raising=False)
        monkeypatch.delenv("GRAPH_CLIENT_ID", raising=False)
        monkeypatch.delenv("GRAPH_CLIENT_SECRET", raising=False)

        with pytest.raises(ValueError) as exc_info:
            GraphAPIClient()

        assert "Graph API credentials not configured" in str(exc_info.value)


# =============================================================================
# AUTHENTICATION TESTS
# =============================================================================


class TestGraphAPIAuthentication:
    """Test Graph API authentication."""

    @patch("shared.graph_client.ConfidentialClientApplication")
    def test_get_access_token_success(self, mock_msal, mock_environment):
        """Test successful token acquisition."""
        # Mock MSAL token acquisition
        mock_app = MagicMock()
        mock_app.acquire_token_for_client.return_value = {"access_token": "test-token-123", "expires_in": 3600}
        mock_msal.return_value = mock_app

        client = GraphAPIClient()
        token = client._get_access_token()

        assert token == "test-token-123"
        assert client._access_token == "test-token-123"
        mock_app.acquire_token_for_client.assert_called_once()

    @patch("shared.graph_client.ConfidentialClientApplication")
    def test_get_access_token_caching(self, mock_msal, mock_environment):
        """Test token caching prevents unnecessary requests."""
        mock_app = MagicMock()
        mock_app.acquire_token_for_client.return_value = {"access_token": "test-token-123", "expires_in": 3600}
        mock_msal.return_value = mock_app

        client = GraphAPIClient()

        # First call acquires token
        token1 = client._get_access_token()

        # Second call uses cached token
        token2 = client._get_access_token()

        assert token1 == token2
        # Should only call MSAL once due to caching
        assert mock_app.acquire_token_for_client.call_count == 1

    @patch("shared.graph_client.ConfidentialClientApplication")
    def test_get_access_token_failure(self, mock_msal, mock_environment):
        """Test token acquisition failure."""
        mock_app = MagicMock()
        mock_app.acquire_token_for_client.return_value = {
            "error": "invalid_client",
            "error_description": "Invalid client secret",
        }
        mock_msal.return_value = mock_app

        client = GraphAPIClient()

        with pytest.raises(Exception) as exc_info:
            client._get_access_token()

        assert "Failed to acquire token" in str(exc_info.value)


# =============================================================================
# EMAIL READING TESTS
# =============================================================================


class TestGetUnreadEmails:
    """Test getting unread emails."""

    @patch("shared.graph_client.ConfidentialClientApplication")
    def test_get_unread_emails_success(self, mock_msal, mock_environment):
        """Test successfully getting unread emails."""
        # Mock MSAL
        mock_app = MagicMock()
        mock_app.acquire_token_for_client.return_value = {"access_token": "test-token", "expires_in": 3600}
        mock_msal.return_value = mock_app

        client = GraphAPIClient()

        # Mock HTTP response
        with patch.object(client.session, "request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.content = b'{"value": []}'
            mock_response.json.return_value = {
                "value": [
                    {
                        "id": "msg1",
                        "sender": {"emailAddress": {"address": "billing@adobe.com"}},
                        "subject": "Invoice #12345",
                        "receivedDateTime": "2024-11-09T10:00:00Z",
                        "hasAttachments": True,
                    }
                ]
            }
            mock_request.return_value = mock_response

            emails = client.get_unread_emails("invoices@example.com")

            assert len(emails) == 1
            assert emails[0]["id"] == "msg1"
            assert emails[0]["subject"] == "Invoice #12345"

    @patch("shared.graph_client.ConfidentialClientApplication")
    def test_get_unread_emails_empty(self, mock_msal, mock_environment):
        """Test getting unread emails when none exist."""
        mock_app = MagicMock()
        mock_app.acquire_token_for_client.return_value = {"access_token": "test-token", "expires_in": 3600}
        mock_msal.return_value = mock_app

        client = GraphAPIClient()

        with patch.object(client.session, "request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.content = b'{"value": []}'
            mock_response.json.return_value = {"value": []}
            mock_request.return_value = mock_response

            emails = client.get_unread_emails("invoices@example.com")

            assert emails == []


# =============================================================================
# ATTACHMENT TESTS
# =============================================================================


class TestGetAttachments:
    """Test getting email attachments."""

    @patch("shared.graph_client.ConfidentialClientApplication")
    def test_get_attachments_success(self, mock_msal, mock_environment):
        """Test successfully getting attachments."""
        mock_app = MagicMock()
        mock_app.acquire_token_for_client.return_value = {"access_token": "test-token", "expires_in": 3600}
        mock_msal.return_value = mock_app

        client = GraphAPIClient()

        with patch.object(client.session, "request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.content = b'{"value": []}'
            mock_response.json.return_value = {
                "value": [
                    {
                        "id": "att1",
                        "name": "invoice.pdf",
                        "contentType": "application/pdf",
                        "size": 102400,
                        "contentBytes": "base64data",
                    }
                ]
            }
            mock_request.return_value = mock_response

            attachments = client.get_attachments("invoices@example.com", "msg1")

            assert len(attachments) == 1
            assert attachments[0]["name"] == "invoice.pdf"
            assert attachments[0]["contentType"] == "application/pdf"


# =============================================================================
# MARK AS READ TESTS
# =============================================================================


class TestMarkAsRead:
    """Test marking emails as read."""

    @patch("shared.graph_client.ConfidentialClientApplication")
    def test_mark_as_read_success(self, mock_msal, mock_environment):
        """Test successfully marking email as read."""
        mock_app = MagicMock()
        mock_app.acquire_token_for_client.return_value = {"access_token": "test-token", "expires_in": 3600}
        mock_msal.return_value = mock_app

        client = GraphAPIClient()

        with patch.object(client.session, "request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.content = b""
            mock_request.return_value = mock_response

            result = client.mark_as_read("invoices@example.com", "msg1")

            assert result is True
            # Verify PATCH was called
            mock_request.assert_called_once()
            assert mock_request.call_args[1]["method"] == "PATCH"


# =============================================================================
# SEND EMAIL TESTS
# =============================================================================


class TestSendEmail:
    """Test sending emails."""

    @patch("shared.graph_client.ConfidentialClientApplication")
    def test_send_email_without_attachments(self, mock_msal, mock_environment):
        """Test sending email without attachments."""
        mock_app = MagicMock()
        mock_app.acquire_token_for_client.return_value = {"access_token": "test-token", "expires_in": 3600}
        mock_msal.return_value = mock_app

        client = GraphAPIClient()

        with patch.object(client.session, "request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 202
            mock_response.content = b"{}"
            mock_response.json.return_value = {}
            mock_request.return_value = mock_response

            result = client.send_email(
                from_address="sender@example.com",
                to_address="recipient@example.com",
                subject="Test Subject",
                body="<html>Test Body</html>",
            )

            mock_request.assert_called_once()
            assert mock_request.call_args[1]["method"] == "POST"

    @patch("shared.graph_client.ConfidentialClientApplication")
    def test_send_email_with_attachments(self, mock_msal, mock_environment):
        """Test sending email with attachments."""
        mock_app = MagicMock()
        mock_app.acquire_token_for_client.return_value = {"access_token": "test-token", "expires_in": 3600}
        mock_msal.return_value = mock_app

        client = GraphAPIClient()

        with patch.object(client.session, "request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 202
            mock_response.content = b"{}"
            mock_response.json.return_value = {}
            mock_request.return_value = mock_response

            attachments = [{"name": "invoice.pdf", "contentBytes": "base64content", "contentType": "application/pdf"}]

            result = client.send_email(
                from_address="sender@example.com",
                to_address="recipient@example.com",
                subject="Invoice",
                body="See attached",
                attachments=attachments,
            )

            mock_request.assert_called_once()
            # Verify attachment was included
            call_json = mock_request.call_args[1]["json"]
            assert "attachments" in call_json["message"]


# =============================================================================
# THROTTLING AND ERROR HANDLING TESTS
# =============================================================================


class TestThrottlingAndErrors:
    """Test throttling and error handling."""

    @patch("shared.graph_client.ConfidentialClientApplication")
    def test_handles_throttling_429(self, mock_msal, mock_environment):
        """Test handling of 429 throttling response."""
        mock_app = MagicMock()
        mock_app.acquire_token_for_client.return_value = {"access_token": "test-token", "expires_in": 3600}
        mock_msal.return_value = mock_app

        client = GraphAPIClient()

        with patch.object(client.session, "request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 429
            mock_response.headers = {"Retry-After": "60"}
            mock_request.return_value = mock_response

            with pytest.raises(Exception) as exc_info:
                client._make_request("GET", "test/endpoint")

            assert "Throttled" in str(exc_info.value)
            assert "retry after 60s" in str(exc_info.value)

    @patch("shared.graph_client.ConfidentialClientApplication")
    def test_handles_http_errors(self, mock_msal, mock_environment):
        """Test handling of HTTP error responses."""
        mock_app = MagicMock()
        mock_app.acquire_token_for_client.return_value = {"access_token": "test-token", "expires_in": 3600}
        mock_msal.return_value = mock_app

        client = GraphAPIClient()

        with patch.object(client.session, "request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_response.raise_for_status.side_effect = Exception("Not found")
            mock_request.return_value = mock_response

            with pytest.raises(Exception) as exc_info:
                client._make_request("GET", "test/endpoint")

            assert "Not found" in str(exc_info.value)
