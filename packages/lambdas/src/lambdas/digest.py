import json
import os
import logging
import boto3
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import requests

from common.logging import log_error

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
table_name = os.getenv("DDB_TABLE_NAME", "SecondBrain")
table = dynamodb.Table(table_name)

# Environment variables
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
USER_CHAT_ID = os.getenv("USER_CHAT_ID")

# Digest summary prompt
SUMMARY_PROMPT = """Generate a concise summary of the following items for a personal second brain digest. Group by category and highlight important items or those needing action.

Items:
{items}

Return a friendly, organized summary in Markdown format suitable for a Telegram message. Include:
- 📊 Overall stats (total items by category)
- 🔥 High priority items or those with next actions
- 📝 Brief highlights from each category
- ⏰ Any overdue items

Keep it concise but actionable."""


def get_open_items(days_back: int = 7) -> List[Dict[str, Any]]:
    """Get open items from the last N days."""
    try:
        start_date = (
            datetime.now(timezone.utc) - timedelta(days=days_back)
        ).isoformat()

        response = table.query(
            IndexName="StatusIndex",
            KeyConditionExpression="#s = :status AND created_at >= :start_date",
            FilterExpression="attribute_not_exists(#s) OR #s = :status OR #s = :in_progress",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":status": "open",
                ":in_progress": "in-progress",
                ":start_date": start_date,
            },
        )

        items = response.get("Items", [])
        logger.info(f"Found {len(items)} open items from last {days_back} days")

        return items
    except Exception as e:
        log_error("Error querying open items", str(e))
        return []


def get_completed_items(days_back: int = 30) -> List[Dict[str, Any]]:
    """Get completed items from the last N days."""
    try:
        start_date = (
            datetime.now(timezone.utc) - timedelta(days=days_back)
        ).isoformat()

        response = table.query(
            IndexName="StatusIndex",
            KeyConditionExpression="#s = :status AND created_at >= :start_date",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":status": "completed",
                ":start_date": start_date,
            },
        )

        items = response.get("Items", [])
        logger.info(f"Found {len(items)} completed items from last {days_back} days")

        return items
    except Exception as e:
        log_error("Error querying completed items", str(e))
        return []


def get_all_items(days_back: int = 7) -> List[Dict[str, Any]]:
    """Get all items from the last N days."""
    try:
        start_date = (
            datetime.now(timezone.utc) - timedelta(days=days_back)
        ).isoformat()

        response = table.scan(
            FilterExpression="created_at >= :start_date",
            ExpressionAttributeValues={":start_date": start_date},
        )

        items = response.get("Items", [])
        logger.info(f"Found {len(items)} total items from last {days_back} days")

        return items
    except Exception as e:
        log_error("Error scanning items", str(e))
        return []


def get_completed_items(days_back: int = 30) -> List[Dict[str, Any]]:
    """Get completed items from the last N days."""
    try:
        start_date = (
            datetime.now(timezone.utc) - timedelta(days=days_back)
        ).isoformat()

        response = table.query(
            IndexName="StatusIndex",
            KeyConditionExpression="#s = :status AND created_at >= :start_date",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":status": "completed",
                ":start_date": start_date,
            },
        )

        items = response.get("Items", [])
        logger.info(f"Found {len(items)} completed items from last {days_back} days")

        return items
    except Exception as e:
        logger.error(f"Error querying completed items: {e}")
        return []


def get_all_items(days_back: int = 7) -> List[Dict[str, Any]]:
    """Get all items from the last N days."""
    try:
        start_date = (
            datetime.now(timezone.utc) - timedelta(days=days_back)
        ).isoformat()

        # Scan all items and filter by date
        response = table.scan(
            FilterExpression="created_at >= :start_date",
            ExpressionAttributeValues={":start_date": start_date},
        )

        items = response.get("Items", [])
        logger.info(f"Found {len(items)} total items from last {days_back} days")

        return items
    except Exception as e:
        logger.error(f"Error scanning items: {e}")
        return []


