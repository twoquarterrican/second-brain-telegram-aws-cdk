"""Merge action - merge one item into another."""


def handle(text: str, send_telegram_message, chat_id: str, table, **kwargs):
    """Merge FROM item INTO INTO item."""
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
