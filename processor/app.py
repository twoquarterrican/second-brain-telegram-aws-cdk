import json
import os
import logging
import hashlib
import hmac
import boto3
import requests
from datetime import datetime
from typing import Dict, Any, Optional

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
TELEGRAM_SECRET_TOKEN = os.getenv("TELEGRAM_SECRET_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

AI_CLASSIFICATION_PROMPT = """
You are a classification AI for a personal second brain system. Analyze the following message and classify it into one of these categories:
- People: Information about people, relationships, contacts
- Projects: Work projects, personal projects, tasks with goals
- Ideas: Brainstorming, creative thoughts, concepts
- Admin: Administrative tasks, scheduling, logistics

Extract the following fields if present:
- name: A brief title/name for this item
- status: Current state (e.g., open, in_progress, completed, waiting)
- next_action: Next step to take
- notes: Additional details or context

Return ONLY a JSON object with this structure:
{
    "category": "People|Projects|Ideas|Admin",
    "name": "Brief title",
    "status": "status",
    "next_action": "next action",
    "notes": "additional notes",
    "confidence": 0-100
}

Message to classify: {message}
"""


def verify_webhook(request_body: bytes, signature: str) -> bool:
    """Verify Telegram webhook signature"""
    if not TELEGRAM_SECRET_TOKEN:
        return True

    secret = TELEGRAM_SECRET_TOKEN.encode()
    expected = hmac.new(secret, request_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def classify_with_ai(message: str) -> Optional[Dict[str, Any]]:
    """Classify message using AI (Claude first, fallback to OpenAI)"""

    # Try Claude first
    if ANTHROPIC_API_KEY and Anthropic:
        try:
            client = Anthropic(api_key=ANTHROPIC_API_KEY)
            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1000,
                messages=[
                    {
                        "role": "user",
                        "content": AI_CLASSIFICATION_PROMPT.format(message=message),
                    }
                ],
            )

            content = response.content[0].text.strip()
            if content.startswith("```json"):
                content = content[7:-3]

            result = json.loads(content)
            return result

        except Exception as e:
            logger.warning(f"Claude classification failed: {e}")

    # Fallback to OpenAI
    if OPENAI_API_KEY and OpenAI:
        try:
            client = OpenAI(api_key=OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "user",
                        "content": AI_CLASSIFICATION_PROMPT.format(message=message),
                    }
                ],
                temperature=0.1,
            )

            content = response.choices[0].message.content.strip()
            if content.startswith("```json"):
                content = content[7:-3]

            result = json.loads(content)
            return result

        except Exception as e:
            logger.error(f"OpenAI classification failed: {e}")

    logger.error("All AI classification methods failed")
    return None


def send_telegram_message(chat_id: str, text: str) -> bool:
    """Send message via Telegram bot API"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False


def store_brain_item(
    classification: Dict[str, Any], original_message: str, chat_id: str
) -> bool:
    """Store classified item in DynamoDB"""
    try:
        timestamp = datetime.utcnow().isoformat()
        uuid_str = timestamp.replace("-", "").replace(":", "").replace(".", "")

        item = {
            "PK": f"CATEGORY#{classification['category']}",
            "SK": f"{timestamp}#{uuid_str}",
            "category": classification["category"],
            "name": classification.get("name", "Untitled"),
            "status": classification.get("status", "open"),
            "next_action": classification.get("next_action", ""),
            "notes": classification.get("notes", ""),
            "original_text": original_message,
            "confidence": classification.get("confidence", 0),
            "chat_id": chat_id,
            "created_at": timestamp,
            "updated_at": timestamp,
        }

        response = table.put_item(Item=item)
        logger.info(
            f"Stored item: {classification['category']} - {classification.get('name', 'Untitled')}"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to store item: {e}")
        return False


def lambda_handler(event, context):
    """Main Lambda handler for Telegram webhook"""

    # Verify webhook signature
    signature = event.get("headers", {}).get("x-telegram-bot-api-secret-token", "")
    if not verify_webhook(event.get("body", "").encode(), signature):
        logger.error("Webhook verification failed")
        return {"statusCode": 403, "body": "Forbidden"}

    try:
        # Parse Telegram update
        body = json.loads(event["body"])
        logger.info(f"Received update: {json.dumps(body)}")

        # Extract message
        if "message" not in body:
            return {"statusCode": 200, "body": "No message to process"}

        message = body["message"]
        chat_id = str(message["chat"]["id"])

        # Handle different message types
        if "text" in message:
            text = message["text"].strip()
            if not text:
                return {"statusCode": 200, "body": "Empty message"}
        elif "voice" in message:
            # TODO: Implement voice transcription
            text = "Voice message - transcription not implemented yet"
        else:
            return {"statusCode": 200, "body": "Unsupported message type"}

        # Classify with AI
        classification = classify_with_ai(text)
        if not classification:
            send_telegram_message(
                chat_id, "❌ Sorry, I couldn't classify your message. Please try again."
            )
            return {"statusCode": 500, "body": "Classification failed"}

        # Check confidence threshold
        confidence = classification.get("confidence", 0)
        if confidence < 60:
            send_telegram_message(
                chat_id,
                f"❓ Low confidence ({confidence}%) - Please rephrase your message.",
            )
            return {"statusCode": 200, "body": "Low confidence"}

        # Store in database
        if store_brain_item(classification, text, chat_id):
            response_text = f"✅ Saved to *{classification['category']}*\n\n"
            response_text += f"📝 {classification.get('name', 'Untitled')}\n"
            response_text += f"📊 Status: {classification.get('status', 'open')}\n"

            if classification.get("next_action"):
                response_text += f"➡️ Next: {classification['next_action']}\n"

            send_telegram_message(chat_id, response_text)
            return {"statusCode": 200, "body": "Success"}
        else:
            send_telegram_message(
                chat_id, "❌ Failed to save to database. Please try again."
            )
            return {"statusCode": 500, "body": "Storage failed"}

    except json.JSONDecodeError:
        logger.error("Invalid JSON in request body")
        return {"statusCode": 400, "body": "Invalid JSON"}
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"statusCode": 500, "body": "Internal server error"}
