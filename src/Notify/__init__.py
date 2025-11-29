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
    Build Teams webhook payload for Power Automate workflows.

    Power Automate webhooks expect Adaptive Card format with attachments array.

    Note: This workflow may fail with "bot not in roster" error until the
    Power Automate Flow bot is granted permission to post to the channel.
    This is a platform limitation that requires admin intervention.
    """
    emoji_map = {"success": "✅", "unknown": "⚠️", "error": "❌", "duplicate": "🔄"}
    color_map = {"success": "good", "unknown": "warning", "error": "attention", "duplicate": "warning"}

    emoji = emoji_map.get(notification.type, "ℹ️")
    color = color_map.get(notification.type, "default")

    # Build facts for Adaptive Card FactSet
    facts = [{"title": f"{k.title()}:", "value": str(v)} for k, v in notification.details.items()]

    return {
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "type": "AdaptiveCard",
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": f"{emoji} {notification.message}",
                            "weight": "Bolder",
                            "size": "Large",
                            "color": color,
                        },
                        {"type": "FactSet", "facts": facts},
                    ],
                },
            }
        ]
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
