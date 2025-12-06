"""
Tests for schema versioning in queue message models.

This module ensures all queue message models support schema versioning
for forward/backward compatibility during rolling deployments.
"""

import json
from shared.models import RawMail, EnrichedInvoice, NotificationMessage


class TestRawMailSchemaVersion:
    """Tests for RawMail schema versioning."""

    def test_rawmail_default_schema_version(self):
        """Test that RawMail includes schema_version 1.0 by default."""
        raw_mail = RawMail(
            id="01JCK3Q7H8ZVXN3BARC9GWAEZM",
            sender="vendor@example.com",
            subject="Invoice #12345",
            blob_url="https://storage.blob.core.windows.net/invoices/test.pdf",
            received_at="2024-12-01T10:00:00Z",
            original_message_id="AAMkAGZjOTlkNjQyLWQ5ZjAtNGQ0Zi1iMGE4LWFmZjBjMGQ4YzUwNQBGAAAAAABQYw",
        )
        assert raw_mail.schema_version == "1.0"

    def test_rawmail_backward_compat_no_version(self):
        """Test that old JSON messages without schema_version still parse correctly."""
        old_message = {
            "id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
            "sender": "vendor@example.com",
            "subject": "Invoice #12345",
            "blob_url": "https://storage.blob.core.windows.net/invoices/test.pdf",
            "received_at": "2024-12-01T10:00:00Z",
            "original_message_id": "AAMkAGZjOTlkNjQyLWQ5ZjAtNGQ0Zi1iMGE4LWFmZjBjMGQ4YzUwNQBGAAAAAABQYw",
        }
        # Should parse successfully with default schema_version
        raw_mail = RawMail.model_validate(old_message)
        assert raw_mail.schema_version == "1.0"
        assert raw_mail.id == "01JCK3Q7H8ZVXN3BARC9GWAEZM"

    def test_rawmail_schema_version_serialization(self):
        """Test that schema_version appears in JSON output."""
        raw_mail = RawMail(
            id="01JCK3Q7H8ZVXN3BARC9GWAEZM",
            sender="vendor@example.com",
            subject="Invoice #12345",
            blob_url="https://storage.blob.core.windows.net/invoices/test.pdf",
            received_at="2024-12-01T10:00:00Z",
            original_message_id="AAMkAGZjOTlkNjQyLWQ5ZjAtNGQ0Zi1iMGE4LWFmZjBjMGQ4YzUwNQBGAAAAAABQYw",
        )
        json_output = json.loads(raw_mail.model_dump_json())
        assert "schema_version" in json_output
        assert json_output["schema_version"] == "1.0"

    def test_rawmail_explicit_version_override(self):
        """Test that schema_version can be explicitly set (for future versions)."""
        raw_mail = RawMail(
            schema_version="2.0",
            id="01JCK3Q7H8ZVXN3BARC9GWAEZM",
            sender="vendor@example.com",
            subject="Invoice #12345",
            blob_url="https://storage.blob.core.windows.net/invoices/test.pdf",
            received_at="2024-12-01T10:00:00Z",
            original_message_id="AAMkAGZjOTlkNjQyLWQ5ZjAtNGQ0Zi1iMGE4LWFmZjBjMGQ4YzUwNQBGAAAAAABQYw",
        )
        assert raw_mail.schema_version == "2.0"


class TestEnrichedInvoiceSchemaVersion:
    """Tests for EnrichedInvoice schema versioning."""

    def test_enrichedinvoice_default_schema_version(self):
        """Test that EnrichedInvoice includes schema_version 1.0 by default."""
        enriched = EnrichedInvoice(
            id="01JCK3Q7H8ZVXN3BARC9GWAEZM",
            vendor_name="Adobe Inc",
            expense_dept="IT",
            gl_code="6100",
            allocation_schedule="MONTHLY",
            billing_party="Acme Corp",
            blob_url="https://storage.blob.core.windows.net/invoices/test.pdf",
            original_message_id="AAMkAGZjOTlkNjQyLWQ5ZjAtNGQ0Zi1iMGE4LWFmZjBjMGQ4YzUwNQBGAAAAAABQYw",
            status="enriched",
        )
        assert enriched.schema_version == "1.0"

    def test_enrichedinvoice_backward_compat_no_version(self):
        """Test that old JSON messages without schema_version still parse correctly."""
        old_message = {
            "id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
            "vendor_name": "Adobe Inc",
            "expense_dept": "IT",
            "gl_code": "6100",
            "allocation_schedule": "MONTHLY",
            "billing_party": "Acme Corp",
            "blob_url": "https://storage.blob.core.windows.net/invoices/test.pdf",
            "original_message_id": "AAMkAGZjOTlkNjQyLWQ5ZjAtNGQ0Zi1iMGE4LWFmZjBjMGQ4YzUwNQBGAAAAAABQYw",
            "status": "enriched",
        }
        # Should parse successfully with default schema_version
        enriched = EnrichedInvoice.model_validate(old_message)
        assert enriched.schema_version == "1.0"
        assert enriched.vendor_name == "Adobe Inc"

    def test_enrichedinvoice_schema_version_serialization(self):
        """Test that schema_version appears in JSON output."""
        enriched = EnrichedInvoice(
            id="01JCK3Q7H8ZVXN3BARC9GWAEZM",
            vendor_name="Adobe Inc",
            expense_dept="IT",
            gl_code="6100",
            allocation_schedule="MONTHLY",
            billing_party="Acme Corp",
            blob_url="https://storage.blob.core.windows.net/invoices/test.pdf",
            original_message_id="AAMkAGZjOTlkNjQyLWQ5ZjAtNGQ0Zi1iMGE4LWFmZjBjMGQ4YzUwNQBGAAAAAABQYw",
            status="enriched",
        )
        json_output = json.loads(enriched.model_dump_json())
        assert "schema_version" in json_output
        assert json_output["schema_version"] == "1.0"

    def test_enrichedinvoice_explicit_version_override(self):
        """Test that schema_version can be explicitly set (for future versions)."""
        enriched = EnrichedInvoice(
            schema_version="2.0",
            id="01JCK3Q7H8ZVXN3BARC9GWAEZM",
            vendor_name="Adobe Inc",
            expense_dept="IT",
            gl_code="6100",
            allocation_schedule="MONTHLY",
            billing_party="Acme Corp",
            blob_url="https://storage.blob.core.windows.net/invoices/test.pdf",
            original_message_id="AAMkAGZjOTlkNjQyLWQ5ZjAtNGQ0Zi1iMGE4LWFmZjBjMGQ4YzUwNQBGAAAAAABQYw",
            status="enriched",
        )
        assert enriched.schema_version == "2.0"


class TestNotificationMessageSchemaVersion:
    """Tests for NotificationMessage schema versioning."""

    def test_notification_default_schema_version(self):
        """Test that NotificationMessage includes schema_version 1.0 by default."""
        notification = NotificationMessage(
            type="success",
            message="Processed: Adobe Inc - GL 6100",
            details={
                "vendor": "Adobe Inc",
                "gl_code": "6100",
                "transaction_id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
            },
        )
        assert notification.schema_version == "1.0"

    def test_notification_backward_compat_no_version(self):
        """Test that old JSON messages without schema_version still parse correctly."""
        old_message = {
            "type": "success",
            "message": "Processed: Adobe Inc - GL 6100",
            "details": {
                "vendor": "Adobe Inc",
                "gl_code": "6100",
                "transaction_id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
            },
        }
        # Should parse successfully with default schema_version
        notification = NotificationMessage.model_validate(old_message)
        assert notification.schema_version == "1.0"
        assert notification.message == "Processed: Adobe Inc - GL 6100"

    def test_notification_schema_version_serialization(self):
        """Test that schema_version appears in JSON output."""
        notification = NotificationMessage(
            type="success",
            message="Processed: Adobe Inc - GL 6100",
            details={
                "vendor": "Adobe Inc",
                "gl_code": "6100",
                "transaction_id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
            },
        )
        json_output = json.loads(notification.model_dump_json())
        assert "schema_version" in json_output
        assert json_output["schema_version"] == "1.0"

    def test_notification_explicit_version_override(self):
        """Test that schema_version can be explicitly set (for future versions)."""
        notification = NotificationMessage(
            schema_version="2.0",
            type="success",
            message="Processed: Adobe Inc - GL 6100",
            details={
                "vendor": "Adobe Inc",
                "gl_code": "6100",
                "transaction_id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
            },
        )
        assert notification.schema_version == "2.0"


class TestSchemaVersionCrossModelCompatibility:
    """Tests for schema version compatibility across the processing pipeline."""

    def test_pipeline_message_flow_with_schema_versions(self):
        """Test that messages flow through pipeline with schema_version preserved."""
        # RawMail (MailIngest -> ExtractEnrich)
        raw_mail = RawMail(
            id="01JCK3Q7H8ZVXN3BARC9GWAEZM",
            sender="vendor@example.com",
            subject="Invoice #12345",
            blob_url="https://storage.blob.core.windows.net/invoices/test.pdf",
            received_at="2024-12-01T10:00:00Z",
            original_message_id="AAMkAGZjOTlkNjQyLWQ5ZjAtNGQ0Zi1iMGE4LWFmZjBjMGQ4YzUwNQBGAAAAAABQYw",
        )
        assert raw_mail.schema_version == "1.0"

        # EnrichedInvoice (ExtractEnrich -> PostToAP)
        enriched = EnrichedInvoice(
            id=raw_mail.id,
            vendor_name="Adobe Inc",
            expense_dept="IT",
            gl_code="6100",
            allocation_schedule="MONTHLY",
            billing_party="Acme Corp",
            blob_url=raw_mail.blob_url,
            original_message_id=raw_mail.original_message_id,
            status="enriched",
        )
        assert enriched.schema_version == "1.0"

        # NotificationMessage (PostToAP -> Notify)
        notification = NotificationMessage(
            type="success",
            message=f"Processed: {enriched.vendor_name} - GL {enriched.gl_code}",
            details={
                "vendor": enriched.vendor_name,
                "gl_code": enriched.gl_code,
                "transaction_id": enriched.id,
            },
        )
        assert notification.schema_version == "1.0"

    def test_old_messages_in_flight_during_deployment(self):
        """Test that old messages (no schema_version) can coexist with new messages."""
        # Simulate old message in queue (no schema_version field)
        old_raw_json = json.dumps(
            {
                "id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
                "sender": "vendor@example.com",
                "subject": "Invoice #12345",
                "blob_url": "https://storage.blob.core.windows.net/invoices/test.pdf",
                "received_at": "2024-12-01T10:00:00Z",
                "original_message_id": "AAMkAGZjOTlkNjQyLWQ5ZjAtNGQ0Zi1iMGE4LWFmZjBjMGQ4YzUwNQBGAAAAAABQYw",
            }
        )

        # New function instance should parse old message successfully
        old_raw_mail = RawMail.model_validate_json(old_raw_json)
        assert old_raw_mail.schema_version == "1.0"  # Default applied

        # Simulate new message in queue (has schema_version field)
        new_raw_json = json.dumps(
            {
                "schema_version": "1.0",
                "id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
                "sender": "vendor@example.com",
                "subject": "Invoice #12345",
                "blob_url": "https://storage.blob.core.windows.net/invoices/test.pdf",
                "received_at": "2024-12-01T10:00:00Z",
                "original_message_id": "AAMkAGZjOTlkNjQyLWQ5ZjAtNGQ0Zi1iMGE4LWFmZjBjMGQ4YzUwNQBGAAAAAABQYw",
            }
        )

        # Function instance should parse new message successfully
        new_raw_mail = RawMail.model_validate_json(new_raw_json)
        assert new_raw_mail.schema_version == "1.0"

        # Both should have identical data
        assert old_raw_mail.id == new_raw_mail.id
        assert old_raw_mail.sender == new_raw_mail.sender
