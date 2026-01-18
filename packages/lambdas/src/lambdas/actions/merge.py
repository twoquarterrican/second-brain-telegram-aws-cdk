"""Merge action - merge one item into another."""

from typing import Mapping, Any

from lambdas.adapter.out.persistence.dynamo_table import get_second_brain_table
from lambdas.telegram.telegram_messages import (
    send_telegram_message,
    TelegramWebhookEvent,
)


def handle(event_model: TelegramWebhookEvent, **kwargs) -> Mapping[str, Any]:
    """Merge FROM item INTO INTO item."""
    # Extract text and chat_id from event model
    message = event_model.message
    if not message or not message.text:
        return {"statusCode": 400, "body": "No message text"}

    text = message.text
    chat_id = str(message.chat.id)

    # Get table from environment
    table = get_second_brain_table()

    parts = text.split()
    if len(parts) != 3:
        send_telegram_message(chat_id, "Usage: /merge FROM_ID INTO_ID")
        return {"statusCode": 200, "body": "Merge command processed"}

    from_id, into_id = parts[1], parts[2]

    from_item = None
    into_item = None
    for item in table.scan().get("Items", []):
        sk_prefix = item.get("SK", "")
        if sk_prefix.startswith(from_id + "#"):
            from_item = item
        elif sk_prefix.startswith(into_id + "#"):
            into_item = item

    if not from_item:
        send_telegram_message(chat_id, f"❌ Item {from_id} not found")
        return {"statusCode": 200, "body": "Merge command processed"}

    if not into_item:
        send_telegram_message(chat_id, f"❌ Item {into_id} not found")
        return {"statusCode": 200, "body": "Merge command processed"}

    merged_notes = []
    if from_item.get("notes"):
        merged_notes.append(f"[From {from_id}]: {from_item['notes']}")
    if into_item.get("notes"):
        merged_notes.append(f"[Original]: {into_item['notes']}")

    table.update_item(
        Key={"PK": into_item["PK"], "SK": into_item["SK"]},
        UpdateExpression="SET #notes = :notes, #status = :status",
        ExpressionAttributeNames={"#notes": "notes", "#status": "status"},
        ExpressionAttributeValues={
            ":notes": "\n\n".join(merged_notes)
            if merged_notes
            else into_item.get("notes"),
            ":status": from_item.get("status", into_item.get("status", "open")),
        },
    )

    table.delete_item(Key={"PK": from_item["PK"], "SK": from_item["SK"]})

    send_telegram_message(chat_id, f"✅ Merged {from_id} into {into_id}")
    return {"statusCode": 200, "body": "Merge command processed"}
