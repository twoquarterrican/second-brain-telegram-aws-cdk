import json
import os
import sys
import logging
import boto3
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import requests

# Add parent directory to path for aws_helper
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from aws_helper import get_boto3_resource

    HAS_AWS_HELPER = True
except ImportError:
    HAS_AWS_HELPER = False

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
if HAS_AWS_HELPER:
    dynamodb = get_boto3_resource("dynamodb")
else:
    dynamodb = boto3.resource("dynamodb")

table_name = os.getenv("DDB_TABLE_NAME", "SecondBrain")
table = dynamodb.Table(table_name)

# Environment variables
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_SECRET_TOKEN = os.getenv("TELEGRAM_SECRET_TOKEN")
USER_CHAT_ID = os.getenv("USER_CHAT_ID")

# AI Classification prompt
CLASSIFICATION_PROMPT = """Classify the following message into one of these categories: People, Projects, Ideas, Admin.

Extract the following fields if present:
- name: A short title/name for this item
- status: Current status (e.g., "open", "in-progress", "completed", "waiting")
- next_action: Next specific action to take
- notes: Additional details or context

Return ONLY a JSON object with this structure:
{
    "category": "People|Projects|Ideas|Admin",
    "name": "string or null",
    "status": "string or null", 
    "next_action": "string or null",
    "notes": "string or null",
    "confidence": 0-100
}

Message: {message}"""


def verify_webhook_secret(request_body: bytes, secret_token: str) -> bool:
    """Verify Telegram webhook secret token."""
    # Telegram uses X-Telegram-Bot-Api-Secret-Token header
    # For simplicity, we'll check if the secret matches
    return secret_token == TELEGRAM_SECRET_TOKEN


def classify_with_anthropic(message: str) -> Optional[Dict[str, Any]]:
    """Classify message using Anthropic Claude."""
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=500,
            messages=[
                {
                    "role": "user",
                    "content": CLASSIFICATION_PROMPT.format(message=message),
                }
            ],
        )

        content = response.content[0].text.strip()
        # Extract JSON from response
        if content.startswith("```json"):
            content = content[7:-3].strip()

        return json.loads(content)
    except Exception as e:
        logger.error(f"Anthropic classification failed: {e}")
        return None


def classify_with_openai(message: str) -> Optional[Dict[str, Any]]:
    """Classify message using OpenAI."""
    try:
        import openai

        client = openai.OpenAI(api_key=OPENAI_API_KEY)

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "user",
                    "content": CLASSIFICATION_PROMPT.format(message=message),
                }
            ],
            max_tokens=500,
        )

        content = response.choices[0].message.content.strip()
        if content.startswith("```json"):
            content = content[7:-3].strip()

        return json.loads(content)
    except Exception as e:
        logger.error(f"OpenAI classification failed: {e}")
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


def save_to_dynamodb(item_data: Dict[str, Any]) -> bool:
    """Save classified item to DynamoDB."""
    try:
        timestamp = datetime.now(timezone.utc).isoformat()
        uuid = f"{timestamp}#{item_data['category']}#{hash(item_data['original_text']) % 10000}"

        item = {
            "PK": f"CATEGORY#{item_data['category']}",
            "SK": uuid,
            "created_at": timestamp,
            "status": item_data.get("status", "open"),
            "name": item_data.get("name"),
            "next_action": item_data.get("next_action"),
            "notes": item_data.get("notes"),
            "original_text": item_data["original_text"],
            "confidence": item_data["confidence"],
            "category": item_data["category"],
        }

        table.put_item(Item=item)
        logger.info(f"Saved item to DynamoDB: {item['PK']}#{item['SK']}")
        return True
    except Exception as e:
        logger.error(f"Failed to save to DynamoDB: {e}")
        return False


def process_message(message: str) -> Dict[str, Any]:
    """Process and classify a message."""
    # Try Anthropic first, fallback to OpenAI
    result = classify_with_anthropic(message)
    if not result and OPENAI_API_KEY:
        result = classify_with_openai(message)

    if not result:
        raise Exception("Both AI classification attempts failed")

    # Add original text to result
    result["original_text"] = message

    # Validate confidence
    confidence = result.get("confidence", 0)
    if not isinstance(confidence, int):
        try:
            confidence = int(float(confidence))
        except:
            confidence = 0

    result["confidence"] = min(100, max(0, confidence))

    return result


def handler(event, context):
    """Main Lambda handler for Telegram webhook."""
    logger.info(f"Received event: {json.dumps(event)}")

    # Verify webhook secret
    headers = event.get("headers", {})
    if (
        TELEGRAM_SECRET_TOKEN
        and headers.get("x-telegram-bot-api-secret-token") != TELEGRAM_SECRET_TOKEN
    ):
        logger.warning("Invalid webhook secret")
        return {"statusCode": 403, "body": "Forbidden"}

    try:
        # Parse webhook body
        if isinstance(event.get("body"), str):
            webhook_data = json.loads(event["body"])
        else:
            webhook_data = event["body"]

        # Extract message
        message = webhook_data.get("message", {})
        text = message.get("text", "")
        chat_id = str(message.get("chat", {}).get("id", ""))

        if not text:
            logger.warning("No text in message")
            return {"statusCode": 200, "body": "No text to process"}

        logger.info(f"Processing message from chat {chat_id}: {text[:100]}...")

        # Process and classify message
        result = process_message(text)

        # Save to DynamoDB if confidence >= 60%
        if result["confidence"] >= 60:
            if save_to_dynamodb(result):
                # Send confirmation message
                category = result["category"]
                confidence = result["confidence"]
                reply = f"✅ Saved as *{category}* (confidence: {confidence}%)"

                if result.get("name"):
                    reply += f"\n📝 *{result['name']}*"

                send_telegram_message(chat_id, reply)

                logger.info(f"Successfully processed and saved message")
            else:
                send_telegram_message(chat_id, "❌ Failed to save your message")
        else:
            reply = f"⚠️ Low confidence ({result['confidence']}%) - not saved. Please rephrase."
            send_telegram_message(chat_id, reply)

        return {"statusCode": 200, "body": "Message processed successfully"}

    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }
