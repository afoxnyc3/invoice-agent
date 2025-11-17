"""
Pydantic models for queue messages and Azure Table entities.

This module defines all data models used throughout the invoice processing pipeline:
- Queue message schemas for inter-function communication
- Azure Table Storage entity schemas
- Teams webhook message card format
"""

from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, Dict, Literal
from datetime import datetime


# =============================================================================
# QUEUE MESSAGE MODELS
# =============================================================================


class RawMail(BaseModel):
    """
    Message sent from MailIngest to ExtractEnrich via raw-mail queue.

    This model represents an email that has been received and had its
    attachment uploaded to blob storage, ready for vendor extraction.
    """

    id: str = Field(..., description="ULID transaction identifier")
    sender: EmailStr = Field(..., description="Email address of sender")
    subject: str = Field(..., description="Email subject line")
    blob_url: str = Field(..., description="URL to invoice PDF in blob storage")
    received_at: str = Field(..., description="ISO 8601 timestamp when email received")
    vendor_name: Optional[str] = Field(
        None, description="Vendor name extracted from invoice (optional, for future PDF automation)"
    )

    @validator("blob_url")
    def validate_url(cls, v):
        """Ensure blob URL uses HTTPS protocol"""
        if not v.startswith("https://"):
            raise ValueError("blob_url must be HTTPS")
        return v

    @validator("id")
    def validate_id(cls, v):
        """Ensure ID is not empty"""
        if not v or not v.strip():
            raise ValueError("id cannot be empty")
        return v


class EnrichedInvoice(BaseModel):
    """
    Message sent from ExtractEnrich to PostToAP via to-post queue.

    This model represents an invoice that has been enriched with vendor
    information from the VendorMaster table, ready to send to AP.
    """

    id: str = Field(..., description="ULID transaction identifier")
    vendor_name: str = Field(..., description="Vendor display name")
    expense_dept: str = Field(..., description="Department code (IT, SALES, HR, etc)")
    gl_code: str = Field(..., description="General ledger code (4 digits)")
    allocation_schedule: str = Field(..., description="Billing frequency (MONTHLY, ANNUAL, etc)")
    billing_party: str = Field(..., description="Entity responsible for payment")
    blob_url: str = Field(..., description="URL to invoice PDF in blob storage")
    status: Literal["enriched", "unknown"] = Field(..., description="Processing status")

    @validator("gl_code")
    def validate_gl_code(cls, v):
        """Ensure GL code is 4 digits"""
        if not v.isdigit() or len(v) != 4:
            raise ValueError("gl_code must be exactly 4 digits")
        return v

    @validator("vendor_name", "expense_dept", "billing_party")
    def validate_not_empty(cls, v):
        """Ensure critical fields are not empty"""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v


class NotificationMessage(BaseModel):
    """
    Message sent from PostToAP to Notify via notify queue.

    This model represents a notification to be sent to Teams webhook,
    with type-specific formatting for success, warning, or error messages.
    """

    type: Literal["success", "unknown", "error"] = Field(..., description="Notification type")
    message: str = Field(..., description="Human-readable summary message")
    details: Dict[str, str] = Field(..., description="Additional context for notification")

    @validator("details")
    def validate_details(cls, v, values):
        """Ensure required detail fields are present based on type"""
        if "type" in values:
            msg_type = values["type"]
            if msg_type in ["success", "unknown"] and "transaction_id" not in v:
                raise ValueError("transaction_id required in details")
        return v

    class Config:
        schema_extra = {
            "example": {
                "type": "success",
                "message": "Processed: Adobe Inc - GL 6100",
                "details": {
                    "vendor": "Adobe Inc",
                    "gl_code": "6100",
                    "transaction_id": "01JCK3Q7H8ZVXN3BARC9GWAEZM",
                },
            }
        }


# =============================================================================
# AZURE TABLE STORAGE ENTITY MODELS
# =============================================================================


class VendorMaster(BaseModel):
    """
    Vendor lookup table entity.

    This model represents a vendor record in Azure Table Storage,
    used for enriching invoices with GL codes and department allocation.

    Storage Pattern:
    - PartitionKey: Always "Vendor"
    - RowKey: normalized_vendor_name (e.g., "amazon_web_services", "microsoft")
    """

    PartitionKey: str = Field(default="Vendor", description="Always 'Vendor' for all records")
    RowKey: str = Field(..., description="Vendor name normalized (e.g., 'amazon_web_services')")
    VendorName: str = Field(..., description="Vendor display name for matching in invoices")
    ProductCategory: str = Field(..., description="'Direct' for direct vendors, 'Reseller' for VARs")
    ExpenseDept: str = Field(..., description="Department code (IT, SALES, HR, etc)")
    AllocationSchedule: str = Field(..., description="Allocation schedule code (numeric: 1, 3, 14, etc)")
    GLCode: str = Field(..., description="General ledger code (4 digits)")
    VenueRequired: bool = Field(default=False, description="True if venue extraction required")
    Active: bool = Field(default=True, description="Soft delete flag")
    UpdatedAt: str = Field(..., description="ISO 8601 timestamp of last update")

    @validator("GLCode")
    def validate_gl_code(cls, v):
        """Ensure GL code is exactly 4 digits"""
        if not v.isdigit() or len(v) != 4:
            raise ValueError("GLCode must be exactly 4 digits")
        return v

    @validator("ProductCategory")
    def validate_product_category(cls, v):
        """Ensure ProductCategory is Direct or Reseller"""
        if v not in ["Direct", "Reseller"]:
            raise ValueError("ProductCategory must be 'Direct' or 'Reseller'")
        return v

    @validator("RowKey")
    def validate_row_key(cls, v):
        """Ensure RowKey is normalized (lowercase, underscore-separated)"""
        if not v.islower() or " " in v:
            raise ValueError("RowKey must be lowercase with no spaces")
        return v


