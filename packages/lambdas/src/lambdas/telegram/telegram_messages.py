import requests
from pydantic import BaseModel, Field
from typing import Optional
from common.environments import get_env
import logging

logger = logging.getLogger(__name__)
TELEGRAM_BOT_TOKEN = get_env("TELEGRAM_BOT_TOKEN", required=True)


# Pydantic models for Telegram webhook events
class TelegramChat(BaseModel):
    """Telegram chat information."""

    id: int = Field(..., description="Unique chat identifier")


class TelegramMessage(BaseModel):
    """Telegram message structure."""

    message_id: str = Field(..., min_length=8, max_length=8, description="Unique message identifier")
    text: Optional[str] = Field(None, description="Message text content")
    chat: TelegramChat = Field(..., description="Chat information")


class TelegramWebhookEvent(BaseModel):
    """Telegram webhook event structure."""

    message: Optional[TelegramMessage] = Field(None, description="Message data")

def send_telegram_message(chat_id: str, text: str) -> bool:
    """Send message via Telegram bot API."""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}

        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}", exc_info=True)
        return False
