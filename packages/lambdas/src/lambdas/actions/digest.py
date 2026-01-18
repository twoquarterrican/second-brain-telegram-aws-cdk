"""Digest action - generate daily/weekly digest."""

from typing import Mapping, Any
from lambdas.digest import generate_digest_summary
from lambdas.telegram.telegram_messages import send_telegram_message
from lambdas.events import MessageReceived


def handle(message_received_event: MessageReceived, **kwargs) -> Mapping[str, Any]:
    """Generate and send digest."""
    text = message_received_event.raw_text
    chat_id = message_received_event.chat_id

    if not chat_id:
        return {"statusCode": 400, "body": "No chat ID"}

    digest_type = "daily" if "daily" in text.lower() else "weekly"
    summary = generate_digest_summary(digest_type)
    if summary:
        send_telegram_message(chat_id, summary)
    else:
        send_telegram_message(chat_id, "❌ Failed to generate digest")
    return {"statusCode": 200, "body": f"{digest_type} digest command processed"}
