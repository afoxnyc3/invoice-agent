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
    Build Teams webhook payload for Power Automate.

    Power Automate's "When a Teams webhook request is received" trigger expects
    the Adaptive Card wrapped in a message envelope with attachments array.
    """
    emoji_map = {"success": "✅", "unknown": "⚠️", "error": "❌", "duplicate": "🔄"}

    emoji = emoji_map.get(notification.type, "ℹ️")

    # Build facts for Adaptive Card FactSet
    facts = [{"title": k.replace("_", " ").title(), "value": str(v)} for k, v in notification.details.items()]

    # Wrap Adaptive Card in Teams message format for Power Automate webhook trigger
    adaptive_card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "text": f"{emoji} {notification.message}",
                "weight": "Bolder",
                "size": "Medium",
                "wrap": True,
            },
            {"type": "FactSet", "facts": facts},
        ],
    }
    return {
        "type": "message",
        "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": adaptive_card}],
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
