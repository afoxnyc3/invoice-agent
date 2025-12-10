"""
Notify queue function - Send Teams webhook notifications.

Formats and posts simple message cards to Teams channel
for success, unknown vendor, and error notifications.
"""

import logging
from typing import Any
import requests
import azure.functions as func
from shared.models import NotificationMessage
from shared.config import config

logger = logging.getLogger(__name__)


def _build_teams_payload(notification: NotificationMessage) -> dict[str, Any]:
    """
    Build Teams webhook payload using MessageCard format.

    Direct Teams Incoming Webhooks use MessageCard (Office 365 Connector) format.
    This is simpler and more reliable than Power Automate + Adaptive Cards.

    See: https://learn.microsoft.com/en-us/microsoftteams/platform/webhooks-and-connectors/how-to/connectors-using
    """
    emoji_map = {"success": "✅", "unknown": "⚠️", "error": "❌", "duplicate": "🔄"}
    # Teams MessageCard uses hex color codes (without #)
    color_map = {"success": "00FF00", "unknown": "FFA500", "error": "FF0000", "duplicate": "FFA500"}

    emoji = emoji_map.get(notification.type, "ℹ️")
    theme_color = color_map.get(notification.type, "0078D4")

    # Build facts for MessageCard format
    facts = [{"name": k.replace("_", " ").title(), "value": str(v)} for k, v in notification.details.items()]

    return {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": theme_color,
        "summary": notification.message,
        "sections": [
            {
                "activityTitle": f"{emoji} {notification.message}",
                "facts": facts,
                "markdown": True,
            }
        ],
    }


def main(msg: func.QueueMessage) -> None:
    """Post notification to Teams webhook."""
    try:
        notification = NotificationMessage.model_validate_json(msg.get_body().decode())
        payload = _build_teams_payload(notification)

        webhook_url = config.teams_webhook_url
        if not webhook_url:
            logger.warning("Teams webhook URL not configured, skipping notification")
            return

        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"Posted {notification.type} notification to Teams")
    except Exception as e:
        # Non-critical: log but don't raise (per CLAUDE.md)
        logger.warning(f"Teams notification failed (non-critical): {str(e)}")
