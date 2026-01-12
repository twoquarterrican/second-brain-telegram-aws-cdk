import json
import os
import logging
import boto3
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger()
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))


def send_telegram_notification(message: str, chat_id: Optional[str] = None) -> bool:
    """Send notification message to Telegram user"""
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not chat_id:
        chat_id = os.getenv("USER_CHAT_ID")

    if not chat_id or not TELEGRAM_BOT_TOKEN:
        logger.warning("Cannot send notification: missing chat_id or bot token")
        return False

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            logger.info("Notification sent to Telegram")
            return True
        else:
            logger.error(f"Failed to send notification: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error sending Telegram notification: {e}")
        return False


def validate_ai_tokens() -> bool:
    """Check if AI tokens are configured"""
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    if not ANTHROPIC_API_KEY and not OPENAI_API_KEY:
        error_msg = (
            "⚠️ *Digest Error*\n\n"
            "No AI API keys found for digest generation.\n\n"
            "Please set either:\n"
            "• `ANTHROPIC_API_KEY` (Claude)\n"
            "• `OPENAI_API_KEY` (OpenAI)\n\n"
            "Check your SAM environment variables configuration."
        )
        send_telegram_notification(error_msg)
        return False
    return True


try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger()
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.getenv("DDB_TABLE_NAME"))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
USER_CHAT_ID = os.getenv("USER_CHAT_ID")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

DIGEST_PROMPT = """
You are creating a digest for a personal second brain system. Based on the following data, create a concise summary that highlights:
1. Open items that need attention
2. Recent additions
3. Action items

Data:
{data}

Create a friendly, motivating summary with clear sections and actionable insights. Keep it under 500 words.
"""


def query_open_items() -> List[Dict[str, Any]]:
    """Query for open items across all categories"""
    try:
        response = table.query(
            IndexName="StatusIndex",
            KeyConditionExpression="status = :status",
            FilterExpression="attribute_not_exists(completed_at)",
            ExpressionAttributeValues={":status": "open"},
        )
        return response.get("Items", [])
    except Exception as e:
        logger.error(f"Failed to query open items: {e}")
        return []


def query_recent_items(days: int = 7) -> List[Dict[str, Any]]:
    """Query for items created in the last N days"""
    try:
        cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()

        # Scan for recent items (DynamoDB doesn't support range queries on SK without knowing PK)
        response = table.scan(
            FilterExpression="created_at >= :cutoff",
            ExpressionAttributeValues={":cutoff": cutoff_date},
            ProjectionExpression="PK, category, name, status, next_action, created_at, notes",
        )
        return response.get("Items", [])
    except Exception as e:
        logger.error(f"Failed to query recent items: {e}")
        return []


def generate_digest_with_ai(
    open_items: List[Dict], recent_items: List[Dict]
) -> Optional[str]:
    """Generate digest summary using AI"""

    data = {
        "open_items": open_items,
        "recent_items": recent_items,
        "total_open": len(open_items),
        "total_recent": len(recent_items),
    }

    data_str = json.dumps(data, indent=2, default=str)

    # Try Claude first
    if ANTHROPIC_API_KEY and Anthropic:
        try:
            client = Anthropic(api_key=ANTHROPIC_API_KEY)
            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1000,
                messages=[
                    {"role": "user", "content": DIGEST_PROMPT.format(data=data_str)}
                ],
            )

            return response.content[0].text.strip()

        except Exception as e:
            logger.warning(f"Claude digest generation failed: {e}")

    # Fallback to OpenAI
    if OPENAI_API_KEY and OpenAI:
        try:
            client = OpenAI(api_key=OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "user", "content": DIGEST_PROMPT.format(data=data_str)}
                ],
                temperature=0.7,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"OpenAI digest generation failed: {e}")

    # Fallback to basic summary
    return create_basic_digest(open_items, recent_items)


def create_basic_digest(open_items: List[Dict], recent_items: List[Dict]) -> str:
    """Create a basic digest without AI"""
    digest = "🧠 *Second Brain Digest*\n\n"

    if open_items:
        digest += f"📋 *{len(open_items)} Open Items*\n"
        for item in open_items[:5]:  # Limit to top 5
            category = item.get("category", "Unknown")
            name = item.get("name", "Untitled")
            next_action = item.get("next_action", "")

            digest += f"• [{category}] {name}"
            if next_action:
                digest += f" - {next_action}"
            digest += "\n"

        if len(open_items) > 5:
            digest += f"... and {len(open_items) - 5} more\n"
        digest += "\n"

    if recent_items:
        digest += f"🆕 *{len(recent_items)} Recent Additions*\n"
        for item in recent_items[:3]:  # Limit to top 3
            category = item.get("category", "Unknown")
            name = item.get("name", "Untitled")
            created_at = item.get("created_at", "")

            digest += f"• [{category}] {name}\n"

        if len(recent_items) > 3:
            digest += f"... and {len(recent_items) - 3} more\n"

    if not open_items and not recent_items:
        digest += "No recent activity or open items. Keep capturing your thoughts!\n"

    return digest




    except Exception as e:
        logger.error(f"Error sending Telegram message: {e}")
        return False


def lambda_handler(event, context):
    """Main Lambda handler for scheduled digest"""

    # Validate AI tokens first
    if not validate_ai_tokens():
        return {"statusCode": 500, "body": "Configuration error"}

    logger.info("Starting digest generation")

    try:
        # Determine digest type from event source
        source = event.get("source", "")
        digest_type = "daily" if "Daily" in source else "weekly"
        recent_days = 1 if digest_type == "daily" else 7

        logger.info(f"Generating {digest_type} digest for last {recent_days} days")

        # Query data
        open_items = query_open_items()
        recent_items = query_recent_items(recent_days)

        logger.info(
            f"Found {len(open_items)} open items and {len(recent_items)} recent items"
        )

        if not open_items and not recent_items:
            logger.info("No items to include in digest")
            return {"statusCode": 200, "body": "No digest needed"}

        # Generate digest
        digest_text = generate_digest_with_ai(open_items, recent_items)

        if not digest_text:
            logger.error("Failed to generate digest")
            return {"statusCode": 500, "body": "Digest generation failed"}

        # Add header
        header = f"📅 {digest_type.title()} Digest - {datetime.utcnow().strftime('%Y-%m-%d')}\n\n"
        full_message = header + digest_text

        # Send to Telegram
        TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
        USER_CHAT_ID = os.getenv("USER_CHAT_ID")
        
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": USER_CHAT_ID,
                "text": full_message,
                "parse_mode": "Markdown"
            }
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                logger.info(f"{digest_type.title()} digest sent successfully")
                return {"statusCode": 200, "body": f"{digest_type.title()} digest sent"}
            else:
                logger.error("Failed to send digest to Telegram")
                return {"statusCode": 500, "body": "Failed to send digest"}

    except Exception as e:
        logger.error(f"Unexpected error in digest Lambda: {e}")
        error_msg = (
            f"⚠️ *Digest Error*\n\n"
            f"Something went wrong generating your {digest_type} digest.\n\n"
            f"📋 Details:\n"
            f"Error: {str(e)}\n"
            f"Time: {datetime.utcnow().isoformat()}\n\n"
            f"🔍 Check CloudWatch logs for more details:\n"
            f"AWS Console → Lambda → Functions → SecondBrainDigest → Monitor → Logs"
        )
        send_telegram_notification(error_msg)
        return {"statusCode": 500, "body": "Internal server error"}
