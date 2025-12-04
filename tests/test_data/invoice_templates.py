"""
Invoice template generator for testing the Invoice Agent system.

Generates realistic invoice content for each vendor in the MVP vendor list.
Can be used to create test PDFs or email content for end-to-end testing.
"""

import random
from datetime import datetime, timedelta
from typing import Dict, List


class InvoiceGenerator:
    """Generate realistic invoice content for testing."""

    def __init__(self):
        self.invoice_counter = 1000
        self.current_date = datetime.now()

    def generate_invoice_number(self, vendor_prefix: str) -> str:
        """Generate unique invoice number with vendor prefix."""
        self.invoice_counter += 1
        return f"{vendor_prefix}-{self.invoice_counter}"

    def generate_due_date(self, days_out: int = 30) -> str:
        """Generate due date N days from now."""
        due_date = self.current_date + timedelta(days=days_out)
        return due_date.strftime("%B %d, %Y")

    def generate_invoice_content(self, vendor_config: Dict) -> Dict:
        """
        Generate complete invoice content for a vendor.

        Args:
            vendor_config: Dictionary with vendor details

        Returns:
            Dictionary with invoice content including text and metadata
        """
        vendor_name = vendor_config["vendor_name"]
        domain = vendor_config["email_domain"]
        dept = vendor_config["expense_dept"]
        schedule = vendor_config["allocation_schedule"]
        notes = vendor_config.get("notes", "")

        # Generate invoice details
        invoice_num = self.generate_invoice_number(vendor_name.split()[0].upper()[:3])
        invoice_date = self.current_date.strftime("%B %d, %Y")
        due_date = self.generate_due_date(30)

        # Generate line items based on vendor type
        line_items = self._generate_line_items(vendor_name, dept, schedule)
        subtotal = sum(item["amount"] for item in line_items)
        tax = round(subtotal * 0.08, 2)
        total = subtotal + tax

        # Determine sender email
        sender_email = self._get_sender_email(domain)

        return {
            "vendor_name": vendor_name,
            "invoice_number": invoice_num,
            "invoice_date": invoice_date,
            "due_date": due_date,
            "sender_email": sender_email,
            "line_items": line_items,
            "subtotal": subtotal,
            "tax": tax,
            "total": total,
            "notes": notes,
            "department": dept,
            "schedule": schedule,
        }

    def _get_sender_email(self, domain: str) -> str:
        """Generate realistic sender email address."""
        prefixes = ["billing", "invoices", "accounts", "ar", "finance", "noreply"]
        prefix = random.choice(prefixes)
        return f"{prefix}@{domain}"

    def _generate_line_items(self, vendor: str, dept: str, schedule: str) -> List[Dict]:
        """Generate realistic line items based on vendor and department."""
        items = []

        # IT Department vendors
        if dept == "IT":
            if "Adobe" in vendor:
                items = [
                    {
                        "description": "Creative Cloud - All Apps Plan (50 licenses)",
                        "qty": 50,
                        "rate": 54.99,
                        "amount": 2749.50,
                    }
                ]
            elif "Microsoft" in vendor:
                items = [
                    {"description": "Microsoft 365 E3 Licenses", "qty": 100, "rate": 36.00, "amount": 3600.00},
                    {"description": "Azure Cloud Services", "qty": 1, "rate": 2450.00, "amount": 2450.00},
                ]
            elif "AWS" in vendor or "Amazon Web Services" in vendor:
                items = [
                    {"description": "EC2 Instance Usage", "qty": 720, "rate": 0.096, "amount": 69.12},
                    {"description": "S3 Storage (TB)", "qty": 5, "rate": 23.00, "amount": 115.00},
                    {"description": "RDS Database", "qty": 1, "rate": 450.00, "amount": 450.00},
                ]
            elif "Zoom" in vendor:
                items = [{"description": "Zoom Business - 75 licenses", "qty": 75, "rate": 19.99, "amount": 1499.25}]
            elif "Slack" in vendor:
                items = [{"description": "Slack Business+ Plan", "qty": 120, "rate": 12.50, "amount": 1500.00}]
            elif "Google" in vendor:
                items = [
                    {"description": "Google Workspace Business Standard", "qty": 80, "rate": 12.00, "amount": 960.00}
                ]
            elif "Dropbox" in vendor:
                items = [
                    {"description": "Dropbox Business Advanced (Annual)", "qty": 1, "rate": 2400.00, "amount": 2400.00}
                ]
            elif "Verizon" in vendor:
                items = [
                    {"description": "Business Internet - 1000 Mbps", "qty": 1, "rate": 299.99, "amount": 299.99},
                    {"description": "Business Phone Lines (25)", "qty": 25, "rate": 29.99, "amount": 749.75},
                ]
            elif "AT&T" in vendor:
                items = [
                    {"description": "Fiber Internet - 500 Mbps", "qty": 1, "rate": 199.99, "amount": 199.99},
                    {"description": "Mobile Lines (50)", "qty": 50, "rate": 45.00, "amount": 2250.00},
                ]
            elif "Oracle" in vendor:
                items = [
                    {
                        "description": "Oracle Database Enterprise Edition (Annual)",
                        "qty": 1,
                        "rate": 47500.00,
                        "amount": 47500.00,
                    }
                ]
            elif "ServiceNow" in vendor:
                items = [
                    {"description": "ServiceNow ITSM Platform (Annual)", "qty": 1, "rate": 36000.00, "amount": 36000.00}
                ]

        # Sales Department
        elif dept == "SALES":
            if "Salesforce" in vendor:
                items = [
                    {
                        "description": "Salesforce Sales Cloud Enterprise (Annual)",
                        "qty": 50,
                        "rate": 1800.00,
                        "amount": 90000.00,
                    }
                ]

        # Marketing Department
        elif dept == "MARKETING":
            if "HubSpot" in vendor:
                items = [
                    {"description": "HubSpot Marketing Hub Professional", "qty": 1, "rate": 890.00, "amount": 890.00},
                    {"description": "Additional Contacts (10,000)", "qty": 1, "rate": 200.00, "amount": 200.00},
                ]

        # Finance Department
        elif dept == "FINANCE":
            if "QuickBooks" in vendor or "Intuit" in vendor:
                items = [
                    {"description": "QuickBooks Enterprise (Annual)", "qty": 5, "rate": 1500.00, "amount": 7500.00}
                ]

        # Legal Department
        elif dept == "LEGAL":
            if "DocuSign" in vendor:
                items = [
                    {"description": "DocuSign Business Pro (Annual)", "qty": 10, "rate": 480.00, "amount": 4800.00}
                ]

        # HR Department
        elif dept == "HR":
            if "Workday" in vendor:
                items = [
                    {"description": "Workday HCM Platform (Annual)", "qty": 1, "rate": 48000.00, "amount": 48000.00}
                ]
            elif "ADP" in vendor:
                items = [
                    {"description": "Payroll Processing (200 employees)", "qty": 200, "rate": 5.00, "amount": 1000.00},
                    {"description": "Time & Attendance", "qty": 1, "rate": 250.00, "amount": 250.00},
                ]
            elif "LinkedIn" in vendor:
                items = [{"description": "LinkedIn Recruiter (Annual)", "qty": 5, "rate": 8999.00, "amount": 44995.00}]
            elif "Indeed" in vendor:
                items = [{"description": "Sponsored Job Postings", "qty": 10, "rate": 299.00, "amount": 2990.00}]

        # Operations Department
        elif dept == "OPERATIONS":
            if "FedEx" in vendor:
                items = [
                    {"description": "Express Shipping", "qty": 45, "rate": 25.50, "amount": 1147.50},
                    {"description": "Ground Shipping", "qty": 120, "rate": 12.75, "amount": 1530.00},
                ]
            elif "UPS" in vendor:
                items = [
                    {"description": "Next Day Air", "qty": 30, "rate": 35.00, "amount": 1050.00},
                    {"description": "Ground Service", "qty": 150, "rate": 10.50, "amount": 1575.00},
                ]
            elif "Staples" in vendor:
                items = [
                    {"description": "Copy Paper (Cases)", "qty": 20, "rate": 45.99, "amount": 919.80},
                    {"description": "Pens & Office Supplies", "qty": 1, "rate": 245.75, "amount": 245.75},
                    {"description": "Toner Cartridges", "qty": 12, "rate": 89.99, "amount": 1079.88},
                ]
            elif "Amazon Business" in vendor or "Amazon" in vendor:
                items = [
                    {"description": "Office Supplies - Various", "qty": 1, "rate": 1245.50, "amount": 1245.50},
                    {"description": "Breakroom Supplies", "qty": 1, "rate": 456.75, "amount": 456.75},
                ]

        # Facilities Department
        elif dept == "FACILITIES":
            if "Grainger" in vendor:
                items = [
                    {"description": "HVAC Filters (Cases)", "qty": 10, "rate": 125.00, "amount": 1250.00},
                    {"description": "Cleaning Supplies", "qty": 1, "rate": 675.50, "amount": 675.50},
                    {"description": "Safety Equipment", "qty": 1, "rate": 890.00, "amount": 890.00},
                ]
            elif "Home Depot" in vendor:
                items = [
                    {"description": "Maintenance Materials", "qty": 1, "rate": 1456.75, "amount": 1456.75},
                    {"description": "Power Tools", "qty": 3, "rate": 299.99, "amount": 899.97},
                ]

        # Default fallback
        if not items:
            items = [{"description": f"{vendor} Services - {schedule}", "qty": 1, "rate": 999.00, "amount": 999.00}]

        return items

    def format_as_text_invoice(self, invoice_data: Dict) -> str:
        """Format invoice data as plain text (for PDF generation or email)."""
        lines = []
        lines.append("=" * 80)
        lines.append(f"{invoice_data['vendor_name'].upper()}")
        lines.append("=" * 80)
        lines.append("")
        lines.append(f"INVOICE NUMBER: {invoice_data['invoice_number']}")
        lines.append(f"INVOICE DATE: {invoice_data['invoice_date']}")
        lines.append(f"DUE DATE: {invoice_data['due_date']}")
        lines.append("")
        lines.append("BILL TO:")
        lines.append("Chelsea Piers")
        lines.append("Pier 62, Hudson River Greenway")
        lines.append("New York, NY 10011")
        lines.append("")
        lines.append("-" * 80)
        lines.append(f"{'DESCRIPTION':<50} {'QTY':>8} {'RATE':>10} {'AMOUNT':>10}")
        lines.append("-" * 80)

        for item in invoice_data["line_items"]:
            lines.append(f"{item['description']:<50} {item['qty']:>8} ${item['rate']:>9.2f} ${item['amount']:>9.2f}")

        lines.append("-" * 80)
        lines.append(f"{'SUBTOTAL:':>70} ${invoice_data['subtotal']:>9.2f}")
        lines.append(f"{'TAX (8%):':>70} ${invoice_data['tax']:>9.2f}")
        lines.append(f"{'TOTAL DUE:':>70} ${invoice_data['total']:>9.2f}")
        lines.append("=" * 80)
        lines.append("")
        lines.append(f"Payment Terms: Net 30 ({invoice_data['schedule']})")
        lines.append(f"Department: {invoice_data['department']}")
        lines.append("")
        lines.append("Thank you for your business!")
        lines.append("")
        lines.append(f"Questions? Email: {invoice_data['sender_email']}")
        lines.append("")

        return "\n".join(lines)

    def format_as_email_body(self, invoice_data: Dict) -> Dict[str, str]:
        """Format invoice data as email subject and body."""
        subject = f"Invoice {invoice_data['invoice_number']} from {invoice_data['vendor_name']}"

        body = f"""Hello,

Please find attached invoice {invoice_data['invoice_number']} from {invoice_data['vendor_name']}.

Invoice Summary:
- Invoice Number: {invoice_data['invoice_number']}
- Invoice Date: {invoice_data['invoice_date']}
- Due Date: {invoice_data['due_date']}
- Total Amount: ${invoice_data['total']:.2f}

This invoice is for:
"""
        for item in invoice_data["line_items"]:
            body += f"  • {item['description']} - ${item['amount']:.2f}\n"

        body += f"""
Payment is due by {invoice_data['due_date']}.

If you have any questions regarding this invoice, please contact us.

Thank you,
{invoice_data['vendor_name']} Accounts Receivable
{invoice_data['sender_email']}
"""

        return {"subject": subject, "body": body}


