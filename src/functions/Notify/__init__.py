"""
Notify queue function - Send Teams webhook notifications.

Formats and posts simple message cards to Teams channel
for success, unknown vendor, and error notifications.
"""
import os
import logging
import requests
import azure.functions as func
from shared.models import NotificationMessage, TeamsMessageCard, MessageCardSection, MessageCardFact

logger = logging.getLogger(__name__)


def _build_teams_card(notification: NotificationMessage) -> TeamsMessageCard:
    """Build Teams message card from notification."""
    color_map = {'success': '00FF00', 'unknown': 'FFA500', 'error': 'FF0000'}
    facts = [MessageCardFact(name=k.title(), value=v) for k, v in notification.details.items()]

    return TeamsMessageCard(
        themeColor=color_map.get(notification.type, '808080'),
        text=notification.message,
        sections=[MessageCardSection(facts=facts)]
    )


def main(msg: func.QueueMessage):
    """Post notification to Teams webhook."""
    try:
        notification = NotificationMessage.model_validate_json(msg.get_body().decode())
        card = _build_teams_card(notification)

        webhook_url = os.environ.get('TEAMS_WEBHOOK_URL')
        if not webhook_url:
            logger.warning("Teams webhook URL not configured, skipping notification")
            return

        response = requests.post(webhook_url, json=card.model_dump(by_alias=True), timeout=10)
        response.raise_for_status()
        logger.info(f"Posted {notification.type} notification to Teams")
    except Exception as e:
        # Non-critical: log but don't raise (per CLAUDE.md)
        logger.warning(f"Teams notification failed (non-critical): {str(e)}")
