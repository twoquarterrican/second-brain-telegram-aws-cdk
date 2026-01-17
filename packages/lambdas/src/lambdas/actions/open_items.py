"""Open items action - list all open items by category."""

from lambdas.digest import get_open_items


def handle(text: str, send_telegram_message, chat_id: str, **kwargs):
    """List open items grouped by category."""
    items = get_open_items(days_back=30)
    if items:
        categories = {}
        for item in items:
            cat = item.get("category", "Unknown")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(item)

        lines = ["📋 *Open Items*"]
        for cat, cat_items in categories.items():
            lines.append(f"\n📂 *{cat}* ({len(cat_items)})")
            for item in cat_items:
                name = item.get("name", "No name")
                action = item.get("next_action", "No action")
                status = item.get("status", "open")
                status_emoji = "🔄" if status == "in-progress" else "📌"
                lines.append(f"{status_emoji} {name}")
                if action and action != "No action":
                    lines.append(f"   → {action}")

        send_telegram_message(chat_id, "\n".join(lines))
    else:
        send_telegram_message(chat_id, "📝 No open items found.")
    return {"statusCode": 200, "body": "Open command processed"}