class InvoiceTransaction(BaseModel):
    """
    Transaction audit log table entity.

    This model represents a processed invoice transaction in Azure Table Storage,
    maintaining a complete audit trail for compliance and reporting.

    Includes email loop prevention fields to track emails sent and prevent
    duplicate processing of the same transaction.

    Storage Pattern:
    - PartitionKey: YYYYMM format (e.g., "202411") for efficient time-based queries
    - RowKey: ULID for unique, sortable transaction IDs
    """

    PartitionKey: str = Field(..., description="YYYYMM format (e.g., '202411')")
    RowKey: str = Field(..., description="ULID transaction identifier")
    VendorName: str = Field(..., description="Vendor name from enrichment")
    SenderEmail: EmailStr = Field(..., description="Original sender email address")
    RecipientEmail: EmailStr = Field(..., description="Email address where invoice was sent")
    ExpenseDept: str = Field(..., description="Department code")
    GLCode: str = Field(..., description="General ledger code")
    Status: Literal["processed", "unknown", "error"] = Field(..., description="Processing status")
    BlobUrl: str = Field(..., description="Full URL to invoice PDF in blob storage")
    ProcessedAt: str = Field(..., description="ISO 8601 timestamp of processing completion")
    ErrorMessage: Optional[str] = Field(default=None, description="Error details if status is 'error'")
    EmailsSentCount: int = Field(default=0, description="Number of emails sent to AP (prevents duplicates)")
    OriginalMessageId: Optional[str] = Field(
        default=None, description="Graph API message ID of invoice email (for dedup)"
    )
    LastEmailSentAt: Optional[str] = Field(default=None, description="ISO 8601 timestamp of last email sent")

    @validator("PartitionKey")
    def validate_partition_key(cls, v):
        """Ensure PartitionKey is in YYYYMM format"""
        if not v.isdigit() or len(v) != 6:
            raise ValueError("PartitionKey must be YYYYMM format (6 digits)")
        year = int(v[:4])
        month = int(v[4:])
        if year < 2020 or year > 2100 or month < 1 or month > 12:
            raise ValueError("Invalid year or month in PartitionKey")
        return v

    @validator("ErrorMessage", always=True)
    def validate_error_message(cls, v, values):
        """Ensure ErrorMessage is present when Status is 'error'"""
        if "Status" in values and values["Status"] == "error" and not v:
            raise ValueError("ErrorMessage required when Status is error")
        return v


# =============================================================================
# TEAMS WEBHOOK MESSAGE CARD MODELS
# =============================================================================


class MessageCardFact(BaseModel):
    """
    Individual name-value pair in a Teams message card.

    Used to display structured information in Teams notifications.
    """

    name: str = Field(..., description="Fact label")
    value: str = Field(..., description="Fact value")


class MessageCardSection(BaseModel):
    """
    Section containing facts in a Teams message card.

    Groups related facts together in the notification display.
    """

    facts: list[MessageCardFact] = Field(..., description="List of facts to display")


class TeamsMessageCard(BaseModel):
    """
    Teams webhook message card format (Office 365 Connector Card).

    This model represents the JSON structure expected by Teams incoming webhooks
    for displaying formatted notifications with color-coded themes.

    Theme Colors:
    - Green (00FF00): Success messages
    - Orange (FFA500): Warning messages (unknown vendors)
    - Red (FF0000): Error messages
    """

    type: str = Field(default="MessageCard", alias="@type")
    themeColor: str = Field(..., description="Hex color code (e.g., '00FF00')")
    text: str = Field(..., description="Card title/summary text")
    sections: list[MessageCardSection] = Field(..., description="Sections containing facts")

    @validator("themeColor")
    def validate_theme_color(cls, v):
        """Ensure theme color is valid hex code"""
        if not v or len(v) != 6 or not all(c in "0123456789ABCDEFabcdef" for c in v):
            raise ValueError("themeColor must be 6-digit hex code")
        return v.upper()

    class Config:
        allow_population_by_field_name = True
        schema_extra = {
            "example": {
                "@type": "MessageCard",
                "themeColor": "00FF00",
                "text": "✅ Invoice Processed",
                "sections": [
                    {
                        "facts": [
                            {"name": "Vendor", "value": "Adobe Inc"},
                            {"name": "GL Code", "value": "6100"},
                            {"name": "Department", "value": "IT"},
                        ]
                    }
                ],
            }
        }
