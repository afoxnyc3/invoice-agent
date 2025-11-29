"""
Edge case tests for Invoice Agent models and validation.

Tests cover:
- Unicode and international characters
- Boundary values (very long/short strings)
- Special characters in various fields
- Invalid data validation
"""

import pytest
from pydantic import ValidationError

from shared.models import (
    RawMail,
    EnrichedInvoice,
    NotificationMessage,
    VendorMaster,
    InvoiceTransaction,
)
from tests.fixtures.edge_cases import (
    VENDOR_EDGE_CASES,
    INVALID_VENDOR_CASES,
    EMAIL_EDGE_CASES,
    INVALID_EMAIL_CASES,
    RAW_MAIL_EDGE_CASES,
    ENRICHED_INVOICE_EDGE_CASES,
    INVALID_ENRICHED_CASES,
    PARTITION_KEY_EDGE_CASES,
    INVALID_PARTITION_KEY_CASES,
    BLOB_URL_EDGE_CASES,
    INVALID_BLOB_URL_CASES,
)


# =============================================================================
# VENDOR NAME EDGE CASE TESTS
# =============================================================================


class TestVendorEdgeCases:
    """Test vendor name handling with edge cases."""

    @pytest.mark.parametrize(
        "case",
        [c for c in VENDOR_EDGE_CASES if c.get("should_pass", True)],
        ids=[c["id"] for c in VENDOR_EDGE_CASES if c.get("should_pass", True)],
    )
    def test_valid_vendor_names(self, case: dict) -> None:
        """Test that valid vendor names are accepted."""
        invoice = EnrichedInvoice(
            id="01JCK3Q7H8ZVXN3BARC9GWAEZM",
            vendor_name=case["VendorName"],
            expense_dept=case["ExpenseDept"],
            gl_code=case["GLCode"],
            allocation_schedule="MONTHLY",
            billing_party="Company HQ",
            blob_url="https://storage.blob.core.windows.net/test.pdf",
            original_message_id="MSG123",
            status="enriched",
        )
        # Pydantic doesn't auto-strip whitespace
        assert invoice.vendor_name == case["VendorName"]

    @pytest.mark.parametrize(
        "case",
        INVALID_VENDOR_CASES,
        ids=[c["id"] for c in INVALID_VENDOR_CASES],
    )
    def test_invalid_vendor_data(self, case: dict) -> None:
        """Test that invalid vendor data raises validation errors."""
        with pytest.raises(ValidationError) as exc_info:
            EnrichedInvoice(
                id="01JCK3Q7H8ZVXN3BARC9GWAEZM",
                vendor_name=case["VendorName"],
                expense_dept=case["ExpenseDept"],
                gl_code=case["GLCode"],
                allocation_schedule="MONTHLY",
                billing_party="Company HQ",
                blob_url="https://storage.blob.core.windows.net/test.pdf",
                original_message_id="MSG123",
                status="enriched",
            )
        assert case["expected_error"].lower() in str(exc_info.value).lower()


# =============================================================================
# EMAIL EDGE CASE TESTS
# =============================================================================


class TestEmailEdgeCases:
    """Test email address handling with edge cases."""

    @pytest.mark.parametrize(
        "case",
        [c for c in EMAIL_EDGE_CASES if c.get("should_pass", True)],
        ids=[c["id"] for c in EMAIL_EDGE_CASES if c.get("should_pass", True)],
    )
    def test_valid_emails(self, case: dict) -> None:
        """Test that valid email addresses are accepted."""
        raw_mail = RawMail(
            id="01JCK3Q7H8ZVXN3BARC9GWAEZM",
            sender=case["email"],
            subject="Test Invoice",
            blob_url="https://storage.blob.core.windows.net/test.pdf",
            received_at="2024-11-09T10:00:00Z",
            original_message_id="MSG123",
        )
        assert raw_mail.sender == case["email"]

    @pytest.mark.parametrize(
        "case",
        INVALID_EMAIL_CASES,
        ids=[c["id"] for c in INVALID_EMAIL_CASES],
    )
    def test_invalid_emails(self, case: dict) -> None:
        """Test that invalid email addresses raise validation errors."""
        with pytest.raises(ValidationError) as exc_info:
            RawMail(
                id="01JCK3Q7H8ZVXN3BARC9GWAEZM",
                sender=case["email"],
                subject="Test Invoice",
                blob_url="https://storage.blob.core.windows.net/test.pdf",
                received_at="2024-11-09T10:00:00Z",
                original_message_id="MSG123",
            )
        assert case["expected_error"].lower() in str(exc_info.value).lower()


