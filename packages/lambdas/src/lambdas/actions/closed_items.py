"""Closed items action - list recently completed items."""

from typing import Mapping, Any
from lambdas.digest import get_completed_items
from lambdas.telegram.telegram_messages import send_telegram_message
from lambdas.events import MessageReceived


def handle(message_received_event: MessageReceived, **kwargs) -> Mapping[str, Any]:
    """List completed items grouped by category."""
    chat_id = message_received_event.chat_id

    if not chat_id:
        return {"statusCode": 400, "body": "No chat ID"}
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
