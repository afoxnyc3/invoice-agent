"""
Unit tests for shared data models
"""

import pytest
import json
from datetime import datetime
from src.shared.models import RawMail, WorkItem, NotifyPayload, Attachment


class TestRawMailModel:
    """Test RawMail data model."""

    def test_create_raw_mail(self):
        """Test creating a RawMail instance."""
        raw_mail = RawMail(
            message_id="msg123",
            sender="billing@adobe.com",
            subject="Invoice #12345",
            attachments=[
                Attachment(
                    name="invoice.pdf",
                    blob_url="https://storage/invoices/raw/invoice.pdf"
                )
            ]
        )

        assert raw_mail.message_id == "msg123"
        assert raw_mail.sender == "billing@adobe.com"
        assert raw_mail.subject == "Invoice #12345"
        assert len(raw_mail.attachments) == 1
        assert raw_mail.attachments[0].name == "invoice.pdf"

    def test_raw_mail_json_serialization(self):
        """Test RawMail JSON serialization."""
        raw_mail = RawMail(
            message_id="msg123",
            sender="billing@adobe.com",
            subject="Invoice #12345",
            attachments=[]
        )

        json_str = raw_mail.model_dump_json()
        data = json.loads(json_str)

        assert data["message_id"] == "msg123"
        assert data["sender"] == "billing@adobe.com"
        assert data["subject"] == "Invoice #12345"

    def test_raw_mail_validation(self):
        """Test RawMail validation."""
        with pytest.raises(ValueError):
            # Missing required fields
            RawMail()

        with pytest.raises(ValueError):
            # Invalid email format (if validation added)
            RawMail(
                message_id="msg123",
                sender="invalid-email",
                subject="Test",
                attachments=[]
            )


class TestWorkItemModel:
    """Test WorkItem data model."""

    def test_create_work_item(self):
        """Test creating a WorkItem instance."""
        work_item = WorkItem(
            item_id="item123",
            vendor_name="Adobe Inc",
            ExpenseDept="IT",
            AllocationScheduleNumber="MONTHLY",
            GLCode="6100",
            BillingParty="Chelsea Piers NY"
        )

        assert work_item.item_id == "item123"
        assert work_item.vendor_name == "Adobe Inc"
        assert work_item.ExpenseDept == "IT"
        assert work_item.GLCode == "6100"

    def test_work_item_optional_fields(self):
        """Test WorkItem with optional fields."""
        work_item = WorkItem(
            item_id="item123",
            vendor_name="Unknown Vendor"
            # Optional fields not provided
        )

        assert work_item.item_id == "item123"
        assert work_item.vendor_name == "Unknown Vendor"
        assert work_item.ExpenseDept is None
        assert work_item.GLCode is None

    def test_work_item_json_serialization(self):
        """Test WorkItem JSON serialization."""
        work_item = WorkItem(
            item_id="item123",
            vendor_name="Adobe Inc",
            ExpenseDept="IT",
            GLCode="6100"
        )

        json_str = work_item.model_dump_json(exclude_none=True)
        data = json.loads(json_str)

        assert data["item_id"] == "item123"
        assert data["vendor_name"] == "Adobe Inc"
        assert "AllocationScheduleNumber" not in data  # None excluded


class TestNotifyPayloadModel:
    """Test NotifyPayload data model."""

    def test_create_notify_payload(self):
        """Test creating a NotifyPayload instance."""
        payload = NotifyPayload(
            title="Invoice Processed",
            facts={
                "Vendor": "Adobe Inc",
                "GL Code": "6100",
                "Status": "Success"
            }
        )

        assert payload.title == "Invoice Processed"
        assert payload.facts["Vendor"] == "Adobe Inc"
        assert payload.facts["GL Code"] == "6100"
        assert len(payload.facts) == 3

    def test_notify_payload_empty_facts(self):
        """Test NotifyPayload with empty facts."""
        payload = NotifyPayload(
            title="Test Notification",
            facts={}
        )

        assert payload.title == "Test Notification"
        assert payload.facts == {}

    def test_notify_payload_teams_format(self):
        """Test NotifyPayload formatted for Teams."""
        payload = NotifyPayload(
            title="Invoice Processed",
            facts={
                "Vendor": "Adobe Inc",
                "Amount": "$1,250.00"
            }
        )

        # Convert to Teams message format
        teams_message = {
            "@type": "MessageCard",
            "text": payload.title,
            "sections": [{
                "facts": [
                    {"name": k, "value": v}
                    for k, v in payload.facts.items()
                ]
            }]
        }

        assert teams_message["text"] == "Invoice Processed"
        assert len(teams_message["sections"][0]["facts"]) == 2


class TestAttachmentModel:
    """Test Attachment data model."""

    def test_create_attachment(self):
        """Test creating an Attachment instance."""
        attachment = Attachment(
            name="invoice_12345.pdf",
            blob_url="https://storage.blob.core.windows.net/invoices/raw/invoice_12345.pdf"
        )

        assert attachment.name == "invoice_12345.pdf"
        assert "invoice_12345.pdf" in attachment.blob_url

    def test_attachment_validation(self):
        """Test Attachment validation."""
        # Valid attachment
        attachment = Attachment(
            name="test.pdf",
            blob_url="https://storage/test.pdf"
        )
        assert attachment.name == "test.pdf"

        # Test with empty name (should fail if validation added)
        with pytest.raises(ValueError):
            Attachment(
                name="",
                blob_url="https://storage/test.pdf"
            )