# =============================================================================
# RAW MAIL EDGE CASE TESTS
# =============================================================================


class TestRawMailEdgeCases:
    """Test RawMail model with edge cases."""

    @pytest.mark.parametrize(
        "case",
        [c for c in RAW_MAIL_EDGE_CASES if c.get("should_pass", True)],
        ids=[c["id"] for c in RAW_MAIL_EDGE_CASES if c.get("should_pass", True)],
    )
    def test_valid_raw_mail(self, case: dict) -> None:
        """Test that valid RawMail messages are accepted."""
        raw_mail = RawMail(
            id="01JCK3Q7H8ZVXN3BARC9GWAEZM",
            sender=case["sender"],
            subject=case["subject"],
            blob_url="https://storage.blob.core.windows.net/test.pdf",
            received_at="2024-11-09T10:00:00Z",
            original_message_id="MSG123",
        )
        assert raw_mail.subject == case["subject"]

    def test_empty_id_rejected(self) -> None:
        """Test that empty transaction ID is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            RawMail(
                id="",
                sender="billing@company.com",
                subject="Test Invoice",
                blob_url="https://storage.blob.core.windows.net/test.pdf",
                received_at="2024-11-09T10:00:00Z",
                original_message_id="MSG123",
            )
        assert "cannot be empty" in str(exc_info.value).lower()

    def test_whitespace_id_rejected(self) -> None:
        """Test that whitespace-only transaction ID is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            RawMail(
                id="   ",
                sender="billing@company.com",
                subject="Test Invoice",
                blob_url="https://storage.blob.core.windows.net/test.pdf",
                received_at="2024-11-09T10:00:00Z",
                original_message_id="MSG123",
            )
        assert "cannot be empty" in str(exc_info.value).lower()


# =============================================================================
# ENRICHED INVOICE EDGE CASE TESTS
# =============================================================================


class TestEnrichedInvoiceEdgeCases:
    """Test EnrichedInvoice model with edge cases."""

    @pytest.mark.parametrize(
        "case",
        [c for c in ENRICHED_INVOICE_EDGE_CASES if c.get("should_pass", True)],
        ids=[c["id"] for c in ENRICHED_INVOICE_EDGE_CASES if c.get("should_pass", True)],
    )
    def test_valid_invoice_amounts(self, case: dict) -> None:
        """Test that valid invoice amounts are accepted."""
        invoice = EnrichedInvoice(
            id="01JCK3Q7H8ZVXN3BARC9GWAEZM",
            vendor_name="Test Vendor",
            expense_dept="IT",
            gl_code="6100",
            allocation_schedule="MONTHLY",
            billing_party="Company HQ",
            blob_url="https://storage.blob.core.windows.net/test.pdf",
            original_message_id="MSG123",
            status="enriched",
            invoice_amount=case["invoice_amount"],
            currency=case.get("currency", "USD"),
        )
        assert invoice.invoice_amount == case["invoice_amount"]

    @pytest.mark.parametrize(
        "case",
        INVALID_ENRICHED_CASES,
        ids=[c["id"] for c in INVALID_ENRICHED_CASES],
    )
    def test_invalid_invoice_amounts(self, case: dict) -> None:
        """Test that invalid invoice amounts raise validation errors."""
        with pytest.raises(ValidationError) as exc_info:
            EnrichedInvoice(
                id="01JCK3Q7H8ZVXN3BARC9GWAEZM",
                vendor_name="Test Vendor",
                expense_dept="IT",
                gl_code="6100",
                allocation_schedule="MONTHLY",
                billing_party="Company HQ",
                blob_url="https://storage.blob.core.windows.net/test.pdf",
                original_message_id="MSG123",
                status="enriched",
                invoice_amount=case["invoice_amount"],
                currency=case.get("currency", "USD"),
            )
        assert case["expected_error"].lower() in str(exc_info.value).lower()


# =============================================================================
# PARTITION KEY EDGE CASE TESTS
# =============================================================================


class TestPartitionKeyEdgeCases:
    """Test InvoiceTransaction partition key validation."""

    @pytest.mark.parametrize(
        "case",
        [c for c in PARTITION_KEY_EDGE_CASES if c.get("should_pass", True)],
        ids=[c["id"] for c in PARTITION_KEY_EDGE_CASES if c.get("should_pass", True)],
    )
    def test_valid_partition_keys(self, case: dict) -> None:
        """Test that valid partition keys are accepted."""
        transaction = InvoiceTransaction(
            PartitionKey=case["partition_key"],
            RowKey="01JCK3Q7H8ZVXN3BARC9GWAEZM",
            VendorName="Test Vendor",
            SenderEmail="billing@company.com",
            RecipientEmail="ap@company.com",
            ExpenseDept="IT",
            GLCode="6100",
            Status="processed",
            BlobUrl="https://storage.blob.core.windows.net/test.pdf",
            ProcessedAt="2024-11-09T10:00:00Z",
        )
        assert transaction.PartitionKey == case["partition_key"]

    @pytest.mark.parametrize(
        "case",
        INVALID_PARTITION_KEY_CASES,
        ids=[c["id"] for c in INVALID_PARTITION_KEY_CASES],
    )
    def test_invalid_partition_keys(self, case: dict) -> None:
        """Test that invalid partition keys raise validation errors."""
        with pytest.raises(ValidationError) as exc_info:
            InvoiceTransaction(
                PartitionKey=case["partition_key"],
                RowKey="01JCK3Q7H8ZVXN3BARC9GWAEZM",
                VendorName="Test Vendor",
                SenderEmail="billing@company.com",
                RecipientEmail="ap@company.com",
                ExpenseDept="IT",
                GLCode="6100",
                Status="processed",
                BlobUrl="https://storage.blob.core.windows.net/test.pdf",
                ProcessedAt="2024-11-09T10:00:00Z",
            )
        assert case["expected_error"].lower() in str(exc_info.value).lower()


# =============================================================================
# BLOB URL EDGE CASE TESTS
# =============================================================================


class TestBlobUrlEdgeCases:
    """Test blob URL validation with edge cases."""

    @pytest.mark.parametrize(
        "case",
        [c for c in BLOB_URL_EDGE_CASES if c.get("should_pass", True)],
        ids=[c["id"] for c in BLOB_URL_EDGE_CASES if c.get("should_pass", True)],
    )
    def test_valid_blob_urls(self, case: dict) -> None:
        """Test that valid blob URLs are accepted."""
        raw_mail = RawMail(
            id="01JCK3Q7H8ZVXN3BARC9GWAEZM",
            sender="billing@company.com",
            subject="Test Invoice",
            blob_url=case["url"],
            received_at="2024-11-09T10:00:00Z",
            original_message_id="MSG123",
        )
        assert raw_mail.blob_url == case["url"]

    @pytest.mark.parametrize(
        "case",
        INVALID_BLOB_URL_CASES,
        ids=[c["id"] for c in INVALID_BLOB_URL_CASES],
    )
    def test_invalid_blob_urls(self, case: dict) -> None:
        """Test that invalid blob URLs raise validation errors."""
        with pytest.raises(ValidationError) as exc_info:
            RawMail(
                id="01JCK3Q7H8ZVXN3BARC9GWAEZM",
                sender="billing@company.com",
                subject="Test Invoice",
                blob_url=case["url"],
                received_at="2024-11-09T10:00:00Z",
                original_message_id="MSG123",
            )
        assert case["expected_error"].lower() in str(exc_info.value).lower()


# =============================================================================
# NOTIFICATION MESSAGE EDGE CASE TESTS
# =============================================================================


