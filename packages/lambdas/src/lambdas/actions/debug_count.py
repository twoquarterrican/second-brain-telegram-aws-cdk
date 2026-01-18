"""Debug count action - count items by category and status."""

from typing import Mapping, Any

from lambdas.adapter.out.persistence.dynamo_table import get_second_brain_table
from lambdas.telegram.telegram_messages import send_telegram_message
from lambdas.events import MessageReceived


def count_items(table):
    """Count items by category and status."""
    response = table.scan()
    items = response.get("Items", [])

    counts = {}
    for item in items:
        cat = item.get("category", "Unknown")
        status = item.get("status", "none")

        if cat not in counts:
            counts[cat] = {}
        if status not in counts[cat]:
            counts[cat][status] = 0
        counts[cat][status] += 1

    return counts


def handle(message_received_event: MessageReceived, **kwargs) -> Mapping[str, Any]:
    """Count and report item counts."""
    chat_id = message_received_event.chat_id

    if not chat_id:
        return {"statusCode": 400, "body": "No chat ID"}

    # Get table from environment
    table = get_second_brain_table()

    counts = count_items(table)

    if not counts:
        send_telegram_message(chat_id, "❌ Failed to count items or table is empty.")
    else:
        lines = ["🔢 *Item Counts*"]
        grand_total = 0
        for cat, status_counts in sorted(counts.items()):
            cat_total = sum(status_counts.values())
            grand_total += cat_total
            lines.append(f"\n📂 *{cat}* (total: {cat_total})")
            for status, count in status_counts.items():
                status_label = status if status != "none" else "no status"
                lines.append(f"   • {status_label}: {count}")

        lines.append(f"\n🏁 Grand total: {grand_total}")
        send_telegram_message(chat_id, "\n".join(lines))

    return {"statusCode": 200, "body": "Debug count command processed"}
