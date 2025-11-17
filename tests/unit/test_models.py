"""
Unit tests for shared data models.

Tests all queue message models, Azure Table Storage entity models,
and Teams webhook message card models for validation and serialization.
"""

import pytest
import json
from datetime import datetime
from pydantic import ValidationError
from shared.models import (
    RawMail,
    EnrichedInvoice,
    NotificationMessage,
    VendorMaster,
    InvoiceTransaction,
    MessageCardFact,
    MessageCardSection,
    TeamsMessageCard,
)


# =============================================================================
# QUEUE MESSAGE MODEL TESTS
# =============================================================================


class TestRawMailModel:
    """Test RawMail data model."""

    def test_create_valid_raw_mail(self):
        """Test creating a valid RawMail instance."""
        raw_mail = RawMail(
            id="01JCK3Q7H8ZVXN3BARC9GWAEZM",
            sender="billing@adobe.com",
            subject="Invoice #12345 - November 2024",
            blob_url="https://storage.blob.core.windows.net/invoices/raw/invoice123.pdf",
            received_at="2024-11-09T14:00:00Z",
            original_message_id="graph-message-id-123",
        )

        assert raw_mail.id == "01JCK3Q7H8ZVXN3BARC9GWAEZM"
        assert raw_mail.sender == "billing@adobe.com"
        assert raw_mail.subject == "Invoice #12345 - November 2024"
        assert raw_mail.blob_url.startswith("https://")
        assert raw_mail.received_at == "2024-11-09T14:00:00Z"
        assert raw_mail.original_message_id == "graph-message-id-123"

    def test_raw_mail_json_serialization(self):
        """Test RawMail JSON serialization."""
        raw_mail = RawMail(
            id="01JCK3Q7H8ZVXN3BARC9GWAEZM",
            sender="billing@adobe.com",
            subject="Invoice #12345",
            blob_url="https://storage/invoices/raw/invoice.pdf",
            received_at="2024-11-09T14:00:00Z",
            original_message_id="graph-message-id-123",
        )

        json_str = raw_mail.model_dump_json()
        data = json.loads(json_str)

        assert data["id"] == "01JCK3Q7H8ZVXN3BARC9GWAEZM"
        assert data["sender"] == "billing@adobe.com"
        assert data["subject"] == "Invoice #12345"
        assert data["blob_url"] == "https://storage/invoices/raw/invoice.pdf"
        assert data["received_at"] == "2024-11-09T14:00:00Z"
        assert data["original_message_id"] == "graph-message-id-123"

    def test_raw_mail_invalid_email(self):
        """Test RawMail validation rejects invalid email."""
        with pytest.raises(ValidationError) as exc_info:
            RawMail(
                id="01JCK3Q7H8ZVXN3BARC9GWAEZM",
                sender="invalid-email-format",
                subject="Test",
                blob_url="https://storage/test.pdf",
                received_at="2024-11-09T14:00:00Z",
                original_message_id="graph-message-id-123",
            )
        assert "sender" in str(exc_info.value)

    def test_raw_mail_invalid_blob_url(self):
        """Test RawMail validation rejects non-HTTPS URL."""
        with pytest.raises(ValidationError) as exc_info:
            RawMail(
                id="01JCK3Q7H8ZVXN3BARC9GWAEZM",
                sender="billing@adobe.com",
                subject="Test",
                blob_url="http://storage/test.pdf",  # HTTP not HTTPS
                received_at="2024-11-09T14:00:00Z",
                original_message_id="graph-message-id-123",
            )
        assert "blob_url must be HTTPS" in str(exc_info.value)

    def test_raw_mail_empty_id(self):
        """Test RawMail validation rejects empty ID."""
        with pytest.raises(ValidationError) as exc_info:
            RawMail(
                id="",
                sender="billing@adobe.com",
                subject="Test",
                blob_url="https://storage/test.pdf",
                received_at="2024-11-09T14:00:00Z",
                original_message_id="graph-message-id-123",
            )
        assert "id cannot be empty" in str(exc_info.value)

    def test_raw_mail_with_original_message_id(self):
        """Test RawMail with original_message_id for deduplication."""
        raw_mail = RawMail(
            id="01JCK3Q7H8ZVXN3BARC9GWAEZM",
            sender="billing@adobe.com",
            subject="Invoice #12345",
            blob_url="https://storage/invoices/raw/invoice.pdf",
            received_at="2024-11-09T14:00:00Z",
            original_message_id="AAMkADExYjM5ZTg3LTBjZTUtNDI5Mi1iMjY4LTg4OTgxZjU4OWUyYgBGAAAAAACvZWm9r6BXRaYvHJvN8-cABwACPwxDp9QgR52KKW-z8RjbAAAAAAEMAAACPwxDp9QgR52KKW-z8RjbAABt7xS3AAA=",
        )

        assert (
            raw_mail.original_message_id
            == "AAMkADExYjM5ZTg3LTBjZTUtNDI5Mi1iMjY4LTg4OTgxZjU4OWUyYgBGAAAAAACvZWm9r6BXRaYvHJvN8-cABwACPwxDp9QgR52KKW-z8RjbAAAAAAEMAAACPwxDp9QgR52KKW-z8RjbAABt7xS3AAA="
        )

    def test_raw_mail_missing_original_message_id(self):
        """Test RawMail validation requires original_message_id."""
        with pytest.raises(ValidationError) as exc_info:
            RawMail(
                id="01JCK3Q7H8ZVXN3BARC9GWAEZM",
                sender="billing@adobe.com",
                subject="Test",
                blob_url="https://storage/test.pdf",
                received_at="2024-11-09T14:00:00Z",
                # Missing original_message_id
            )
        assert "original_message_id" in str(exc_info.value)


class TestEnrichedInvoiceModel:
    """Test EnrichedInvoice data model."""

    def test_create_valid_enriched_invoice(self):
        """Test creating a valid EnrichedInvoice instance."""
        invoice = EnrichedInvoice(
            id="01JCK3Q7H8ZVXN3BARC9GWAEZM",
            vendor_name="Adobe Inc",
            expense_dept="IT",
            gl_code="6100",
            allocation_schedule="MONTHLY",
            billing_party="Company HQ",
            blob_url="https://storage/invoices/raw/invoice.pdf",
            original_message_id="graph-message-id-123",
            status="enriched",
        )

        assert invoice.id == "01JCK3Q7H8ZVXN3BARC9GWAEZM"
        assert invoice.vendor_name == "Adobe Inc"
        assert invoice.expense_dept == "IT"
        assert invoice.gl_code == "6100"
        assert invoice.allocation_schedule == "MONTHLY"
        assert invoice.billing_party == "Company HQ"
        assert invoice.original_message_id == "graph-message-id-123"
        assert invoice.status == "enriched"

    def test_enriched_invoice_unknown_status(self):
        """Test EnrichedInvoice with unknown status."""
        invoice = EnrichedInvoice(
            id="01JCK3Q7H8ZVXN3BARC9GWAEZM",
            vendor_name="UNKNOWN",
            expense_dept="UNKNOWN",
            gl_code="9999",
            allocation_schedule="UNKNOWN",
            billing_party="UNKNOWN",
            blob_url="https://storage/invoices/raw/invoice.pdf",
            original_message_id="graph-message-id-123",
            status="unknown",
        )

        assert invoice.status == "unknown"
        assert invoice.vendor_name == "UNKNOWN"
        assert invoice.original_message_id == "graph-message-id-123"

    def test_enriched_invoice_invalid_gl_code(self):
        """Test EnrichedInvoice validation rejects invalid GL code."""
        with pytest.raises(ValidationError) as exc_info:
            EnrichedInvoice(
                id="01JCK3Q7H8ZVXN3BARC9GWAEZM",
                vendor_name="Adobe Inc",
                expense_dept="IT",
                gl_code="123",  # Only 3 digits
                allocation_schedule="MONTHLY",
                billing_party="Company HQ",
                blob_url="https://storage/test.pdf",
                original_message_id="graph-message-id-123",
                status="enriched",
            )
        assert "gl_code must be exactly 4 digits" in str(exc_info.value)

    def test_enriched_invoice_empty_vendor_name(self):
        """Test EnrichedInvoice validation rejects empty vendor name."""
        with pytest.raises(ValidationError) as exc_info:
            EnrichedInvoice(
                id="01JCK3Q7H8ZVXN3BARC9GWAEZM",
                vendor_name="",
                expense_dept="IT",
                gl_code="6100",
                allocation_schedule="MONTHLY",
                billing_party="Company HQ",
                blob_url="https://storage/test.pdf",
                original_message_id="graph-message-id-123",
                status="enriched",
            )
        assert "Field cannot be empty" in str(exc_info.value)

    def test_enriched_invoice_with_original_message_id(self):
        """Test EnrichedInvoice with original_message_id for deduplication."""
        invoice = EnrichedInvoice(
            id="01JCK3Q7H8ZVXN3BARC9GWAEZM",
            vendor_name="Adobe Inc",
            expense_dept="IT",
            gl_code="6100",
            allocation_schedule="MONTHLY",
            billing_party="Company HQ",
            blob_url="https://storage/invoices/raw/invoice.pdf",
            original_message_id="AAMkADExYjM5ZTg3LTBjZTUtNDI5Mi1iMjY4LTg4OTgxZjU4OWUyYgBGAAAAAACvZWm9r6BXRaYvHJvN8-cABwACPwxDp9QgR52KKW-z8RjbAAAAAAEMAAACPwxDp9QgR52KKW-z8RjbAABt7xS3AAA=",
            status="enriched",
        )

        assert (
            invoice.original_message_id
            == "AAMkADExYjM5ZTg3LTBjZTUtNDI5Mi1iMjY4LTg4OTgxZjU4OWUyYgBGAAAAAACvZWm9r6BXRaYvHJvN8-cABwACPwxDp9QgR52KKW-z8RjbAAAAAAEMAAACPwxDp9QgR52KKW-z8RjbAABt7xS3AAA="
        )

    def test_enriched_invoice_missing_original_message_id(self):
        """Test EnrichedInvoice validation requires original_message_id."""
        with pytest.raises(ValidationError) as exc_info:
            EnrichedInvoice(
                id="01JCK3Q7H8ZVXN3BARC9GWAEZM",
                vendor_name="Adobe Inc",
                expense_dept="IT",
                gl_code="6100",
                allocation_schedule="MONTHLY",
                billing_party="Company HQ",
                blob_url="https://storage/test.pdf",
                status="enriched",
                # Missing original_message_id
            )
        assert "original_message_id" in str(exc_info.value)


class TestNotificationMessageModel:
    """Test NotificationMessage data model."""

    def test_create_success_notification(self):
        """Test creating a success notification."""
        notification = NotificationMessage(
            type="success",
            message="Processed: Adobe Inc - GL 6100",
            details={"vendor": "Adobe Inc", "gl_code": "6100", "transaction_id": "01JCK3Q7H8ZVXN3BARC9GWAEZM"},
        )

        assert notification.type == "success"
        assert "Adobe Inc" in notification.message
        assert notification.details["transaction_id"] == "01JCK3Q7H8ZVXN3BARC9GWAEZM"

    def test_create_unknown_vendor_notification(self):
        """Test creating an unknown vendor notification."""
        notification = NotificationMessage(
            type="unknown",
            message="Unknown vendor: newvendor@example.com",
            details={
                "sender": "newvendor@example.com",
                "subject": "Invoice #12345",
                "transaction_id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
            },
        )

        assert notification.type == "unknown"
        assert "Unknown vendor" in notification.message

    def test_create_error_notification(self):
        """Test creating an error notification."""
        notification = NotificationMessage(
            type="error",
            message="Failed to process invoice",
            details={"error": "Graph API connection failed", "transaction_id": "01JCK3Q7H8ZVXN3BARC9GWAEZM"},
        )

        assert notification.type == "error"
        assert "Failed" in notification.message

    def test_notification_missing_transaction_id(self):
        """Test NotificationMessage validation requires transaction_id for success."""
        with pytest.raises(ValidationError) as exc_info:
            NotificationMessage(
                type="success",
                message="Test",
                details={
                    "vendor": "Adobe Inc"
                    # Missing transaction_id
                },
            )
        assert "transaction_id required" in str(exc_info.value)


# =============================================================================
# AZURE TABLE STORAGE ENTITY MODEL TESTS
# =============================================================================


class TestVendorMasterModel:
    """Test VendorMaster data model."""

    def test_create_valid_vendor(self):
        """Test creating a valid VendorMaster entity."""
        vendor = VendorMaster(
            RowKey="adobe",
            VendorName="Adobe",
            ExpenseDept="IT",
            AllocationSchedule="1",
            GLCode="6100",
            ProductCategory="Direct",
            VenueRequired=False,
            UpdatedAt="2024-11-09T12:00:00Z",
        )

        assert vendor.PartitionKey == "Vendor"  # Default value
        assert vendor.RowKey == "adobe"
        assert vendor.VendorName == "Adobe"
        assert vendor.GLCode == "6100"
        assert vendor.ProductCategory == "Direct"
        assert vendor.Active is True  # Default value

    def test_vendor_invalid_gl_code(self):
        """Test VendorMaster validation rejects invalid GL code."""
        with pytest.raises(ValidationError) as exc_info:
            VendorMaster(
                RowKey="adobe",
                VendorName="Adobe",
                ExpenseDept="IT",
                AllocationSchedule="1",
                GLCode="ABC1",  # Not all digits
                ProductCategory="Direct",
                UpdatedAt="2024-11-09T12:00:00Z",
            )
        assert "GLCode must be exactly 4 digits" in str(exc_info.value)

    def test_vendor_invalid_row_key(self):
        """Test VendorMaster validation rejects invalid RowKey."""
        with pytest.raises(ValidationError) as exc_info:
            VendorMaster(
                RowKey="Adobe",  # Not lowercase
                VendorName="Adobe",
                ExpenseDept="IT",
                AllocationSchedule="1",
                GLCode="6100",
                ProductCategory="Direct",
                UpdatedAt="2024-11-09T12:00:00Z",
            )
        assert "RowKey must be lowercase" in str(exc_info.value)


class TestInvoiceTransactionModel:
    """Test InvoiceTransaction data model."""

    def test_create_valid_transaction(self):
        """Test creating a valid InvoiceTransaction entity."""
        transaction = InvoiceTransaction(
            PartitionKey="202411",
            RowKey="01JCK3Q7H8ZVXN3BARC9GWAEZM",
            VendorName="Adobe Inc",
            SenderEmail="billing@adobe.com",
            RecipientEmail="accountspayable@chelseapiers.com",
            ExpenseDept="IT",
            GLCode="6100",
            Status="processed",
            BlobUrl="https://storage/invoices/raw/invoice.pdf",
            ProcessedAt="2024-11-09T14:30:00Z",
        )

        assert transaction.PartitionKey == "202411"
        assert transaction.RowKey == "01JCK3Q7H8ZVXN3BARC9GWAEZM"
        assert transaction.Status == "processed"
        assert transaction.ErrorMessage is None
        assert transaction.RecipientEmail == "accountspayable@chelseapiers.com"

    def test_transaction_with_error(self):
        """Test InvoiceTransaction with error status and message."""
        transaction = InvoiceTransaction(
            PartitionKey="202411",
            RowKey="01JCK3Q7H8ZVXN3BARC9GWAEZM",
            VendorName="Unknown Vendor",
            SenderEmail="unknown@example.com",
            RecipientEmail="accountspayable@chelseapiers.com",
            ExpenseDept="UNKNOWN",
            GLCode="9999",
            Status="error",
            BlobUrl="https://storage/invoices/raw/invoice.pdf",
            ProcessedAt="2024-11-09T14:30:00Z",
            ErrorMessage="Graph API connection failed",
        )

        assert transaction.Status == "error"
        assert transaction.ErrorMessage == "Graph API connection failed"

    def test_transaction_invalid_partition_key(self):
        """Test InvoiceTransaction validation rejects invalid PartitionKey."""
        with pytest.raises(ValidationError) as exc_info:
            InvoiceTransaction(
                PartitionKey="2024-11",  # Wrong format
                RowKey="01JCK3Q7H8ZVXN3BARC9GWAEZM",
                VendorName="Adobe Inc",
                SenderEmail="billing@adobe.com",
                RecipientEmail="accountspayable@chelseapiers.com",
                ExpenseDept="IT",
                GLCode="6100",
                Status="processed",
                BlobUrl="https://storage/test.pdf",
                ProcessedAt="2024-11-09T14:30:00Z",
            )
        assert "PartitionKey must be YYYYMM format" in str(exc_info.value)

    def test_transaction_error_without_message(self):
        """Test InvoiceTransaction validation requires ErrorMessage when Status is error."""
        with pytest.raises(ValidationError) as exc_info:
            InvoiceTransaction(
                PartitionKey="202411",
                RowKey="01JCK3Q7H8ZVXN3BARC9GWAEZM",
                VendorName="Adobe Inc",
                SenderEmail="billing@adobe.com",
                RecipientEmail="accountspayable@chelseapiers.com",
                ExpenseDept="IT",
                GLCode="6100",
                Status="error",
                BlobUrl="https://storage/test.pdf",
                ProcessedAt="2024-11-09T14:30:00Z",
                # Missing ErrorMessage
            )
        assert "ErrorMessage required when Status is error" in str(exc_info.value)


# =============================================================================
# TEAMS WEBHOOK MESSAGE CARD MODEL TESTS
# =============================================================================


class TestTeamsMessageCardModels:
    """Test Teams webhook message card models."""

    def test_create_message_card_fact(self):
        """Test creating a MessageCardFact."""
        fact = MessageCardFact(name="Vendor", value="Adobe Inc")

        assert fact.name == "Vendor"
        assert fact.value == "Adobe Inc"

    def test_create_message_card_section(self):
        """Test creating a MessageCardSection."""
        section = MessageCardSection(
            facts=[MessageCardFact(name="Vendor", value="Adobe Inc"), MessageCardFact(name="GL Code", value="6100")]
        )

        assert len(section.facts) == 2
        assert section.facts[0].name == "Vendor"

    def test_create_success_teams_card(self):
        """Test creating a success Teams message card."""
        card = TeamsMessageCard(
            themeColor="00FF00",
            text="✅ Invoice Processed",
            sections=[
                MessageCardSection(
                    facts=[
                        MessageCardFact(name="Vendor", value="Adobe Inc"),
                        MessageCardFact(name="GL Code", value="6100"),
                        MessageCardFact(name="Department", value="IT"),
                    ]
                )
            ],
        )

        assert card.type == "MessageCard"
        assert card.themeColor == "00FF00"
        assert card.text == "✅ Invoice Processed"
        assert len(card.sections) == 1
        assert len(card.sections[0].facts) == 3

    def test_teams_card_invalid_color(self):
        """Test TeamsMessageCard validation rejects invalid color."""
        with pytest.raises(ValidationError) as exc_info:
            TeamsMessageCard(themeColor="green", text="Test", sections=[])  # Not hex code
        assert "themeColor must be 6-digit hex code" in str(exc_info.value)

    def test_teams_card_json_serialization(self):
        """Test TeamsMessageCard JSON serialization with @type alias."""
        card = TeamsMessageCard(themeColor="00FF00", text="Test Message", sections=[MessageCardSection(facts=[])])

        json_data = json.loads(card.model_dump_json(by_alias=True))

        assert json_data["@type"] == "MessageCard"
        assert json_data["themeColor"] == "00FF00"
        assert "sections" in json_data
