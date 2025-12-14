#!/usr/bin/env python3
"""
Validate Adaptive Card JSON for Power Automate Teams webhook.

Checks:
1. Valid JSON syntax
2. Required message envelope structure
3. Adaptive Card schema compliance
4. Teams-specific constraints

Usage:
    python validate_adaptive_card.py <json_file>
    python validate_adaptive_card.py --payload '{"type": "message", ...}'
"""

import json
import sys
import argparse
from typing import Tuple, List

# Teams-supported Adaptive Card version
MAX_SUPPORTED_VERSION = "1.4"

# Required envelope structure
REQUIRED_ENVELOPE = {
    "type": "message",
    "attachments": [
        {
            "contentType": "application/vnd.microsoft.card.adaptive",
            "contentUrl": None,  # Must be present
            "content": {}
        }
    ]
}

# Teams size limits
MAX_PAYLOAD_SIZE = 28 * 1024  # ~28KB


def validate_json_syntax(payload_str: str) -> Tuple[bool, dict | str]:
    """Check if string is valid JSON."""
    try:
        data = json.loads(payload_str)
        return True, data
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {e}"


def validate_envelope(payload: dict) -> List[str]:
    """Validate the message envelope structure."""
    errors = []
    
    # Check root type
    if payload.get("type") != "message":
        errors.append(f"Root 'type' must be 'message', got: {payload.get('type')}")
    
    # Check attachments
    attachments = payload.get("attachments")
    if not attachments:
        errors.append("Missing 'attachments' array")
        return errors
    
    if not isinstance(attachments, list):
        errors.append(f"'attachments' must be an array, got: {type(attachments).__name__}")
        return errors
    
    if len(attachments) == 0:
        errors.append("'attachments' array is empty")
        return errors
    
    # Check first attachment
    attachment = attachments[0]
    
    if attachment.get("contentType") != "application/vnd.microsoft.card.adaptive":
        errors.append(
            f"'contentType' must be 'application/vnd.microsoft.card.adaptive', "
            f"got: {attachment.get('contentType')}"
        )
    
    if "contentUrl" not in attachment:
        errors.append("Missing 'contentUrl' field (should be null)")
    
    if "content" not in attachment:
        errors.append("Missing 'content' field containing the Adaptive Card")
    
    return errors


def validate_card(card: dict) -> List[str]:
    """Validate Adaptive Card structure and Teams compatibility."""
    errors = []
    warnings = []
    
    # Check card type
    if card.get("type") != "AdaptiveCard":
        errors.append(f"Card 'type' must be 'AdaptiveCard', got: {card.get('type')}")
    
    # Check version
    version = card.get("version", "1.0")
    try:
        v_parts = [int(x) for x in version.split(".")]
        max_parts = [int(x) for x in MAX_SUPPORTED_VERSION.split(".")]
        if v_parts > max_parts:
            errors.append(
                f"Version '{version}' may not be fully supported in Teams. "
                f"Recommended: '{MAX_SUPPORTED_VERSION}' or lower"
            )
    except ValueError:
        errors.append(f"Invalid version format: {version}")
    
    # Check body exists
    body = card.get("body", [])
    if not body:
        warnings.append("Card 'body' is empty - card will be blank")
    
    # Recursively check for common issues
    issues = check_elements(body, "body")
    errors.extend(issues["errors"])
    warnings.extend(issues["warnings"])
    
    # Check actions
    actions = card.get("actions", [])
    if len(actions) > 6:
        warnings.append(f"Card has {len(actions)} actions. Teams displays max 6 well.")
    
    return errors + warnings


def check_elements(elements: list, path: str) -> dict:
    """Recursively check card elements for issues."""
    errors = []
    warnings = []
    
    for i, element in enumerate(elements):
        if not isinstance(element, dict):
            continue
        
        current_path = f"{path}[{i}]"
        elem_type = element.get("type", "unknown")
        
        # TextBlock checks
        if elem_type == "TextBlock":
            if not element.get("wrap"):
                warnings.append(f"{current_path}: TextBlock missing 'wrap: true' - text may truncate")
        
        # Image checks
        if elem_type == "Image":
            url = element.get("url", "")
            if url and not url.startswith("https://"):
                if url.startswith("data:image"):
                    pass  # Base64 is OK
                elif url.startswith("http://"):
                    errors.append(f"{current_path}: Image URL must use HTTPS, not HTTP")
                else:
                    warnings.append(f"{current_path}: Image URL format may not be supported")
        
        # Check nested elements
        for key in ["items", "columns", "body", "card"]:
            if key in element:
                nested = element[key]
                if isinstance(nested, list):
                    nested_issues = check_elements(nested, f"{current_path}.{key}")
                    errors.extend(nested_issues["errors"])
                    warnings.extend(nested_issues["warnings"])
        
        # Check Column width
        if elem_type == "Column":
            items = element.get("items", [])
            nested_issues = check_elements(items, f"{current_path}.items")
            errors.extend(nested_issues["errors"])
            warnings.extend(nested_issues["warnings"])
    
    return {"errors": errors, "warnings": warnings}


def validate_size(payload: dict) -> List[str]:
    """Check payload size against Teams limits."""
    warnings = []
    
    payload_str = json.dumps(payload)
    size = len(payload_str.encode("utf-8"))
    
    if size > MAX_PAYLOAD_SIZE:
        warnings.append(
            f"Payload size ({size:,} bytes) exceeds Teams limit (~28KB). "
            "Message may fail to post."
        )
    elif size > MAX_PAYLOAD_SIZE * 0.8:
        warnings.append(
            f"Payload size ({size:,} bytes) is close to Teams limit. "
            "Consider reducing content."
        )
    
    return warnings


def validate_payload(payload_str: str) -> dict:
    """Run all validations and return results."""
    results = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "size_bytes": 0
    }
    
    # Step 1: JSON syntax
    is_valid, data = validate_json_syntax(payload_str)
    if not is_valid:
        results["valid"] = False
        results["errors"].append(data)
        return results
    
    results["size_bytes"] = len(payload_str.encode("utf-8"))
    
    # Step 2: Envelope structure
    envelope_errors = validate_envelope(data)
    if envelope_errors:
        results["valid"] = False
        results["errors"].extend(envelope_errors)
        return results
    
    # Step 3: Card validation
    card = data["attachments"][0].get("content", {})
    card_issues = validate_card(card)
    
    for issue in card_issues:
        if issue.startswith("Version") or "may not" in issue:
            results["warnings"].append(issue)
        else:
            results["errors"].append(issue)
            results["valid"] = False
    
    # Step 4: Size check
    size_warnings = validate_size(data)
    results["warnings"].extend(size_warnings)
    
    return results


def print_results(results: dict):
    """Print validation results in readable format."""
    print("\n" + "=" * 60)
    print("VALIDATION RESULTS")
    print("=" * 60)
    
    if results["valid"]:
        print("✅ Payload is VALID")
    else:
        print("❌ Payload is INVALID")
    
    print(f"\nSize: {results['size_bytes']:,} bytes")
    
    if results["errors"]:
        print(f"\n🔴 ERRORS ({len(results['errors'])}):")
        for error in results["errors"]:
            print(f"   • {error}")
    
    if results["warnings"]:
        print(f"\n🟡 WARNINGS ({len(results['warnings'])}):")
        for warning in results["warnings"]:
            print(f"   • {warning}")
    
    if results["valid"] and not results["warnings"]:
        print("\n✨ No issues found!")
    
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Validate Adaptive Card JSON for Power Automate Teams webhook"
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="Path to JSON file to validate"
    )
    parser.add_argument(
        "--payload",
        "-p",
        help="JSON payload string to validate"
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Only output errors"
    )
    
    args = parser.parse_args()
    
    if args.payload:
        payload_str = args.payload
    elif args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                payload_str = f.read()
        except FileNotFoundError:
            print(f"Error: File not found: {args.file}")
            sys.exit(1)
        except IOError as e:
            print(f"Error reading file: {e}")
            sys.exit(1)
    else:
        # Read from stdin
        if sys.stdin.isatty():
            print("Enter JSON payload (Ctrl+D to finish):")
        payload_str = sys.stdin.read()
    
    results = validate_payload(payload_str)
    
    if args.quiet:
        if not results["valid"]:
            for error in results["errors"]:
                print(f"ERROR: {error}")
            sys.exit(1)
    else:
        print_results(results)
        if not results["valid"]:
            sys.exit(1)


if __name__ == "__main__":
    main()
