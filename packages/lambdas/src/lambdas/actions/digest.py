"""Digest action - generate daily/weekly digest."""

from typing import Mapping, Any
from lambdas.digest import generate_digest_summary
from lambdas.processor import TelegramWebhookEvent
from lambdas.telegram.telegram_messages import send_telegram_message


def handle(event_model: TelegramWebhookEvent, **kwargs) -> Mapping[str, Any]:
    """Generate and send digest."""
    # Extract text from event model
    message = event_model.message
    if not message or not message.text:
        return {"statusCode": 400, "body": "No message text"}

    text = message.text
    chat_id = str(message.chat.id)

    digest_type = "daily" if "daily" in text.lower() else "weekly"
    summary = generate_digest_summary(digest_type)
    if summary:
        send_telegram_message(chat_id, summary)
    else:
        send_telegram_message(chat_id, "❌ Failed to generate digest")
    return {"statusCode": 200, "body": f"{digest_type} digest command processed"}
