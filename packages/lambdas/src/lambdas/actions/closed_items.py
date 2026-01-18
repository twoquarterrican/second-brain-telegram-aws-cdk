"""Closed items action - list recently completed items."""

from typing import Mapping, Any
from lambdas.digest import get_completed_items
from lambdas.processor import TelegramWebhookEvent
from lambdas.telegram.telegram_messages import send_telegram_message


def handle(event_model: TelegramWebhookEvent, **kwargs) -> Mapping[str, Any]:
    """List completed items grouped by category."""
    # Extract chat_id from event model
    message = event_model.message
    if not message:
        return {"statusCode": 400, "body": "No message data"}

    chat_id = str(message.chat.id)
    items = get_completed_items(days_back=30)
    if items:
        categories = {}
        for item in items:
            cat = item.get("category", "Unknown")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(item)

        lines = ["✅ *Recently Completed*"]
        for cat, cat_items in categories.items():
            lines.append(f"\n📂 *{cat}* ({len(cat_items)})")
            for item in cat_items:
                name = item.get("name", "No name")
                lines.append(f"  ✓ {name}")

        send_telegram_message(chat_id, "\n".join(lines))
    else:
        send_telegram_message(chat_id, "📝 No completed items found.")
    return {"statusCode": 200, "body": "Closed command processed"}
