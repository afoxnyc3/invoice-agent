"""
Microsoft Graph API client for email operations.

Provides authenticated access to Microsoft Graph API for:
- Reading unread emails from a mailbox
- Marking emails as read
- Sending emails with attachments

Uses MSAL for authentication and handles throttling automatically.
"""

import os
import time
import base64
from typing import List, Dict, Any, Optional
import requests
from msal import ConfidentialClientApplication
from shared.retry import retry_with_backoff
from shared.logger import get_logger


class GraphAPIClient:
    """
    Microsoft Graph API client for email operations.

    Handles authentication via MSAL and provides methods for
    email reading, marking, and sending operations.
    """

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None
    ):
        """
        Initialize Graph API client with credentials.

        Args:
            tenant_id: Azure AD tenant ID (or from env)
            client_id: App registration client ID (or from env)
            client_secret: App registration secret (or from env)

        Raises:
            ValueError: If required credentials are missing
        """
        self.tenant_id = tenant_id or os.environ.get('GRAPH_TENANT_ID')
        self.client_id = client_id or os.environ.get('GRAPH_CLIENT_ID')
        self.client_secret = client_secret or os.environ.get('GRAPH_CLIENT_SECRET')

        if not all([self.tenant_id, self.client_id, self.client_secret]):
            raise ValueError("Graph API credentials not configured")

        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.scopes = ["https://graph.microsoft.com/.default"]
        self.graph_url = "https://graph.microsoft.com/v1.0"

        # Initialize MSAL app
        self.app = ConfidentialClientApplication(
            client_id=self.client_id,
            client_credential=self.client_secret,
            authority=self.authority
        )

        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })

        self._access_token: Optional[str] = None
        self._token_expiry: float = 0

    def _get_access_token(self) -> str:
        """
        Get valid access token, refreshing if needed.

        Returns:
            str: Valid access token

        Raises:
            Exception: If token acquisition fails
        """
        # Check if token is still valid (with 5 min buffer)
        if self._access_token and time.time() < (self._token_expiry - 300):
            return self._access_token

        # Acquire new token
        result = self.app.acquire_token_for_client(scopes=self.scopes)

        if "access_token" not in result:
            error = result.get("error_description", "Unknown error")
            raise Exception(f"Failed to acquire token: {error}")

        self._access_token = result["access_token"]
        self._token_expiry = time.time() + result.get("expires_in", 3600)

        return self._access_token

    def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make authenticated request to Graph API.

        Handles authentication, throttling, and retries.

        Args:
            method: HTTP method (GET, POST, PATCH)
            endpoint: API endpoint (relative to graph_url)
            **kwargs: Additional request parameters

        Returns:
            dict: Response JSON

        Raises:
            Exception: If request fails after retries
        """
        url = f"{self.graph_url}/{endpoint}"
        token = self._get_access_token()

        headers = kwargs.pop('headers', {})
        headers['Authorization'] = f'Bearer {token}'

        response = self.session.request(
            method=method,
            url=url,
            headers=headers,
            **kwargs
        )

        # Handle throttling with retry-after
        if response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 60))
            raise Exception(f"Throttled, retry after {retry_after}s")

        response.raise_for_status()
        return response.json() if response.content else {}

    @retry_with_backoff(max_attempts=3, initial_delay=2.0)
    def get_unread_emails(
        self,
        mailbox: str,
        max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get unread emails from a mailbox.

        Args:
            mailbox: Email address of mailbox to query
            max_results: Maximum number of emails to return

        Returns:
            list: List of email message objects with:
                - id: Message ID
                - sender: Sender information
                - subject: Email subject
                - receivedDateTime: Timestamp
                - hasAttachments: Boolean
                - body: Email body

        Example:
            >>> client = GraphAPIClient()
            >>> emails = client.get_unread_emails('invoices@example.com')
            >>> for email in emails:
            ...     print(email['subject'])
        """
        endpoint = f"users/{mailbox}/messages"
        params = {
            '$filter': 'isRead eq false',
            '$select': 'id,sender,subject,receivedDateTime,hasAttachments,body',
            '$top': max_results,
            '$orderby': 'receivedDateTime desc'
        }

        response = self._make_request('GET', endpoint, params=params)
        return response.get('value', [])

    def get_attachments(
        self,
        mailbox: str,
        message_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get attachments for a specific email.

        Args:
            mailbox: Email address of mailbox
            message_id: ID of the email message

        Returns:
            list: List of attachment objects with:
                - id: Attachment ID
                - name: Filename
                - contentType: MIME type
                - size: Size in bytes
                - contentBytes: Base64 encoded content
        """
        endpoint = f"users/{mailbox}/messages/{message_id}/attachments"
        response = self._make_request('GET', endpoint)
        return response.get('value', [])

    @retry_with_backoff(max_attempts=3, initial_delay=1.0)
    def mark_as_read(self, mailbox: str, message_id: str) -> bool:
        """
        Mark an email as read.

        Args:
            mailbox: Email address of mailbox
            message_id: ID of the email message

        Returns:
            bool: True if successful

        Raises:
            Exception: If operation fails
        """
        endpoint = f"users/{mailbox}/messages/{message_id}"
        body = {'isRead': True}

        self._make_request('PATCH', endpoint, json=body)
        return True

    @retry_with_backoff(max_attempts=3, initial_delay=2.0)
    def send_email(
        self,
        from_address: str,
        to_address: str,
        subject: str,
        body: str,
        attachments: Optional[List[Dict[str, Any]]] = None,
        is_html: bool = True
    ) -> Dict[str, Any]:
        """
        Send an email with optional attachments.

        Args:
            from_address: Sender email address
            to_address: Recipient email address
            subject: Email subject
            body: Email body content
            attachments: Optional list of attachments, each with:
                - name: Filename
                - contentBytes: Base64 encoded content
                - contentType: MIME type
            is_html: Whether body is HTML (default: True)

        Returns:
            dict: Response from Graph API

        Example:
            >>> client.send_email(
            ...     from_address='sender@example.com',
            ...     to_address='recipient@example.com',
            ...     subject='Invoice Processed',
            ...     body='<html>Invoice details...</html>',
            ...     attachments=[{
            ...         'name': 'invoice.pdf',
            ...         'contentBytes': base64_content,
            ...         'contentType': 'application/pdf'
            ...     }]
            ... )
        """
        message = {
            'subject': subject,
            'body': {
                'contentType': 'HTML' if is_html else 'Text',
                'content': body
            },
            'toRecipients': [
                {'emailAddress': {'address': to_address}}
            ]
        }

        if attachments:
            message['attachments'] = attachments

        endpoint = f"users/{from_address}/sendMail"
        body = {'message': message, 'saveToSentItems': True}

        return self._make_request('POST', endpoint, json=body)

    def __del__(self):
        """Clean up session on deletion."""
        if hasattr(self, 'session'):
            self.session.close()
