"""
Email composition utilities for invoice processing workflows.

Provides template-based email generation for various notification scenarios,
particularly for unknown vendor handling.
"""


def compose_unknown_vendor_email(sender_domain: str, transaction_id: str, api_url: str) -> tuple[str, str]:
    """
    Compose email for unknown vendor notification.

    Sends instructions to the original sender on how to register
    a new vendor via the AddVendor API endpoint.

    Args:
        sender_domain: Email domain of the invoice sender
        transaction_id: ULID transaction identifier
        api_url: Base URL of the API (e.g., https://func-app.azurewebsites.net)

    Returns:
        tuple: (subject, html_body)

    Example:
        >>> subject, body = compose_unknown_vendor_email(
        ...     "adobe.com", "01JCK3Q7H8ZVXN3BARC9GWAEZM",
        ...     "https://func-app.azurewebsites.net"
        ... )
    """
    subject = "Action Required: Add Vendor Information for Invoice Processing"

    html_body = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <h2 style="color: #d9534f;">Action Required: Vendor Registration Needed</h2>

    <p>Hello,</p>

    <p>Your invoice from <strong>{sender_domain}</strong> could not be automatically processed
    because this vendor is not in our system.</p>

    <h3>To register this vendor and resubmit your invoice:</h3>

    <ol>
        <li>Call our vendor registration API:
            <pre style="background: #f4f4f4; padding: 10px; border-left: 3px solid #5bc0de;">
POST {api_url}/api/AddVendor</pre>
        </li>

        <li>With this JSON payload (fill in the details):
            <pre style="background: #f4f4f4; padding: 10px; border-left: 3px solid #5bc0de;">
{{
  "vendor_domain": "{sender_domain}",
  "vendor_name": "Company Name",
  "expense_dept": "IT|SALES|HR|ADMIN",
  "gl_code": "4-digit GL code",
  "allocation_schedule": "MONTHLY|ANNUAL|QUARTERLY",
  "billing_party": "Entity name"
}}</pre>
        </li>

        <li>After successfully registering the vendor, please <strong>forward your original invoice email again</strong>.</li>
    </ol>

    <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">

    <p style="font-size: 0.9em; color: #777;">
        <strong>Transaction ID:</strong> {transaction_id}<br>
        <strong>Need Help?</strong> Contact IT Support
    </p>
</body>
</html>
"""

    return subject, html_body