# Generate all test invoices
def generate_all_test_invoices() -> List[Dict]:
    """Generate test invoices for all vendors in the MVP list."""
    vendors = [
        {
            "vendor_name": "Adobe Inc",
            "email_domain": "adobe.com",
            "expense_dept": "IT",
            "allocation_schedule": "MONTHLY",
            "gl_code": "6100",
            "notes": "Creative Cloud subscriptions",
        },
        {
            "vendor_name": "Microsoft Corporation",
            "email_domain": "microsoft.com",
            "expense_dept": "IT",
            "allocation_schedule": "ANNUAL",
            "gl_code": "6100",
            "notes": "Office 365 and Azure services",
        },
        {
            "vendor_name": "Amazon Web Services",
            "email_domain": "aws.amazon.com",
            "expense_dept": "IT",
            "allocation_schedule": "MONTHLY",
            "gl_code": "6110",
            "notes": "Cloud infrastructure",
        },
        {
            "vendor_name": "Salesforce",
            "email_domain": "salesforce.com",
            "expense_dept": "SALES",
            "allocation_schedule": "ANNUAL",
            "gl_code": "6200",
            "notes": "CRM platform",
        },
        {
            "vendor_name": "Zoom Video Communications",
            "email_domain": "zoom.us",
            "expense_dept": "IT",
            "allocation_schedule": "MONTHLY",
            "gl_code": "6120",
            "notes": "Video conferencing",
        },
        {
            "vendor_name": "Slack Technologies",
            "email_domain": "slack.com",
            "expense_dept": "IT",
            "allocation_schedule": "MONTHLY",
            "gl_code": "6120",
            "notes": "Team collaboration",
        },
        {
            "vendor_name": "Google Workspace",
            "email_domain": "google.com",
            "expense_dept": "IT",
            "allocation_schedule": "MONTHLY",
            "gl_code": "6100",
            "notes": "Email and productivity suite",
        },
        {
            "vendor_name": "Dropbox",
            "email_domain": "dropbox.com",
            "expense_dept": "IT",
            "allocation_schedule": "ANNUAL",
            "gl_code": "6130",
            "notes": "File storage and sharing",
        },
        {
            "vendor_name": "HubSpot",
            "email_domain": "hubspot.com",
            "expense_dept": "MARKETING",
            "allocation_schedule": "MONTHLY",
            "gl_code": "6300",
            "notes": "Marketing automation",
        },
        {
            "vendor_name": "QuickBooks",
            "email_domain": "intuit.com",
            "expense_dept": "FINANCE",
            "allocation_schedule": "ANNUAL",
            "gl_code": "6400",
            "notes": "Accounting software",
        },
        {
            "vendor_name": "DocuSign",
            "email_domain": "docusign.com",
            "expense_dept": "LEGAL",
            "allocation_schedule": "ANNUAL",
            "gl_code": "6500",
            "notes": "Electronic signatures",
        },
        {
            "vendor_name": "Verizon",
            "email_domain": "verizon.com",
            "expense_dept": "IT",
            "allocation_schedule": "MONTHLY",
            "gl_code": "6140",
            "notes": "Telecom services",
        },
        {
            "vendor_name": "AT&T",
            "email_domain": "att.com",
            "expense_dept": "IT",
            "allocation_schedule": "MONTHLY",
            "gl_code": "6140",
            "notes": "Telecom services",
        },
        {
            "vendor_name": "Oracle",
            "email_domain": "oracle.com",
            "expense_dept": "IT",
            "allocation_schedule": "ANNUAL",
            "gl_code": "6110",
            "notes": "Database licenses",
        },
        {
            "vendor_name": "ServiceNow",
            "email_domain": "servicenow.com",
            "expense_dept": "IT",
            "allocation_schedule": "ANNUAL",
            "gl_code": "6150",
            "notes": "IT service management",
        },
        {
            "vendor_name": "Workday",
            "email_domain": "workday.com",
            "expense_dept": "HR",
            "allocation_schedule": "ANNUAL",
            "gl_code": "6600",
            "notes": "HR management system",
        },
        {
            "vendor_name": "ADP",
            "email_domain": "adp.com",
            "expense_dept": "HR",
            "allocation_schedule": "MONTHLY",
            "gl_code": "6610",
            "notes": "Payroll processing",
        },
        {
            "vendor_name": "LinkedIn",
            "email_domain": "linkedin.com",
            "expense_dept": "HR",
            "allocation_schedule": "ANNUAL",
            "gl_code": "6620",
            "notes": "Recruiting platform",
        },
        {
            "vendor_name": "Indeed",
            "email_domain": "indeed.com",
            "expense_dept": "HR",
            "allocation_schedule": "MONTHLY",
            "gl_code": "6620",
            "notes": "Job postings",
        },
        {
            "vendor_name": "FedEx",
            "email_domain": "fedex.com",
            "expense_dept": "OPERATIONS",
            "allocation_schedule": "MONTHLY",
            "gl_code": "6700",
            "notes": "Shipping services",
        },
        {
            "vendor_name": "UPS",
            "email_domain": "ups.com",
            "expense_dept": "OPERATIONS",
            "allocation_schedule": "MONTHLY",
            "gl_code": "6700",
            "notes": "Shipping services",
        },
        {
            "vendor_name": "Staples",
            "email_domain": "staples.com",
            "expense_dept": "OPERATIONS",
            "allocation_schedule": "MONTHLY",
            "gl_code": "6710",
            "notes": "Office supplies",
        },
        {
            "vendor_name": "Amazon Business",
            "email_domain": "amazon.com",
            "expense_dept": "OPERATIONS",
            "allocation_schedule": "MONTHLY",
            "gl_code": "6710",
            "notes": "Business supplies",
        },
        {
            "vendor_name": "Grainger",
            "email_domain": "grainger.com",
            "expense_dept": "FACILITIES",
            "allocation_schedule": "MONTHLY",
            "gl_code": "6800",
            "notes": "Industrial supplies",
        },
        {
            "vendor_name": "Home Depot",
            "email_domain": "homedepot.com",
            "expense_dept": "FACILITIES",
            "allocation_schedule": "MONTHLY",
            "gl_code": "6810",
            "notes": "Maintenance supplies",
        },
    ]

    generator = InvoiceGenerator()
    test_invoices = []

    for vendor in vendors:
        invoice_data = generator.generate_invoice_content(vendor)
        test_invoices.append(invoice_data)

    return test_invoices


if __name__ == "__main__":
    # Generate and print sample invoices
    invoices = generate_all_test_invoices()
    generator = InvoiceGenerator()

    print(f"Generated {len(invoices)} test invoices\n")
    print("=" * 80)

    # Print first 3 as examples
    for i, invoice in enumerate(invoices[:3], 1):
        print(f"\nSAMPLE INVOICE {i}:")
        print(generator.format_as_text_invoice(invoice))
        email = generator.format_as_email_body(invoice)
        print(f"\nEMAIL SUBJECT: {email['subject']}")
        print("-" * 80)
