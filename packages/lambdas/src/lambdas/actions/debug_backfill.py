"""Debug backfill action - backfill GSI for items from last week."""

from datetime import datetime, timezone, timedelta
from typing import Mapping, Any

from lambdas.adapter.out.persistence.dynamo_table import get_second_brain_table
from lambdas.telegram.telegram_messages import send_telegram_message, TelegramWebhookEvent


def handle(event_model: TelegramWebhookEvent, **kwargs) -> Mapping[str, Any]:
    """Backfill GSI for items from last week."""
    # Extract chat_id from event model
    message = event_model.message
    if not message:
        return {"statusCode": 400, "body": "No message data"}

    chat_id = str(message.chat.id)

    # Get table from environment
    table = get_second_brain_table()

    send_telegram_message(chat_id, "🔄 Backfilling GSI for items from last week...")

    start_date = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    categories = ["People", "Projects", "Ideas", "Admin"]
    backfilled_by_status = {}
    total_items = 0

    for category in categories:
        response = table.query(
            KeyConditionExpression="PK = :pk AND SK >= :start_date",
            ExpressionAttributeValues={
                ":pk": f"CATEGORY#{category}",
                ":start_date": start_date,
            },
        )
        items = response.get("Items", [])

        for item in items:
            status = item.get("status", "none")
            backfilled_by_status[status] = backfilled_by_status.get(status, 0) + 1
            total_items += 1
            table.put_item(Item=item)

    if total_items == 0:
        send_telegram_message(chat_id, "📝 No items found from last week.")
        return {"statusCode": 200, "body": "Backfill command processed"}

    lines = ["✅ *Backfill Complete*"]
    lines.append(f"\nBackfilled {total_items} items from last week.")
    lines.append("\n📊 By status:")
    for status, count in sorted(backfilled_by_status.items()):
        status_label = status if status != "none" else "no status"
        lines.append(f"   • {status_label}: {count}")

    send_telegram_message(chat_id, "\n".join(lines))
    return {"statusCode": 200, "body": "Backfill command processed"}
