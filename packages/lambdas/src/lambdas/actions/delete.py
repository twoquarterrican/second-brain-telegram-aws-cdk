"""Delete action - delete an item."""


def handle(text: str, send_telegram_message, chat_id: str, table, **kwargs):
    """Delete an item by ID."""
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
