"""
Mock Microsoft Graph API client for integration tests.

Simulates Graph API responses without making actual API calls.
"""

import base64
from typing import List, Dict, Any, Optional


class MockGraphAPIClient:
    """Mock Graph API client for testing."""

    def __init__(self):
        """Initialize mock client with predefined responses."""
        self.emails: List[Dict[str, Any]] = []
        self.sent_emails: List[Dict[str, Any]] = []
        self.marked_read: List[str] = []

    def add_test_email(self, email: Dict[str, Any]) -> None:
        """Add email to mock inbox."""
        self.emails.append(email)

    def get_unread_emails(self, mailbox: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """Return mock unread emails."""
        return self.emails[:max_results]

    def get_attachments(self, mailbox: str, message_id: str) -> List[Dict[str, Any]]:
        """Return mock attachments for email."""
        email = next((e for e in self.emails if e["id"] == message_id), None)
        if not email or not email.get("hasAttachments"):
            return []

        # Return attachment metadata with base64 sample PDF
        sample_pdf = b"%PDF-1.4\nSample Invoice\n%%EOF"
        return [
            {
                "id": att["id"],
                "name": att["name"],
                "contentType": att["contentType"],
                "contentBytes": base64.b64encode(sample_pdf).decode(),
                "size": att.get("size", len(sample_pdf)),
            }
            for att in email.get("attachments", [])
        ]

    def mark_as_read(self, mailbox: str, message_id: str) -> bool:
        """Mark email as read."""
        self.marked_read.append(message_id)
        return True

    def send_email(
        self,
        from_address: str,
        to_address: str,
        subject: str,
        body: str,
        is_html: bool = False,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Mock send email."""
        sent_email = {
            "id": f"sent-{len(self.sent_emails) + 1}",
            "from": from_address,
            "to": to_address,
            "subject": subject,
            "body": body,
            "is_html": is_html,
            "attachments": attachments or [],
            "status": "sent",
        }
        self.sent_emails.append(sent_email)
        return sent_email

    def get_sent_emails(self) -> List[Dict[str, Any]]:
        """Return all sent emails."""
        return self.sent_emails

    def reset(self) -> None:
        """Reset mock state."""
        self.emails.clear()
        self.sent_emails.clear()
        self.marked_read.clear()
