"""Debug duplicates-auto action - auto-deduplicate items using AI."""

import json
from datetime import datetime, timezone, timedelta
from typing import Mapping, Any

from anthropic.types import MessageParam

from lambdas.adapter.out.persistence.dynamo_table import get_second_brain_table
from lambdas.telegram.telegram_messages import send_telegram_message
from common.environments import get_env
from lambdas.events import MessageReceived


def handle(message_received_event: MessageReceived) -> Mapping[str, Any]:
    """Auto-deduplicate items from last month."""
    import anthropic

    chat_id = message_received_event.chat_id

    if not chat_id:
        return {"statusCode": 400, "body": "No chat ID"}

    # Get table and API key from environment
    table = get_second_brain_table()

    send_telegram_message(chat_id, "🔄 Auto-deduplicating items from last month...")

    start_date = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    categories = ["People", "Projects", "Ideas", "Admin"]
    all_items = []

    for category in categories:
        response = table.query(
            KeyConditionExpression="PK = :pk AND SK >= :start_date",
            ExpressionAttributeValues={
                ":pk": f"CATEGORY#{category}",
                ":start_date": start_date,
            },
        )
        for item in response.get("Items", []):
            item["id"] = item["SK"].split("#")[0]
            all_items.append(item)

    if len(all_items) < 2:
        send_telegram_message(chat_id, "📝 Not enough items to deduplicate.")
        return {"statusCode": 200, "body": "Duplicates-auto command processed"}

    items_summary = []
    for item in all_items:
        summary = f"[ID:{item['id']}] {item.get('category', 'N/A')}: {item.get('name', 'N/A')} ({item.get('status', 'open')})"
        if item.get("notes"):
            summary += f" - notes: {item['notes'][:100]}"
        items_summary.append(summary)

    items_text = "\n".join(items_summary)

    auto_prompt = f"""Analyze these items and automatically deduplicate. Return JSON with actions to take:

{items_text}

Return JSON:
{{
    "actions": [
        {{
            "action": "merge|delete|keep",
            "from_id": "ID of item to merge/delete (or null)",
            "into_id": "ID of item to merge into (or null)",
            "reason": "why this action"
        }}
    ],
    "summary": "brief summary of what was done"
}}

Rules:
- If items have same name and one is completed, merge completed into open and delete completed
- If items are clearly about same topic, merge newer into older, delete newer
- Keep items that are clearly different topics
- Use "keep" action to mark items as not duplicates"""

    result = None
    anthropic_api_key = get_env("ANTHROPIC_API_KEY", required=False)
    if anthropic_api_key:
        try:
            client = anthropic.Anthropic(api_key=anthropic_api_key)
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                messages=[MessageParam(role="user", content=auto_prompt)],
            )
            content = response.content[0].text.strip()
            if content.startswith("```json"):
                content = content[7:-3].strip()
            result = json.loads(content)
        except Exception as e:
            send_telegram_message(chat_id, f"❌ AI auto-deduplication failed: {e}")

    if not result or not result.get("actions"):
        send_telegram_message(chat_id, "📊 No automatic deduplication needed.")
        return {"statusCode": 200, "body": "Duplicates-auto command processed"}

    merged_count = 0
    deleted_count = 0
    kept_count = 0

    id_to_item = {}
    for item in all_items:
        id_to_item[item["id"]] = item

    for action in result["actions"]:
        action_type = action.get("action")
        from_id = action.get("from_id")
        into_id = action.get("into_id")

        if action_type == "merge" and from_id and into_id:
            from_item = id_to_item.get(from_id)
            into_item = id_to_item.get(into_id)
            if from_item and into_item:
                merged_notes = []
                if from_item.get("notes"):
                    merged_notes.append(f"[From {from_id}]: {from_item['notes']}")
                if into_item.get("notes"):
                    merged_notes.append(f"[Original]: {into_item['notes']}")

                table.update_item(
                    Key={"PK": into_item["PK"], "SK": into_item["SK"]},
                    UpdateExpression="SET #notes = :notes, #status = :status",
                    ExpressionAttributeNames={
                        "#notes": "notes",
                        "#status": "status",
                    },
                    ExpressionAttributeValues={
                        ":notes": "\n\n".join(merged_notes)
                        if merged_notes
                        else into_item.get("notes"),
                        ":status": from_item.get(
                            "status", into_item.get("status", "open")
                        ),
                    },
                )
                table.delete_item(Key={"PK": from_item["PK"], "SK": from_item["SK"]})
                merged_count += 1

        elif action_type == "delete" and from_id:
            from_item = id_to_item.get(from_id)
            if from_item:
                table.delete_item(Key={"PK": from_item["PK"], "SK": from_item["SK"]})
                deleted_count += 1

        elif action_type == "keep":
            kept_count += 1

    lines = [
        "✅ *Auto-Deduplication Complete*",
        f"\n📊 {result.get('summary', 'Done')}",
        f"\n• Merged: {merged_count}",
        f"• Deleted: {deleted_count}",
        f"• Kept: {kept_count}",
    ]

    send_telegram_message(chat_id, "\n".join(lines))
    return {"statusCode": 200, "body": "Duplicates-auto command processed"}
