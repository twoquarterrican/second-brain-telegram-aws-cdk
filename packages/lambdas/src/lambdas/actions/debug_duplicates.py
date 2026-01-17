"""Debug duplicates action - find potential duplicate items using AI."""

import json
from datetime import datetime, timezone, timedelta


def handle(
    text: str, send_telegram_message, chat_id: str, table, ANTHROPIC_API_KEY, **kwargs
):
    """Find potential duplicate items."""
    import anthropic

    send_telegram_message(
        chat_id, "🔍 Analyzing items from last month for duplicates..."
    )

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
        send_telegram_message(chat_id, "📝 Not enough items to find duplicates.")
        return {"statusCode": 200, "body": "Duplicates command processed"}

    items_summary = []
    for item in all_items:
        summary = f"[ID:{item['id']}] {item.get('category', 'N/A')}: {item.get('name', 'N/A')} ({item.get('status', 'open')})"
        if item.get("next_action"):
            summary += f" - next: {item['next_action']}"
        items_summary.append(summary)

    items_text = "\n".join(items_summary)

    duplicate_prompt = f"""Analyze these items and find potential duplicates (items with similar names or topics):

{items_text}

Look for:
- Items with the same or very similar names
- Items that appear to be about the same topic
- Multiple items that should be consolidated

Return JSON with this structure:
{{
    "groups": [
        {{
            "reason": "explanation of why these are duplicates",
            "items": [{{"id": "item ID", "name": "item name", "category": "category"}}]
        }}
    ],
    "total_items": total items analyzed,
    "potential_duplicates": count of items in duplicate groups
}}

Only group items that are clearly duplicates. Return empty groups if items seem unique."""

    duplicates = None
    if ANTHROPIC_API_KEY:
        try:
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                messages=[{"role": "user", "content": duplicate_prompt}],
            )
            content = response.content[0].text.strip()
            if content.startswith("```json"):
                content = content[7:-3].strip()
            duplicates = json.loads(content)
        except Exception as e:
            send_telegram_message(chat_id, f"❌ AI duplicate detection failed: {{e}}")

    if not duplicates or not duplicates.get("groups"):
        send_telegram_message(
            chat_id,
            f"📊 Analyzed {{len(all_items)}} items. No obvious duplicates found.",
        )
        return {"statusCode": 200, "body": "Duplicates command processed"}

    lines = ["🔍 *Potential Duplicates Found*\n"]
    lines.append(
        f"Found {duplicates['potential_duplicates']} potential duplicates across {len(duplicates['groups'])} groups:\n"
    )

    for i, group in enumerate(duplicates["groups"], 1):
        lines.append(f"*Group {i}:* {group['reason']}")
        for item in group["items"]:
            lines.append(f"  • [ID:{item['id']}] {item['name']} ({item['category']})")
        lines.append("")

    lines.append("---")
    lines.append("*Resolution options:*")
    lines.append("  `/merge FROM_ID INTO_ID` - Merge FROM into INTO, keep both data")
    lines.append("  `/delete ID` - Delete this item")
    lines.append("  `/keep ID ID...` - Mark these as not duplicates")

    send_telegram_message(chat_id, "\n".join(lines))
    return {"statusCode": 200, "body": "Duplicates command processed"}
