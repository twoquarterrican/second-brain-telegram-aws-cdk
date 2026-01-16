import json
import os
import sys
import logging
import boto3
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import requests

from lambdas.digest import generate_digest_summary, get_open_items


# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")

table_name = os.getenv("DDB_TABLE_NAME", "SecondBrain")
table = dynamodb.Table(table_name)


def _get_env(key: str, default: str = "") -> str | None:
    value = os.getenv(key, default).strip()
    if value in ["", "-"] or value is None:
        return None
    return value


# Environment variables
ANTHROPIC_API_KEY = _get_env("ANTHROPIC_API_KEY")
OPENAI_API_KEY = _get_env("OPENAI_API_KEY")
BEDROCK_REGION = _get_env("BEDROCK_REGION", "us-east-1")
TELEGRAM_BOT_TOKEN = _get_env("TELEGRAM_BOT_TOKEN")
TELEGRAM_SECRET_TOKEN = _get_env("TELEGRAM_SECRET_TOKEN")
USER_CHAT_ID = _get_env("USER_CHAT_ID")

# AI Classification prompt
CLASSIFICATION_PROMPT = """Classify the following message into one of these categories: People, Projects, Ideas, Admin.

Extract following fields if present:
- name: A short title/name for this item
- status: Current status (e.g., "open", "in-progress", "completed", "waiting")
- next_action: Next specific action to take
- notes: Additional details or context

Return ONLY a JSON object with this structure:
{{
    "category": "People|Projects|Ideas|Admin",
    "name": "string or null",
    "status": "string or null", 
    "next_action": "string or null",
    "notes": "string or null",
    "confidence": 0-100
}}

Message: {message}"""


def classify_with_anthropic(message: str) -> Optional[Dict[str, Any]]:
    """Classify message using Anthropic Claude."""
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        # noinspection PyTypeChecker
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
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
        logger.error(f"Anthropic classification failed: {e}", exc_info=e)
        return None


def classify_with_openai(message: str) -> Optional[Dict[str, Any]]:
    """Classify message using OpenAI."""
    try:
        import openai

        client = openai.OpenAI(api_key=OPENAI_API_KEY)

        # noinspection PyTypeChecker
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


def classify_with_bedrock(message: str) -> Optional[Dict[str, Any]]:
    """Classify message using AWS Bedrock."""
    try:
        import boto3

        # Create Bedrock client with region-specific config
        bedrock_config = {
            "region_name": BEDROCK_REGION,
            "config": botocore.Config(read_timeout=60, retries={"max_attempts": 3}),
        }
        bedrock = boto3.client("bedrock-runtime", **bedrock_config)

        # Use Anthropic Claude via Bedrock with provisioned throughput
        try:
            response = bedrock.converse(
                modelId="anthropic.claude-3-haiku-20240307-v1:0",
                messages=[
                    {
                        "role": "user",
                        "content": CLASSIFICATION_PROMPT.format(message=message),
                    }
                ],
                max_tokens=500,
                temperature=0.1,
                additional_model_request_fields={
                    "throughput_config": {"throughput_mode": "provisioned"}
                },
            )
        except Exception as provisioned_error:
            logger.warning(
                f"Provisioned throughput failed, trying on-demand: {provisioned_error}"
            )
            # Fallback to on-demand
            response = bedrock.converse(
                modelId="anthropic.claude-3-haiku-20240307-v1:0",
                messages=[
                    {
                        "role": "user",
                        "content": CLASSIFICATION_PROMPT.format(message=message),
                    }
                ],
                max_tokens=500,
                temperature=0.1,
            )

        # Extract content from Bedrock response
        content = response["output"]["message"]["content"]
        if content.startswith("```json"):
            content = content[7:-3].strip()

        return json.loads(content)
    except Exception as e:
        logger.error(f"Bedrock classification failed: {e}", exc_info=e)
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
    # Try Anthropic first, then OpenAI, then Bedrock
    result = None
    if ANTHROPIC_API_KEY:
        result = classify_with_anthropic(message)
    if not result and OPENAI_API_KEY:
        result = classify_with_openai(message)
    if not result and BEDROCK_REGION:
        result = classify_with_bedrock(message)

    if not result:
        raise Exception("All AI classification attempts failed")

    # Add original text to result
    result["original_text"] = message

    # Validate confidence
    confidence = result.get("confidence", 0)
    if not isinstance(confidence, int):
        try:
            confidence = int(float(confidence))
        except (ValueError, TypeError):
            confidence = 0

    result["confidence"] = min(100, max(0, confidence))

    return result


def handler(event, _context):
    """Main Lambda handler for Telegram webhook."""
    import uuid

    message_id = str(uuid.uuid4())[:8]  # Add unique ID for debugging
    logger.info(f"[{message_id}] Received event: {json.dumps(event)}")

    # Verify webhook secret
    headers = event.get("headers", {})
    received_secret = headers.get("x-telegram-bot-api-secret-token")
    expected_secret = TELEGRAM_SECRET_TOKEN

    if expected_secret and received_secret != expected_secret:
        logger.error(f"❌ Invalid webhook secret")
        logger.error(f"  Expected: {expected_secret}")
        logger.error(f"  Received: {received_secret}")
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
        snippet = text[:50]

        # Extract unique message identifier to detect duplicates
        message_unique_id = message.get("message_id", "")

        if not text:
            logger.warning("No text in message")
            return {"statusCode": 200, "body": "No text to process"}

        logger.info(
            f"[{message_id}] Processing message {message_unique_id}: {snippet}..."
        )

        logger.info(f"Processing message from chat {chat_id}: {snippet}...")

        # Handle commands
        if text.startswith("/digest"):
            digest_type = "daily" if "daily" in text.lower() else "weekly"
            logger.info(f"[{message_id}] Generating {digest_type} digest")
            summary = generate_digest_summary(digest_type)
            if summary:
                send_telegram_message(chat_id, summary)
            else:
                send_telegram_message(chat_id, "❌ Failed to generate digest")
            return {"statusCode": 200, "body": "Digest command processed"}

        if text.startswith("/open"):
            logger.info(f"[{message_id}] Getting open items")
            items = get_open_items(days_back=30)
            if items:
                # Group by category
                categories = {}
                for item in items:
                    cat = item.get("category", "Unknown")
                    if cat not in categories:
                        categories[cat] = []
                    categories[cat].append(item)

                lines = ["📋 *Open Items*"]
                for cat, cat_items in categories.items():
                    lines.append(f"\n📂 *{cat}* ({len(cat_items)})")
                    for item in cat_items:
                        name = item.get("name", "No name")
                        action = item.get("next_action", "No action")
                        status = item.get("status", "open")
                        status_emoji = "🔄" if status == "in-progress" else "📌"
                        lines.append(f"{status_emoji} {name}")
                        if action and action != "No action":
                            lines.append(f"   → {action}")

                send_telegram_message(chat_id, "\n".join(lines))
            else:
                send_telegram_message(chat_id, "📝 No open items found.")
            return {"statusCode": 200, "body": "Open command processed"}

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
            reply = f"⚠️ Low confidence ({result['confidence']}%) - not saved. Please rephrase `{snippet}`."
            send_telegram_message(chat_id, reply)

        return {"statusCode": 200, "body": "Message processed successfully"}

    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }
