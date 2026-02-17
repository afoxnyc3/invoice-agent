# AddVendor API Reference

**Last Updated:** February 17, 2026

Complete API documentation for the AddVendor HTTP endpoint. This endpoint manages vendor records in the VendorMaster table.

## Endpoint Overview

| Property | Value |
|----------|-------|
| **URL** | `https://{function-app}.azurewebsites.net/api/AddVendor` |
| **Method** | `POST` |
| **Authentication** | Function key required (`authLevel: function`) |
| **Content-Type** | `application/json` |
| **Response Format** | JSON |

---

## Request Schema

### HTTP POST Request

```json
{
  "vendor_name": "string (required)",
  "expense_dept": "string (required)",
  "gl_code": "string (required)",
  "allocation_schedule": "string (required)",
  "product_category": "string (optional, default: Direct)",
  "venue_required": "boolean (optional, default: false)"
}
```

### Field Descriptions

| Field | Type | Required | Description | Constraints |
|-------|------|----------|-------------|-------------|
| `vendor_name` | string | Yes | Display name of vendor (also used as lookup key) | 1-100 characters |
| `expense_dept` | string | Yes | Department code | IT, SALES, HR, FINANCE, LEGAL, MARKETING, OPERATIONS, FACILITIES |
| `gl_code` | string | Yes | General ledger code | Exactly 4 digits (0-9) |
| `allocation_schedule` | string | Yes | Allocation schedule code | Numeric string (1, 3, 14, etc.) |
| `product_category` | string | No | Vendor type classification | "Direct" (default) or "Reseller" |
| `venue_required` | boolean | No | Whether venue extraction is needed | Default: false |

### Field Details

**vendor_name**
- Human-readable vendor name
- Examples: "Adobe Inc", "Microsoft Corporation", "Amazon Web Services"
- Used in notifications and audit trail

**vendor_domain**
- Email domain part of sender address
- Automatically normalized: lowercase, dots remain (e.g., adobe.com)
- Stored as RowKey with dots → underscores (e.g., adobe_com)
- Must be unique per vendor

**expense_dept**
- Must match one of 8 valid departments
- Valid values: `IT`, `SALES`, `HR`, `FINANCE`, `LEGAL`, `MARKETING`, `OPERATIONS`, `FACILITIES`
- Determines routing in GL system

**gl_code**
- Exactly 4 digits
- Examples: 6100 (IT), 6200 (Sales), 6300 (Marketing)
- Used for invoice categorization

**allocation_schedule**
- How often vendor is billed
- Valid values: `MONTHLY`, `ANNUAL`, `QUARTERLY`, `WEEKLY`
- Informational only, used in reporting

**billing_party**
- Entity responsible for paying the invoice
- Examples: "Company HQ", "Company Branch", "Subsidiary Inc"
- Determines payment processing

---

## Response Schemas

### Success Response (HTTP 201)

```json
{
  "status": "success",
  "vendor": "Adobe Inc"
}
```

**Fields:**
- `status`: Always "success" on 201
- `vendor`: Echo of vendor_name from request

**Status Code:** `201 Created`

### Validation Error Response (HTTP 400)

```json
{
  "error": "Validation failed",
  "details": [
    {
      "field": "gl_code",
      "message": "gl_code must be exactly 4 digits"
    },
    {
      "field": "expense_dept",
      "message": "expense_dept must be one of: IT, SALES, HR, FINANCE, LEGAL, MARKETING, OPERATIONS, FACILITIES"
    }
  ]
}
```

**Fields:**
- `error`: Error description
- `details`: Array of validation errors
  - `field`: Field name that failed validation
  - `message`: Specific validation error message

**Status Code:** `400 Bad Request`

### Server Error Response (HTTP 500)

```json
{
  "error": "Failed to connect to VendorMaster table"
}
```

**Fields:**
- `error`: Error description (storage access, service unavailable, etc.)

**Status Code:** `500 Internal Server Error`

---

## Usage Examples

### Example 1: Add Adobe Vendor

```bash
curl -X POST https://func-invoice-agent-prod.azurewebsites.net/api/AddVendor \
  -H "Content-Type: application/json" \
  -d '{
    "vendor_name": "Adobe Inc",
    "vendor_domain": "adobe.com",
    "expense_dept": "IT",
    "gl_code": "6100",
    "allocation_schedule": "MONTHLY",
    "billing_party": "Company HQ"
  }'
```

**Response:**
```json
{
  "status": "success",
  "vendor": "Adobe Inc"
}
```

### Example 2: Add AWS Vendor

```bash
curl -X POST https://func-invoice-agent-prod.azurewebsites.net/api/AddVendor \
  -H "Content-Type: application/json" \
  -d '{
    "vendor_name": "Amazon Web Services",
    "vendor_domain": "aws.amazon.com",
    "expense_dept": "IT",
    "gl_code": "6110",
    "allocation_schedule": "MONTHLY",
    "billing_party": "Company HQ"
  }'
```

**Response:**
```json
{
  "status": "success",
  "vendor": "Amazon Web Services"
}
```

### Example 3: Validation Error

```bash
curl -X POST https://func-invoice-agent-prod.azurewebsites.net/api/AddVendor \
  -H "Content-Type: application/json" \
  -d '{
    "vendor_name": "Test Vendor",
    "vendor_domain": "test.com",
    "expense_dept": "INVALID",      # Not valid department
    "gl_code": "999",                # Only 3 digits, needs 4
    "allocation_schedule": "MONTHLY",
    "billing_party": "Company HQ"
  }'
```

**Response (HTTP 400):**
```json
{
  "error": "Validation failed",
  "details": [
    {
      "field": "expense_dept",
      "message": "value must be one of: IT, SALES, HR, FINANCE, LEGAL, MARKETING, OPERATIONS, FACILITIES"
    },
    {
      "field": "gl_code",
      "message": "gl_code must be exactly 4 digits"
    }
  ]
}
```

---

## Testing

### Using curl (Linux/macOS)

```bash
# Local testing
curl -X POST http://localhost:7071/api/AddVendor \
  -H "Content-Type: application/json" \
  -d @- << 'EOF'
{
  "vendor_name": "Local Test",
  "vendor_domain": "localtest.com",
  "expense_dept": "IT",
  "gl_code": "9999",
  "allocation_schedule": "MONTHLY",
  "billing_party": "Local"
}
EOF
```

### Using Python

```python
import requests
import json

url = "http://localhost:7071/api/AddVendor"
payload = {
    "vendor_name": "Python Test",
    "vendor_domain": "pythontest.com",
    "expense_dept": "IT",
    "gl_code": "8888",
    "allocation_schedule": "MONTHLY",
    "billing_party": "Test"
}

response = requests.post(url, json=payload)
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")

# Expected output:
# Status: 201
# Response: {'status': 'success', 'vendor': 'Python Test'}
```

### Using Postman

1. **Create New Request**
   - Method: POST
   - URL: `http://localhost:7071/api/AddVendor`

2. **Headers Tab**
   - Key: `Content-Type`
   - Value: `application/json`

3. **Body Tab**
   - Select: Raw → JSON
   - Paste sample request

4. **Click Send**

### Unit Test Example

```python
import pytest
import json
from azure.functions import HttpRequest
from functions.AddVendor import main

def test_add_vendor_success():
    # Arrange
    request_body = {
        "vendor_name": "Test Inc",
        "vendor_domain": "test.com",
        "expense_dept": "IT",
        "gl_code": "6100",
        "allocation_schedule": "MONTHLY",
        "billing_party": "Company HQ"
    }
    request = HttpRequest(
        method="POST",
        url="http://localhost:7071/api/AddVendor",
        body=json.dumps(request_body).encode()
    )

    # Act
    response = main(request)

    # Assert
    assert response.status_code == 201
    body = json.loads(response.get_body())
    assert body["status"] == "success"
    assert body["vendor"] == "Test Inc"


def test_add_vendor_invalid_gl_code():
    # Arrange
    request_body = {
        "vendor_name": "Test Inc",
        "vendor_domain": "test.com",
        "expense_dept": "IT",
        "gl_code": "999",  # Invalid: only 3 digits
        "allocation_schedule": "MONTHLY",
        "billing_party": "Company HQ"
    }
    request = HttpRequest(
        method="POST",
        url="http://localhost:7071/api/AddVendor",
        body=json.dumps(request_body).encode()
    )

    # Act
    response = main(request)

    # Assert
    assert response.status_code == 400
    body = json.loads(response.get_body())
    assert body["error"] == "Validation failed"
    assert any(e["field"] == "gl_code" for e in body["details"])
```

---

## Error Codes

### 201 Created
**Success:** Vendor successfully added or updated

```json
{
  "status": "success",
  "vendor": "Vendor Name"
}
```

### 400 Bad Request
**Validation failed:** One or more fields are invalid

```json
{
  "error": "Validation failed",
  "details": [
    {"field": "field_name", "message": "error message"}
  ]
}
```

**Common validation errors:**
- `gl_code` - Must be exactly 4 digits
- `expense_dept` - Must be one of valid departments
- `vendor_name` - Required, 1-100 characters
- `vendor_domain` - Required, valid domain format
- `allocation_schedule` - Must be MONTHLY, ANNUAL, QUARTERLY, or WEEKLY
- `billing_party` - Required, 1-100 characters

### 500 Internal Server Error
**Server error:** Database unavailable, connection failed, etc.

```json
{
  "error": "Failed to connect to VendorMaster table"
}
```

**Troubleshooting:**
- Check Azure storage account is accessible
- Verify VendorMaster table exists
- Check Function App logs for detailed error

---

## Important Notes

### Duplicate Prevention

The endpoint uses **create** semantics (not upsert):
- New vendor name = creates record (HTTP 201)
- Existing vendor name = returns error (HTTP 400 "Vendor already exists")

The RowKey is derived from `vendor_name` (lowercased, spaces/hyphens to underscores).
To update an existing vendor, use Azure Table Storage directly or the seed script.

### Data Storage

All vendor data is stored in Azure Table Storage:

**Table:** `VendorMaster`
**Partition Key:** Always "Vendor"
**Row Key:** vendor_name normalized (lowercase, spaces/hyphens → underscores)

Example storage:
```
PartitionKey=Vendor, RowKey=adobe_inc, VendorName=Adobe Inc, GLCode=6100
PartitionKey=Vendor, RowKey=amazon_web_services, VendorName=Amazon Web Services, GLCode=6110
```

### Timestamp

`UpdatedAt` field is automatically set to current UTC time.

```bash
"UpdatedAt": "2025-11-13T14:23:45.123Z"
```

### Performance

- **Latency:** Typically 200-500ms
- **Throughput:** Rate limited to 10 requests/minute per IP
- **Scale:** Can handle 1000s of vendors without performance degradation

---

## Security

### Authentication

The endpoint requires a **function key** (`authLevel: function`).

Include the key as a query parameter `?code=<function-key>` or in the `x-functions-key` header.

**Additional security:**
- Network level (Azure firewall rules)
- Rate limiting (10 requests/minute per IP)
- Application level (Function App access control)

### Data Privacy

- **No audit logging** of individual API calls (handled by Azure monitoring)
- **No personal data** is stored (only vendor business info)
- **Secrets:** Stored in Key Vault, not in logs

### HTTPS Enforcement

All production endpoints use HTTPS:
```
https://func-invoice-agent-prod.azurewebsites.net/api/AddVendor
```

Local development uses HTTP:
```
http://localhost:7071/api/AddVendor
```

---

## Bulk Operations

To add multiple vendors at once, script the API:

```python
import requests
import time

vendors = [
    {"vendor_name": "Adobe Inc", "vendor_domain": "adobe.com", ...},
    {"vendor_name": "Microsoft", "vendor_domain": "microsoft.com", ...},
    # ... more vendors
]

url = "https://func-invoice-agent-prod.azurewebsites.net/api/AddVendor"

for vendor in vendors:
    response = requests.post(url, json=vendor)
    if response.status_code == 201:
        print(f"✓ Added: {vendor['vendor_name']}")
    else:
        print(f"✗ Failed: {vendor['vendor_name']}")
        print(f"  Error: {response.json()}")
    time.sleep(0.5)  # Small delay between requests
```

---

## See Also

- [Vendor Management Guide](../VENDOR_MANAGEMENT.md) - How to manage vendors
- [Local Development Guide](../LOCAL_DEVELOPMENT.md) - Testing locally
- [ARCHITECTURE.md](../ARCHITECTURE.md) - System design

---

**Last Updated:** February 17, 2026
