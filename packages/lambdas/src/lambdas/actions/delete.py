"""Delete action - delete an item."""

from typing import Mapping, Any

from lambdas.adapter.out.persistence.dynamo_table import get_second_brain_table
from lambdas.telegram.telegram_messages import send_telegram_message
from lambdas.events import MessageReceived


def handle(message_received_event: MessageReceived, **kwargs) -> Mapping[str, Any]:
    """Delete an item by ID."""
    text = message_received_event.raw_text
    chat_id = message_received_event.chat_id

    if not chat_id:
        return {"statusCode": 400, "body": "No chat ID"}

    # Get table from environment
    table = get_second_brain_table()

    parts = text.split()
    if len(parts) != 2:
        send_telegram_message(chat_id, "Usage: /delete ID")
        return {"statusCode": 200, "body": "Delete command processed"}

    item_id = parts[1]

    for item in table.scan().get("Items", []):
        if item.get("SK", "").startswith(item_id + "#"):
            table.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})
            send_telegram_message(chat_id, f"✅ Deleted item {item_id}")
            return {"statusCode": 200, "body": "Delete command processed"}

    send_telegram_message(chat_id, f"❌ Item {item_id} not found")
    return {"statusCode": 200, "body": "Delete command processed"}