class TestNotificationEdgeCases:
    """Test NotificationMessage model with edge cases."""

    def test_success_requires_transaction_id(self) -> None:
        """Test that success notification requires transaction_id."""
        with pytest.raises(ValidationError) as exc_info:
            NotificationMessage(
                type="success",
                message="Processed invoice",
                details={"vendor": "Test"},  # Missing transaction_id
            )
        assert "transaction_id required" in str(exc_info.value).lower()

    def test_unknown_requires_transaction_id(self) -> None:
        """Test that unknown notification requires transaction_id."""
        with pytest.raises(ValidationError) as exc_info:
            NotificationMessage(
                type="unknown",
                message="Unknown vendor",
                details={"sender": "test@company.com"},  # Missing transaction_id
            )
        assert "transaction_id required" in str(exc_info.value).lower()

    def test_error_does_not_require_transaction_id(self) -> None:
        """Test that error notification does not require transaction_id."""
        notification = NotificationMessage(
            type="error",
            message="Processing failed",
            details={"error": "Connection timeout"},
        )
        assert notification.type == "error"

    def test_duplicate_type_accepted(self) -> None:
        """Test that duplicate notification type is accepted."""
        notification = NotificationMessage(
            type="duplicate",
            message="Duplicate invoice detected",
            details={"original_id": "01JCK3Q7H8ZVXN3BARC9GWAEZM"},
        )
        assert notification.type == "duplicate"

    def test_unicode_in_message(self) -> None:
        """Test that unicode characters in message are accepted."""
        notification = NotificationMessage(
            type="success",
            message="処理完了: Adobe Inc - GL 6100",  # Japanese
            details={"transaction_id": "01JCK3Q7H8ZVXN3BARC9GWAEZM"},
        )
        assert "処理完了" in notification.message

    def test_very_long_message(self) -> None:
        """Test that very long messages are accepted."""
        notification = NotificationMessage(
            type="success",
            message="A" * 1000,  # 1000 character message
            details={"transaction_id": "01JCK3Q7H8ZVXN3BARC9GWAEZM"},
        )
        assert len(notification.message) == 1000


# =============================================================================
# VENDOR MASTER EDGE CASE TESTS
# =============================================================================


class TestVendorMasterEdgeCases:
    """Test VendorMaster model with edge cases."""

    def test_valid_vendor_master(self) -> None:
        """Test valid VendorMaster entity."""
        vendor = VendorMaster(
            RowKey="adobe_systems",
            VendorName="Adobe Systems",
            ProductCategory="Direct",
            ExpenseDept="IT",
            AllocationSchedule="1",
            GLCode="6100",
            UpdatedAt="2024-11-09T10:00:00Z",
        )
        assert vendor.VendorName == "Adobe Systems"

    def test_row_key_must_be_lowercase(self) -> None:
        """Test that RowKey must be lowercase."""
        with pytest.raises(ValidationError) as exc_info:
            VendorMaster(
                RowKey="Adobe_Systems",  # Uppercase not allowed
                VendorName="Adobe Systems",
                ProductCategory="Direct",
                ExpenseDept="IT",
                AllocationSchedule="1",
                GLCode="6100",
                UpdatedAt="2024-11-09T10:00:00Z",
            )
        assert "lowercase" in str(exc_info.value).lower()

    def test_row_key_no_spaces(self) -> None:
        """Test that RowKey cannot have spaces."""
        with pytest.raises(ValidationError) as exc_info:
            VendorMaster(
                RowKey="adobe systems",  # Spaces not allowed
                VendorName="Adobe Systems",
                ProductCategory="Direct",
                ExpenseDept="IT",
                AllocationSchedule="1",
                GLCode="6100",
                UpdatedAt="2024-11-09T10:00:00Z",
            )
        assert "no spaces" in str(exc_info.value).lower()

    def test_product_category_direct(self) -> None:
        """Test that Direct ProductCategory is valid."""
        vendor = VendorMaster(
            RowKey="vendor_direct",
            VendorName="Direct Vendor",
            ProductCategory="Direct",
            ExpenseDept="IT",
            AllocationSchedule="1",
            GLCode="6100",
            UpdatedAt="2024-11-09T10:00:00Z",
        )
        assert vendor.ProductCategory == "Direct"

    def test_product_category_reseller(self) -> None:
        """Test that Reseller ProductCategory is valid."""
        vendor = VendorMaster(
            RowKey="vendor_reseller",
            VendorName="Reseller Vendor",
            ProductCategory="Reseller",
            ExpenseDept="IT",
            AllocationSchedule="1",
            GLCode="6100",
            UpdatedAt="2024-11-09T10:00:00Z",
        )
        assert vendor.ProductCategory == "Reseller"

    def test_invalid_product_category(self) -> None:
        """Test that invalid ProductCategory is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            VendorMaster(
                RowKey="vendor_invalid",
                VendorName="Invalid Vendor",
                ProductCategory="Partner",  # Invalid
                ExpenseDept="IT",
                AllocationSchedule="1",
                GLCode="6100",
                UpdatedAt="2024-11-09T10:00:00Z",
            )
        assert "direct" in str(exc_info.value).lower() or "reseller" in str(exc_info.value).lower()