def summarize_with_anthropic(items: List[Dict[str, Any]]) -> Optional[str]:
    """Generate summary using Anthropic Claude."""
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        # Format items for the prompt
        items_text = "\n".join(
            [
                f"- [{item.get('category', 'Unknown')}] {item.get('name', 'No name')} "
                f"(Status: {item.get('status', 'N/A')}, "
                f"Next Action: {item.get('next_action', 'None')}, "
                f"Notes: {item.get('notes', 'None')[:50]}{'...' if len(item.get('notes', '')) > 50 else ''})"
                for item in items
            ]
        )

        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1000,
            messages=[
                {"role": "user", "content": SUMMARY_PROMPT.format(items=items_text)}
            ],
        )

        return response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Anthropic summarization failed: {e}")
        return None


def summarize_with_openai(items: List[Dict[str, Any]]) -> Optional[str]:
    """Generate summary using OpenAI."""
    try:
        import openai

        client = openai.OpenAI(api_key=OPENAI_API_KEY)

        # Format items for the prompt
        items_text = "\n".join(
            [
                f"- [{item.get('category', 'Unknown')}] {item.get('name', 'No name')} "
                f"(Status: {item.get('status', 'N/A')}, "
                f"Next Action: {item.get('next_action', 'None')}, "
                f"Notes: {item.get('notes', 'None')[:50]}{'...' if len(item.get('notes', '')) > 50 else ''})"
                for item in items
            ]
        )

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": SUMMARY_PROMPT.format(items=items_text)}
            ],
            max_tokens=1000,
        )

        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"OpenAI summarization failed: {e}")
        return None


def send_telegram_message(chat_id: str, text: str) -> bool:
    """Send message via Telegram bot API."""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}

        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False


def generate_digest_summary(digest_type: str = "daily") -> Optional[str]:
    """Generate digest summary - callable from other Lambdas."""
    # Determine how many days to look back
    days_back = 1 if digest_type == "daily" else 7

    # Get items - only open/in-progress (no completed)
    items = get_open_items(days_back)

    if not items:
        return f"📝 No open items found in the last {days_back} days."

    # Try to generate AI summary
    summary = None
    if ANTHROPIC_API_KEY:
        summary = summarize_with_anthropic(items)
    elif OPENAI_API_KEY:
        summary = summarize_with_openai(items)

    # Fallback to simple summary if AI fails
    if not summary:
        # Group by category
        categories = {}
        for item in items:
            cat = item.get("category", "Unknown")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(item)

        # Build simple summary
        summary_lines = [f"📊 {digest_type.title()} Digest ({days_back} days)"]
        summary_lines.append(f"Open items: {len(items)}")

        for category, cat_items in categories.items():
            summary_lines.append(f"\n📂 {category}: {len(cat_items)} items")
            # Show items with next actions
            for item in cat_items:
                if item.get("next_action"):
                    name = item.get("name", "No name")
                    action = item.get("next_action")
                    summary_lines.append(f"  • {name}: {action}")

        summary = "\n".join(summary_lines)

    return summary


def handler(event, context):
    """Main Lambda handler for scheduled digest."""
    logger.info(f"Digest Lambda triggered: {json.dumps(event)}")

    try:
        # Determine digest type from event source or default to daily
        digest_type = "daily"
        if "resources" in event:
            for resource in event.get("resources", []):
                if "Weekly" in resource:
                    digest_type = "weekly"
                    break

        logger.info(f"Generating {digest_type} digest")

        # Generate summary using core function
        summary = generate_digest_summary(digest_type)
        if not summary:
            logger.error("Failed to generate digest summary")
            return {"statusCode": 500, "body": "Failed to generate digest"}

        # Send to Telegram
        if USER_CHAT_ID and send_telegram_message(USER_CHAT_ID, summary):
            logger.info(f"Successfully sent {digest_type} digest to Telegram")
            return {"statusCode": 200, "body": "Digest sent successfully"}
        else:
            logger.error("Failed to send digest to Telegram")
            return {"statusCode": 500, "body": "Failed to send digest"}

    except Exception as e:
        logger.error(f"Error generating digest: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }
