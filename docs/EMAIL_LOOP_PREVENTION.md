# Email Loop Prevention Strategy

**Status:** CRITICAL - Must implement before production testing
**Created:** 2024-11-16
**Priority:** P0 (Blocking)

---

## Executive Summary

Analysis of the invoice-agent codebase has revealed **CRITICAL email loop vulnerabilities** with NO current safeguards. The system is configured to send emails TO the same mailbox it reads FROM, creating an infinite loop that would exponentially generate emails (1 → 12/hr → 288/day → 8,640/month).

**Risk Level:** CRITICAL - System will fail catastrophically on first test
**Blast Radius:** Entire email infrastructure, potential mailbox quota exhaustion
**Time to Implement:** 2-4 hours for immediate safeguards

---

## The Critical Problem

### Infrastructure Misconfiguration

**File:** `infrastructure/bicep/modules/functionapp.bicep` (Lines 129-132)

```bicep
{
  name: 'INVOICE_MAILBOX'
  value: '@Microsoft.KeyVault(SecretUri=https://${keyVaultName}.vault.azure.net/secrets/ap-email-address/)'
}
```

**CRITICAL ISSUE:** Both `INVOICE_MAILBOX` and `AP_EMAIL_ADDRESS` point to the **SAME** Key Vault secret (`ap-email-address`).

```
INVOICE_MAILBOX = AP_EMAIL_ADDRESS = accountspayable@chelseapiers.com
```

### Email Loop Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Vendor sends invoice                                     │
│    FROM: billing@adobe.com                                  │
│    TO: accountspayable@chelseapiers.com                     │
│    ATTACHMENT: invoice.pdf                                  │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. MailIngest (Timer: 0 */5 * * * *)                       │
│    - Reads unread emails from accountspayable@              │
│    - NO sender filtering                                    │
│    - NO subject pattern detection                           │
│    - Processes email → Queue                                │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. ExtractEnrich → PostToAP                                 │
│    - Enriches with GL codes                                 │
│    - Sends email:                                           │
│      FROM: accountspayable@chelseapiers.com                 │
│      TO: accountspayable@chelseapiers.com ← SAME MAILBOX!   │
│      SUBJECT: "Invoice: Adobe Inc - GL 6100"                │
│      ATTACHMENT: invoice.pdf                                │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. 5 minutes later: MailIngest runs again                   │
│    - Finds NEW unread email (the one we just sent)          │
│    - NO CHECK if sender is system                           │
│    - Processes SAME invoice again                           │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. INFINITE LOOP                                            │
│    - Cycle 1: 1 email sent                                  │
│    - Cycle 2: 1 email sent (processing cycle 1's email)     │
│    - Cycle 3: 1 email sent (processing cycle 2's email)     │
│    - Growth: 12 emails/hour → 288/day → 8,640/month         │
│    - Mailbox quota exhaustion in ~3-7 days                  │
└─────────────────────────────────────────────────────────────┘
```

---

## Current Safeguards Analysis

### ❌ No Safeguards Found

| Defense Layer | Status | Location | Issue |
|---------------|--------|----------|-------|
| Sender Filtering | ❌ NOT IMPLEMENTED | MailIngest | No check if `sender == INVOICE_MAILBOX` |
| Subject Pattern Detection | ❌ NOT IMPLEMENTED | MailIngest | No regex to detect system subjects |
| Transaction Deduplication | ❌ NOT IMPLEMENTED | PostToAP | No query to check if transaction exists |
| Email Sent Counter | ❌ NOT IMPLEMENTED | Models | `InvoiceTransaction` has no `EmailsSentCount` |
| Recipient Validation | ❌ NOT IMPLEMENTED | PostToAP | No validation of `to_address` |
| Attachment Type Filtering | ⚠️ PARTIAL | MailIngest | Requires attachments, but PostToAP sends PDF |

---

## Vulnerability Details

### Vulnerability 1: Same Mailbox for Send/Receive (CRITICAL)

**Severity:** CRITICAL
**Likelihood:** 100% on first test
**Impact:** System failure, email storm

**Evidence:**
```python
# infrastructure/bicep/modules/functionapp.bicep:129-132
{
  name: 'INVOICE_MAILBOX'
  value: '@Microsoft.KeyVault(SecretUri=https://${keyVaultName}.vault.azure.net/secrets/ap-email-address/)'
}

# Same secret used for both:
INVOICE_MAILBOX → ap-email-address
AP_EMAIL_ADDRESS → ap-email-address
```

**Fix Required:** Use separate Key Vault secrets or add runtime validation.

---

### Vulnerability 2: No Sender Filtering (CRITICAL)

**Severity:** CRITICAL
**Likelihood:** 100% when Vuln 1 present
**Impact:** Infinite loop triggered

**Evidence:**
```python
# src/functions/MailIngest/__init__.py:51-60
emails = graph.get_unread_emails(mailbox, max_results=50)
for email in emails:
    if not email.get("hasAttachments"):
        # Skip - no filtering on sender
        continue
    _process_email(email, graph, mailbox, blob_container, outQueueItem)
```

**Missing Check:**
```python
sender = email['sender']['emailAddress']['address'].lower()
if sender == os.environ["INVOICE_MAILBOX"].lower():
    logger.info(f"Skipping system-sent email {email['id']}")
    graph.mark_as_read(mailbox, email["id"])
    continue
```

---

### Vulnerability 3: No Transaction Deduplication (HIGH)

**Severity:** HIGH
**Likelihood:** 100% on re-processing
**Impact:** Duplicate emails to AP, incorrect audit trail

**Evidence:**
```python
# src/functions/PostToAP/__init__.py:67-85
# No check if transaction already processed
graph.send_email(...)
_log_transaction(enriched)
```

**Missing Check:**
```python
# Query InvoiceTransactions table first
try:
    existing = table_client.get_entity(
        partition_key=datetime.utcnow().strftime("%Y%m"),
        row_key=enriched.id
    )
    if existing.get('Status') == 'processed':
        logger.warning(f"Transaction {enriched.id} already processed")
        return
except ResourceNotFoundError:
    pass  # New transaction, proceed
```

---

### Vulnerability 4: No Subject Pattern Detection (HIGH)

**Severity:** HIGH
**Likelihood:** 100% when system emails re-ingested
**Impact:** Cannot distinguish system emails from vendor emails

**Evidence:**
```python
# src/functions/MailIngest/__init__.py
# No subject filtering before processing
```

**System Email Pattern:**
```
Subject: "Invoice: {VendorName} - GL {GLCode}"
Example: "Invoice: Adobe Inc - GL 6100"
```

**Missing Check:**
```python
import re
if re.match(r"^Invoice:\s+.+\s+-\s+GL\s+\d{4}$", email['subject']):
    logger.info(f"Skipping system-generated email {email['id']}")
    graph.mark_as_read(mailbox, email["id"])
    continue
```

---

### Vulnerability 5: No Email Sent Tracking (HIGH)

**Severity:** HIGH
**Likelihood:** 100% on multiple processing attempts
**Impact:** Multiple emails sent to AP for same invoice

**Evidence:**
```python
# src/shared/models.py:169-209
class InvoiceTransaction(BaseModel):
    # ... fields ...
    Status: Literal["processed", "unknown", "error"]
    # MISSING: EmailsSentCount, RecipientEmail
```

**Required Fields:**
```python
EmailsSentCount: int = Field(default=0, description="Number of emails sent to AP")
RecipientEmail: EmailStr = Field(..., description="Email address where invoice was sent")
OriginalMessageId: Optional[str] = Field(None, description="Graph API message ID for dedup")
```

---

### Vulnerability 6: No Recipient Validation (MEDIUM)

**Severity:** MEDIUM
**Likelihood:** LOW (requires config error)
**Impact:** Emails sent to wrong recipient, data leak

**Evidence:**
```python
# src/functions/PostToAP/__init__.py:72-85
graph.send_email(
    from_address=os.environ["INVOICE_MAILBOX"],
    to_address=os.environ["AP_EMAIL_ADDRESS"],  # No validation
    # ...
)
```

**Missing Validation:**
```python
# Validate recipient is not the ingest mailbox
if to_address.lower() == os.environ["INVOICE_MAILBOX"].lower():
    raise ValueError("Cannot send to INVOICE_MAILBOX - loop prevention")

# Validate recipient is in allowed list
ALLOWED_RECIPIENTS = os.environ.get("ALLOWED_AP_EMAILS", "").split(",")
if to_address not in ALLOWED_RECIPIENTS:
    raise ValueError(f"Recipient {to_address} not in allowed list")
```

---

### Vulnerability 7: Vendor Registration Email Replies (MEDIUM)

**Severity:** MEDIUM
**Likelihood:** 30% (requires vendor action)
**Impact:** Registration response triggers re-processing

**Flow:**
```
1. Unknown vendor sends invoice
   ↓
2. ExtractEnrich sends registration email TO vendor
   FROM accountspayable@chelseapiers.com
   ↓
3. Vendor replies to registration email
   TO accountspayable@chelseapiers.com
   ↓
4. MailIngest processes reply as new invoice (if has attachment)
   ↓
5. Another unknown vendor email sent
```

**Fix:** Add subject pattern for registration emails, skip "Re:" subjects.

---

## Multi-Layer Defense Strategy

### Layer 1: Sender Filtering (MailIngest) - IMMEDIATE

**Priority:** P0 (Critical)
**Effort:** 30 minutes
**Testing:** Unit test + Integration test

**Implementation:**
```python
# src/functions/MailIngest/__init__.py

def _should_skip_email(email: dict, invoice_mailbox: str) -> tuple[bool, str]:
    """
    Determine if email should be skipped to prevent loops.

    Returns: (should_skip, reason)
    """
    sender = email.get('sender', {}).get('emailAddress', {}).get('address', '').lower()
    subject = email.get('subject', '')

    # Skip emails from our own mailbox (loop prevention)
    if sender == invoice_mailbox.lower():
        return True, f"sender is system mailbox ({sender})"

    # Skip system-generated email patterns
    if re.match(r"^Invoice:\s+.+\s+-\s+GL\s+\d{4}$", subject):
        return True, f"system-generated subject pattern ({subject})"

    # Skip replies to registration emails
    if subject.lower().startswith("re:") and "vendor registration" in subject.lower():
        return True, f"reply to registration email ({subject})"

    return False, ""


# In main loop:
for email in emails:
    should_skip, reason = _should_skip_email(email, mailbox)
    if should_skip:
        logger.info(f"Skipping email {email['id']}: {reason}")
        graph.mark_as_read(mailbox, email["id"])
        continue

    if not email.get("hasAttachments"):
        logger.warning(f"Skipping email {email['id']} - no attachments")
        graph.mark_as_read(mailbox, email["id"])
        continue

    _process_email(email, graph, mailbox, blob_container, outQueueItem)
```

**Tests Required:**
- `test_mail_ingest_skips_system_sent_emails`
- `test_mail_ingest_skips_system_subject_patterns`
- `test_mail_ingest_skips_registration_replies`

---

### Layer 2: Transaction Deduplication (PostToAP) - IMMEDIATE

**Priority:** P0 (Critical)
**Effort:** 45 minutes
**Testing:** Unit test

**Implementation:**
```python
# src/functions/PostToAP/__init__.py

def _check_already_processed(enriched: EnrichedInvoice) -> bool:
    """
    Check if transaction has already been processed.

    Returns: True if already processed, False otherwise
    """
    table_client = TableServiceClient.from_connection_string(
        os.environ["AzureWebJobsStorage"]
    ).get_table_client("InvoiceTransactions")

    try:
        existing = table_client.get_entity(
            partition_key=datetime.utcnow().strftime("%Y%m"),
            row_key=enriched.id
        )

        if existing.get('Status') == 'processed':
            logger.warning(
                f"Transaction {enriched.id} already processed at {existing.get('ProcessedAt')}"
            )
            return True

    except ResourceNotFoundError:
        # New transaction, not processed yet
        return False

    return False


# In main function:
def main(msg: func.QueueMessage, notify: func.Out[str]):
    try:
        enriched = EnrichedInvoice.model_validate_json(msg.get_body().decode())

        # Check if already processed (deduplication)
        if _check_already_processed(enriched):
            logger.info(f"Skipping duplicate transaction {enriched.id}")
            return

        # ... rest of processing
```

**Tests Required:**
- `test_post_to_ap_skips_duplicate_transactions`
- `test_post_to_ap_processes_new_transactions`

---

### Layer 3: Email Sent Counter (Models + PostToAP) - IMMEDIATE

**Priority:** P0 (Critical)
**Effort:** 1 hour (includes model migration)
**Testing:** Unit test + Model validation test

**Implementation:**

**Step 3.1: Update InvoiceTransaction Model**
```python
# src/shared/models.py

class InvoiceTransaction(BaseModel):
    """Invoice transaction audit log."""

    PartitionKey: str = Field(..., description="YYYYMM format for monthly partitioning")
    RowKey: str = Field(..., description="ULID transaction ID")
    VendorName: str
    SenderEmail: EmailStr = Field(..., description="Original invoice sender email")
    RecipientEmail: EmailStr = Field(..., description="Email address where invoice was sent")
    ExpenseDept: str
    GLCode: str
    Status: Literal["processed", "unknown", "error"]
    BlobUrl: str
    ProcessedAt: str
    ErrorMessage: Optional[str] = None

    # NEW FIELDS for loop prevention
    EmailsSentCount: int = Field(default=0, description="Number of emails sent to AP")
    OriginalMessageId: Optional[str] = Field(None, description="Graph API message ID")
    LastEmailSentAt: Optional[str] = Field(None, description="Timestamp of last email sent")

    @validator("ErrorMessage", always=True)
    def validate_error_message(cls, v, values):
        if values.get("Status") == "error" and not v:
            raise ValueError("ErrorMessage required when Status is error")
        return v
```

**Step 3.2: Update PostToAP to Track Emails Sent**
```python
# src/functions/PostToAP/__init__.py

def _log_transaction(enriched: EnrichedInvoice, recipient: str, message_id: str):
    """Log transaction with email tracking."""
    table_client = TableServiceClient.from_connection_string(
        os.environ["AzureWebJobsStorage"]
    ).get_table_client("InvoiceTransactions")

    now = datetime.utcnow()

    transaction = InvoiceTransaction(
        PartitionKey=now.strftime("%Y%m"),
        RowKey=enriched.id,
        VendorName=enriched.vendor_name,
        SenderEmail=enriched.sender if hasattr(enriched, 'sender') else "unknown@system.com",
        RecipientEmail=recipient,
        ExpenseDept=enriched.expense_dept,
        GLCode=enriched.gl_code,
        Status="processed",
        BlobUrl=enriched.blob_url,
        ProcessedAt=now.isoformat() + "Z",
        EmailsSentCount=1,
        OriginalMessageId=message_id,
        LastEmailSentAt=now.isoformat() + "Z",
    )

    table_client.upsert_entity(transaction.model_dump())


def _check_email_sent_limit(enriched: EnrichedInvoice) -> bool:
    """
    Check if email has already been sent for this transaction.

    Returns: True if limit exceeded, False otherwise
    """
    table_client = TableServiceClient.from_connection_string(
        os.environ["AzureWebJobsStorage"]
    ).get_table_client("InvoiceTransactions")

    try:
        existing = table_client.get_entity(
            partition_key=datetime.utcnow().strftime("%Y%m"),
            row_key=enriched.id
        )

        emails_sent = existing.get('EmailsSentCount', 0)
        if emails_sent >= 1:
            logger.error(
                f"LOOP PREVENTION: Transaction {enriched.id} already sent {emails_sent} email(s). "
                f"Last sent at {existing.get('LastEmailSentAt')}"
            )
            return True

    except ResourceNotFoundError:
        return False

    return False


# In main function:
def main(msg: func.QueueMessage, notify: func.Out[str]):
    try:
        enriched = EnrichedInvoice.model_validate_json(msg.get_body().decode())

        # Check email sent limit (loop prevention)
        if _check_email_sent_limit(enriched):
            raise ValueError(f"Email loop prevention: Transaction {enriched.id} already sent to AP")

        # ... rest of processing

        # After sending email:
        # Note: Graph API send_email doesn't return message ID directly
        # We'll use transaction ID as reference
        _log_transaction(enriched, ap_email, enriched.id)
```

**Tests Required:**
- `test_invoice_transaction_email_sent_counter`
- `test_post_to_ap_prevents_duplicate_sends`
- `test_post_to_ap_tracks_recipient_email`

---

### Layer 4: Recipient Validation (PostToAP) - IMMEDIATE

**Priority:** P0 (Critical)
**Effort:** 30 minutes
**Testing:** Unit test

**Implementation:**
```python
# src/functions/PostToAP/__init__.py

def _validate_recipient(to_address: str, from_address: str) -> None:
    """
    Validate email recipient to prevent loops.

    Raises:
        ValueError: If recipient is invalid or creates loop
    """
    to_lower = to_address.lower()
    from_lower = from_address.lower()

    # Critical: Prevent sending to the mailbox we read from
    if to_lower == from_lower:
        raise ValueError(
            f"LOOP PREVENTION: Cannot send email TO same address as FROM "
            f"({to_address} == {from_address})"
        )

    # Validate recipient is in allowed list (if configured)
    allowed_recipients = os.environ.get("ALLOWED_AP_EMAILS", "").split(",")
    if allowed_recipients and allowed_recipients[0]:  # Non-empty list
        if to_address not in allowed_recipients:
            raise ValueError(
                f"Recipient {to_address} not in allowed list: {allowed_recipients}"
            )

    logger.info(f"Recipient validation passed: {to_address}")


# In main function:
def main(msg: func.QueueMessage, notify: func.Out[str]):
    try:
        enriched = EnrichedInvoice.model_validate_json(msg.get_body().decode())

        ap_email = os.environ["AP_EMAIL_ADDRESS"]
        invoice_mailbox = os.environ["INVOICE_MAILBOX"]

        # Validate recipient (loop prevention)
        _validate_recipient(ap_email, invoice_mailbox)

        # ... rest of processing
```

**Environment Variable Addition:**
```bash
# Optional: Add to Function App settings
ALLOWED_AP_EMAILS="accountspayable@chelseapiers.com,ap-backup@chelseapiers.com"
```

**Tests Required:**
- `test_post_to_ap_rejects_same_sender_recipient`
- `test_post_to_ap_validates_allowed_recipients`

---

### Layer 5: Infrastructure Fix (Long-term) - POST-MVP

**Priority:** P1 (High, but not blocking for MVP)
**Effort:** 2 hours (includes Key Vault setup + deployment)
**Testing:** Integration test

**Implementation:**

**Step 5.1: Create Separate Key Vault Secret**
```bash
# Create new secret for invoice mailbox
az keyvault secret set \
  --vault-name kv-invoice-agent-prod \
  --name invoice-mailbox \
  --value "invoices@chelseapiers.com"

# Verify AP email secret
az keyvault secret show \
  --vault-name kv-invoice-agent-prod \
  --name ap-email-address \
  --query value -o tsv
# Should return: accountspayable@chelseapiers.com
```

**Step 5.2: Update Bicep Template**
```bicep
// infrastructure/bicep/modules/functionapp.bicep

// BEFORE (WRONG):
{
  name: 'INVOICE_MAILBOX'
  value: '@Microsoft.KeyVault(SecretUri=https://${keyVaultName}.vault.azure.net/secrets/ap-email-address/)'
}

// AFTER (CORRECT):
{
  name: 'INVOICE_MAILBOX'
  value: '@Microsoft.KeyVault(SecretUri=https://${keyVaultName}.vault.azure.net/secrets/invoice-mailbox/)'
}
```

**Step 5.3: Deploy Updated Configuration**
```bash
# Redeploy infrastructure
az deployment group create \
  --resource-group rg-invoice-agent-prod \
  --template-file infrastructure/bicep/main.bicep \
  --parameters infrastructure/parameters/prod.json

# Restart Function App to pick up new settings
az functionapp restart \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod
```

**Verification:**
```bash
# Verify settings reference different secrets
az functionapp config appsettings list \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "[?name=='INVOICE_MAILBOX' || name=='AP_EMAIL_ADDRESS'].{name:name, value:value}" \
  --output table

# Expected output:
# INVOICE_MAILBOX → @Microsoft.KeyVault(...secrets/invoice-mailbox/)
# AP_EMAIL_ADDRESS → @Microsoft.KeyVault(...secrets/ap-email-address/)
```

---

### Layer 6: Graph API Filter Query (Performance Optimization) - POST-MVP

**Priority:** P2 (Medium, performance optimization)
**Effort:** 1 hour
**Testing:** Integration test

**Implementation:**
```python
# src/shared/graph_client.py

def get_unread_emails(
    self,
    mailbox: str,
    max_results: int = 50,
    exclude_sender: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get unread emails from a mailbox with optional sender filtering.

    Args:
        mailbox: Email address of mailbox to query
        max_results: Maximum number of emails to return
        exclude_sender: Optional email address to exclude (for loop prevention)
    """
    endpoint = f"users/{mailbox}/messages"

    # Build filter query
    filters = ["isRead eq false"]

    if exclude_sender:
        # Graph API filter to exclude system-sent emails
        filters.append(f"from/emailAddress/address ne '{exclude_sender}'")

    filter_query = " and ".join(filters)

    params = {
        "$filter": filter_query,
        "$select": "id,sender,subject,receivedDateTime,hasAttachments,body",
        "$top": max_results,
        "$orderby": "receivedDateTime desc",
    }

    response = self._make_request("GET", endpoint, params=params)
    return response.get("value", [])


# Update MailIngest to use:
emails = graph.get_unread_emails(
    mailbox,
    max_results=50,
    exclude_sender=mailbox  # Exclude emails FROM our own mailbox
)
```

**Benefits:**
- Server-side filtering (reduces bandwidth)
- Faster processing (fewer emails to check)
- Additional safety layer

---

## Implementation Priority & Timeline

### Phase 1: Immediate Safeguards (2-4 hours) - BEFORE TESTING

| Layer | Component | Priority | Effort | Dependencies |
|-------|-----------|----------|--------|--------------|
| 1 | Sender Filtering | P0 | 30 min | None |
| 2 | Transaction Deduplication | P0 | 45 min | None |
| 3 | Email Sent Counter | P0 | 1 hour | Model update |
| 4 | Recipient Validation | P0 | 30 min | None |

**Timeline:**
- Hour 1: Implement Layers 1, 2, 4 in parallel
- Hour 2: Update InvoiceTransaction model (Layer 3)
- Hour 3: Write unit tests for all layers
- Hour 4: Integration testing + deployment

**Deliverables:**
- ✅ 4 defense layers active
- ✅ 8+ unit tests passing
- ✅ Integration test passing
- ✅ Deployed to staging
- ✅ Ready for test email

---

### Phase 2: Infrastructure Fix (2 hours) - POST-MVP

| Layer | Component | Priority | Effort | Dependencies |
|-------|-----------|----------|--------|--------------|
| 5 | Separate Mailboxes | P1 | 2 hours | Key Vault access |

**Timeline:**
- Hour 1: Create Key Vault secret, update Bicep
- Hour 2: Deploy, test, verify

**Deliverables:**
- ✅ INVOICE_MAILBOX → invoices@chelseapiers.com
- ✅ AP_EMAIL_ADDRESS → accountspayable@chelseapiers.com
- ✅ Root cause eliminated

---

### Phase 3: Performance Optimization (1 hour) - POST-MVP

| Layer | Component | Priority | Effort | Dependencies |
|-------|-----------|----------|--------|--------------|
| 6 | Graph API Filtering | P2 | 1 hour | None |

**Timeline:**
- 1 hour: Update GraphAPIClient, test

**Deliverables:**
- ✅ Server-side filtering active
- ✅ Reduced email processing overhead

---

## Testing Strategy

### Unit Tests Required

**File:** `tests/unit/test_mail_ingest_loop_prevention.py`
```python
def test_mail_ingest_skips_system_sent_emails()
def test_mail_ingest_skips_system_subject_patterns()
def test_mail_ingest_skips_registration_replies()
def test_should_skip_email_logic()
```

**File:** `tests/unit/test_post_to_ap_loop_prevention.py`
```python
def test_post_to_ap_skips_duplicate_transactions()
def test_post_to_ap_prevents_duplicate_sends()
def test_post_to_ap_rejects_same_sender_recipient()
def test_post_to_ap_validates_allowed_recipients()
def test_check_email_sent_limit()
def test_validate_recipient()
```

**File:** `tests/unit/test_models_email_tracking.py`
```python
def test_invoice_transaction_email_sent_counter()
def test_invoice_transaction_recipient_email()
def test_invoice_transaction_message_id()
```

---

### Integration Tests Required

**File:** `tests/integration/test_email_loop_prevention.py`
```python
@pytest.mark.integration
def test_no_email_loop_end_to_end():
    """
    Verify that sending an invoice to AP does not trigger re-processing.

    Scenario:
    1. Send test email FROM adobe.com TO invoices@chelseapiers.com
    2. Wait for MailIngest to process
    3. Verify PostToAP sends email to accountspayable@chelseapiers.com
    4. Wait 5 minutes for next MailIngest cycle
    5. Verify system-sent email is NOT re-processed
    6. Verify InvoiceTransactions shows EmailsSentCount = 1
    """
    pass


@pytest.mark.integration
def test_duplicate_transaction_prevention():
    """
    Verify that processing same transaction twice does not send duplicate emails.

    Scenario:
    1. Queue enriched invoice to to-post queue
    2. Wait for PostToAP to process
    3. Queue SAME enriched invoice again
    4. Verify second processing is skipped
    5. Verify only 1 email sent to AP
    """
    pass
```

---

### Manual Testing Checklist

**Before Production:**
- [ ] Send test email from adobe.com to invoices@ (separate mailbox)
- [ ] Verify email processed successfully
- [ ] Check InvoiceTransactions table shows EmailsSentCount = 1
- [ ] Wait 5 minutes for next MailIngest cycle
- [ ] Verify system-sent email is marked as read but NOT processed
- [ ] Check Application Insights logs show "Skipping system-sent email"
- [ ] Send same test email again
- [ ] Verify deduplication prevents double-processing

**After Production (Monitoring):**
- [ ] Set up alert for EmailsSentCount > 1 (indicates loop attempt)
- [ ] Monitor MailIngest logs for "Skipping system-sent email" frequency
- [ ] Track InvoiceTransactions growth rate (should be linear, not exponential)
- [ ] Set mailbox quota alert at 80% capacity

---

## Monitoring & Alerting

### Application Insights Queries

**Query 1: Detect Email Loop Attempts**
```kusto
traces
| where message contains "LOOP PREVENTION"
| summarize count() by bin(timestamp, 5m)
| where count_ > 0
```

**Query 2: Email Sent Counter Violations**
```kusto
customEvents
| where name == "EmailsSentCountExceeded"
| extend transactionId = tostring(customDimensions.transactionId)
| extend emailsSent = toint(customDimensions.emailsSentCount)
| project timestamp, transactionId, emailsSent
```

**Query 3: System Email Detection Rate**
```kusto
traces
| where message contains "Skipping system-sent email"
| summarize count() by bin(timestamp, 1h)
```

---

### Alerts Configuration

**Alert 1: Email Loop Detected**
```json
{
  "name": "Email Loop Prevention Triggered",
  "condition": "traces | where message contains 'LOOP PREVENTION' | count > 0",
  "severity": "Critical",
  "frequency": "5 minutes",
  "action": "Email ops team + PagerDuty"
}
```

**Alert 2: High Email Sent Count**
```json
{
  "name": "High Email Processing Rate",
  "condition": "InvoiceTransactions | where EmailsSentCount > 1 | count > 5",
  "severity": "High",
  "frequency": "15 minutes",
  "action": "Email ops team"
}
```

**Alert 3: Mailbox Quota Warning**
```json
{
  "name": "Invoice Mailbox Quota Warning",
  "condition": "MailboxUsage > 80%",
  "severity": "Medium",
  "frequency": "1 hour",
  "action": "Email ops team"
}
```

---

## Rollback Procedures

### If Email Loop Occurs in Production

**Step 1: Immediate Response (0-5 minutes)**
```bash
# STOP THE TIMER TRIGGER IMMEDIATELY
az functionapp config appsettings set \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --settings "AzureWebJobs.MailIngest.Disabled=true"

# Restart function app to apply
az functionapp restart \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod
```

**Step 2: Assess Damage (5-15 minutes)**
```bash
# Count emails sent in last hour
az monitor app-insights query \
  --app invoice-agent \
  --analytics-query "traces | where message contains 'Sent email to AP' | summarize count()" \
  --offset 1h

# Check mailbox quota
# (Manual check via Outlook or Graph API)
```

**Step 3: Clean Up (15-30 minutes)**
```bash
# Mark all system-sent emails as read
# (Manual: Use Outlook search for subject pattern "Invoice: * - GL *")

# OR use Graph API batch mark as read
```

**Step 4: Deploy Fix (30-60 minutes)**
```bash
# Deploy hotfix with sender filtering
git checkout -b hotfix/email-loop-prevention
# Apply fixes from Layer 1 (minimum)
git commit -m "hotfix: add sender filtering to prevent email loops"
git push origin hotfix/email-loop-prevention

# Deploy via GitHub Actions
gh workflow run ci-cd.yml --ref hotfix/email-loop-prevention
```

**Step 5: Re-enable (60+ minutes)**
```bash
# After verification in staging:
az functionapp config appsettings set \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --settings "AzureWebJobs.MailIngest.Disabled=false"
```

---

## Decision Log

### ADR-021: Multi-Layer Email Loop Prevention

**Date:** 2024-11-16
**Status:** Proposed → Accepted (pending implementation)
**Context:** Email loop vulnerability discovered during pre-testing analysis

**Decision:** Implement 6-layer defense strategy before production testing

**Rationale:**
- Infrastructure misconfiguration creates guaranteed loop
- No current safeguards in place
- Risk of catastrophic failure on first test
- Multiple defense layers provide redundancy
- Each layer catches different failure modes

**Consequences:**
- ✅ Production-safe system
- ✅ Audit trail for loop prevention
- ✅ Multiple failure modes caught
- ⚠️ Additional 2-4 hours implementation time
- ⚠️ Model schema migration required

**Alternatives Considered:**
1. **Infrastructure fix only**: Rejected - doesn't protect against future misconfig
2. **Single-layer defense**: Rejected - single point of failure
3. **Delay testing until perfect**: Rejected - multi-layer approach allows phased testing

**Implementation Status:** Documented, awaiting execution

---

## Code Review Checklist

Before merging email loop prevention:

- [ ] All 6 defense layers implemented
- [ ] Unit tests written for each layer
- [ ] Integration tests passing
- [ ] Code coverage ≥60% for new code
- [ ] Black formatting applied
- [ ] Flake8 linting passes
- [ ] Model migration tested
- [ ] Rollback procedure documented
- [ ] Monitoring queries tested
- [ ] Alerts configured in App Insights
- [ ] Documentation updated (this file)
- [ ] CHANGELOG.md updated
- [ ] Stakeholders notified

---

## References

### Related Documents
- `docs/DECISIONS.md` - ADR-021 Email Loop Prevention
- `docs/ARCHITECTURE.md` - System flow diagrams
- `docs/AZURE_SETUP.md` - Infrastructure setup
- `CLAUDE.md` - Development constraints

### Related Code Files
- `src/functions/MailIngest/__init__.py` - Email ingestion
- `src/functions/PostToAP/__init__.py` - Email sending
- `src/shared/models.py` - Data models
- `src/shared/graph_client.py` - Graph API client
- `infrastructure/bicep/modules/functionapp.bicep` - Configuration

### External References
- [Microsoft Graph API: Message Filtering](https://learn.microsoft.com/en-us/graph/query-parameters)
- [Azure Functions: Queue Triggers](https://learn.microsoft.com/en-us/azure/azure-functions/functions-bindings-storage-queue-trigger)
- [Email Loop Prevention Best Practices](https://tools.ietf.org/html/rfc5321#section-6.2)

---

## Appendix A: Email Loop Scenarios

### Scenario 1: Basic Loop (CRITICAL)
```
Trigger: Infrastructure misconfiguration (INVOICE_MAILBOX == AP_EMAIL_ADDRESS)
Flow: Vendor → System → System → System (infinite)
Impact: Exponential email growth
Prevention: Layers 1, 4
```

### Scenario 2: Duplicate Processing (HIGH)
```
Trigger: Same email processed multiple times
Flow: Vendor → System (process) → System (re-process same email)
Impact: Duplicate emails to AP
Prevention: Layers 2, 3
```

### Scenario 3: Registration Email Reply (MEDIUM)
```
Trigger: Vendor replies to registration email
Flow: Vendor → Unknown → Registration Email → Vendor Reply → Re-process
Impact: Additional registration emails
Prevention: Layer 1 (subject pattern)
```

### Scenario 4: Manual Retry (LOW)
```
Trigger: Operator manually re-queues message
Flow: Manual → Queue → Process → Already processed check
Impact: Prevented by deduplication
Prevention: Layers 2, 3
```

---

## Appendix B: Graph API Message ID Extraction

**Note:** Microsoft Graph API `send_email` does not return message ID in response.

**Workaround Options:**
1. Use transaction ULID as reference (current approach)
2. Search sent items folder for recently sent email
3. Use `Prefer: return=representation` header (if supported)

**Implementation:**
```python
# Option 1: Use ULID (simplest)
_log_transaction(enriched, ap_email, enriched.id)

# Option 2: Search sent items (more accurate but slower)
sent_emails = graph.get_sent_emails(from_mailbox, subject=subject, max_results=1)
message_id = sent_emails[0]['id'] if sent_emails else enriched.id
```

---

## Appendix C: Emergency Contacts

**If email loop occurs:**
1. **First Response:** Disable MailIngest timer trigger (see Rollback Step 1)
2. **Escalate to:** DevOps team lead
3. **Notify:** Finance team (AP mailbox owner)
4. **Incident Channel:** #invoice-agent-alerts (Teams)

**24/7 On-Call:** [To be configured]

---

**Document Status:** Draft → Ready for Implementation
**Next Review:** After Phase 1 implementation
**Owner:** Development Team
**Approved By:** [Pending stakeholder review]

---

*This document is a living artifact. Update after each implementation phase.*
