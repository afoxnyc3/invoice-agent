#!/usr/bin/env python3
"""
Test Power Automate Teams webhook with sample payloads.

Sends test adaptive cards to a Power Automate workflow URL to verify
connectivity and payload format.

Usage:
    python test_webhook.py <webhook_url>
    python test_webhook.py <webhook_url> --card custom_card.json
    python test_webhook.py <webhook_url> --message "Test message"

Environment:
    TEAMS_WEBHOOK_URL: Default webhook URL if not provided as argument
"""

import json
import sys
import argparse
import os
from datetime import datetime
from typing import Optional

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    import urllib.request
    import urllib.error


def create_test_card(message: Optional[str] = None) -> dict:
    """Create a simple test adaptive card."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "text": "🔧 Webhook Test",
                "weight": "Bolder",
                "size": "Large",
                "color": "Accent",
                "wrap": True
            },
            {
                "type": "TextBlock",
                "text": message or "This is a test message from the Power Automate webhook test script.",
                "wrap": True
            },
            {
                "type": "FactSet",
                "facts": [
                    {
                        "title": "Timestamp",
                        "value": timestamp
                    },
                    {
                        "title": "Source",
                        "value": "test_webhook.py"
                    },
                    {
                        "title": "Status",
                        "value": "✓ Connection successful"
                    }
                ]
            }
        ]
    }


def wrap_in_envelope(card: dict) -> dict:
    """Wrap adaptive card in required message envelope."""
    return {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "contentUrl": None,
                "content": card
            }
        ]
    }


def send_with_requests(url: str, payload: dict) -> tuple:
    """Send payload using requests library."""
    try:
        response = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        return response.status_code, response.text
    except requests.exceptions.Timeout:
        return None, "Request timed out"
    except requests.exceptions.RequestException as e:
        return None, str(e)


def send_with_urllib(url: str, payload: dict) -> tuple:
    """Send payload using urllib (no external dependencies)."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")
    except urllib.error.URLError as e:
        return None, str(e.reason)
    except Exception as e:
        return None, str(e)


def send_webhook(url: str, payload: dict) -> tuple:
    """Send webhook request, using best available method."""
    if HAS_REQUESTS:
        return send_with_requests(url, payload)
    else:
        return send_with_urllib(url, payload)


def main():
    parser = argparse.ArgumentParser(
        description="Test Power Automate Teams webhook"
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="Webhook URL (or set TEAMS_WEBHOOK_URL env var)"
    )
    parser.add_argument(
        "--card", "-c",
        help="Path to custom card JSON file"
    )
    parser.add_argument(
        "--message", "-m",
        help="Custom message text for test card"
    )
    parser.add_argument(
        "--raw", "-r",
        action="store_true",
        help="Send card JSON directly without wrapping in envelope"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show full request/response details"
    )
    
    args = parser.parse_args()
    
    # Get webhook URL
    url = args.url or os.environ.get("TEAMS_WEBHOOK_URL")
    if not url:
        print("Error: No webhook URL provided.")
        print("Usage: python test_webhook.py <webhook_url>")
        print("   Or: export TEAMS_WEBHOOK_URL=<url>")
        sys.exit(1)
    
    # Load or create card
    if args.card:
        try:
            with open(args.card, "r", encoding="utf-8") as f:
                card_data = json.load(f)
        except FileNotFoundError:
            print(f"Error: Card file not found: {args.card}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in card file: {e}")
            sys.exit(1)
        
        # Check if it's already a full envelope
        if card_data.get("type") == "message" and "attachments" in card_data:
            payload = card_data
        else:
            payload = wrap_in_envelope(card_data)
    else:
        card = create_test_card(args.message)
        payload = wrap_in_envelope(card)
    
    if args.raw and args.card:
        # Send raw without envelope (for testing)
        with open(args.card, "r", encoding="utf-8") as f:
            payload = json.load(f)
    
    # Show request details
    print("\n" + "=" * 60)
    print("SENDING TEST WEBHOOK")
    print("=" * 60)
    print(f"\nURL: {url[:50]}...")
    print(f"Payload size: {len(json.dumps(payload)):,} bytes")
    
    if args.verbose:
        print("\nPayload:")
        print(json.dumps(payload, indent=2))
    
    print("\nSending...")
    
    # Send request
    status, response = send_webhook(url, payload)
    
    # Show results
    print("\n" + "-" * 60)
    print("RESPONSE")
    print("-" * 60)
    
    if status is None:
        print(f"❌ Request failed: {response}")
        sys.exit(1)
    elif status == 200 or status == 202:
        print(f"✅ Success! Status: {status}")
        if response:
            print(f"Response: {response[:200]}")
    elif status == 400:
        print(f"❌ Bad Request (400)")
        print("The payload format is incorrect. Check:")
        print("  - Root 'type' should be 'message'")
        print("  - 'attachments' array with proper structure")
        print("  - Valid adaptive card in 'content'")
        if response:
            print(f"\nServer response: {response[:500]}")
    elif status == 401 or status == 403:
        print(f"❌ Authentication error ({status})")
        print("The webhook requires authentication or caller is not allowed.")
        print("Check trigger settings in Power Automate.")
    elif status == 404:
        print(f"❌ Not Found (404)")
        print("The webhook URL may be invalid or flow may be disabled.")
    elif status == 429:
        print(f"⚠️ Rate Limited (429)")
        print("Too many requests. Wait before retrying.")
    else:
        print(f"❌ Unexpected status: {status}")
        if response:
            print(f"Response: {response[:500]}")
    
    print("=" * 60 + "\n")
    
    if status not in [200, 202]:
        sys.exit(1)


if __name__ == "__main__":
    main()
