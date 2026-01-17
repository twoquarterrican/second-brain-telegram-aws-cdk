import os
import json
import logging
import boto3
from typing import Dict, Any, Optional
import requests
from anthropic.types import MessageParam

from lambdas.actions import (
    digest,
    open_items,
    closed_items,
    debug_count,
    debug_backfill,
    debug_duplicates_auto,
    debug_duplicates,
    merge,
    delete,
    process as process_action,
)
from lambdas.embedding_matcher import save_to_dynamodb_with_embedding


logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("SecondBrain")


def _get_env(key: str, default: str = "") -> str | None:
    value = os.getenv(key, default).strip()
    if value in ["", "-"] or value is None:
        return None
    return value


ANTHROPIC_API_KEY = _get_env("ANTHROPIC_API_KEY")
OPENAI_API_KEY = _get_env("OPENAI_API_KEY")
BEDROCK_REGION = _get_env("BEDROCK_REGION", "us-east-1")
TELEGRAM_BOT_TOKEN = _get_env("TELEGRAM_BOT_TOKEN")
TELEGRAM_SECRET_TOKEN = _get_env("TELEGRAM_SECRET_TOKEN")
USER_CHAT_ID = _get_env("USER_CHAT_ID")


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

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[
                MessageParam(
                    role="user",
                    content=CLASSIFICATION_PROMPT.format(message=message),
                ),
            ],
        )

        content = response.content[0].text.strip()
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
        import botocore

        bedrock_config = {
            "region_name": BEDROCK_REGION,
            "config": botocore.Config(read_timeout=60, retries={"max_attempts": 3}),
        }
        bedrock = boto3.client("bedrock-runtime", **bedrock_config)

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


def process_message(message: str) -> Dict[str, Any]:
    """Process and classify a message."""
    result = None
    if ANTHROPIC_API_KEY:
        result = classify_with_anthropic(message)
    if not result and OPENAI_API_KEY:
        result = classify_with_openai(message)
    if not result and BEDROCK_REGION:
        result = classify_with_bedrock(message)

    if not result:
        raise Exception("All AI classification attempts failed")

    result["original_text"] = message

    confidence = result.get("confidence", 0)
    if not isinstance(confidence, int):
        try:
            confidence = int(float(confidence))
        except (ValueError, TypeError):
            confidence = 0

    result["confidence"] = min(100, max(0, confidence))

    return result


COMMAND_DISPATCH = [
    ("/digest", digest),
    ("/open", open_items),
    ("/closed", closed_items),
    ("/debug count", debug_count),
    ("/debug backfill", debug_backfill),
    ("/debug duplicates-auto", debug_duplicates_auto),
    ("/debug duplicates", debug_duplicates),
    ("/merge", merge),
    ("/delete", delete),
    (None, process_action),
]


def handler(event, _context):
    """Main Lambda handler for Telegram webhook."""
    import uuid

    message_id = str(uuid.uuid4())[:8]
    logger.info(f"[{message_id}] Received event: {json.dumps(event)}")

    headers = event.get("headers", {})
    received_secret = headers.get("x-telegram-bot-api-secret-token")
    expected_secret = TELEGRAM_SECRET_TOKEN

    if expected_secret and received_secret != expected_secret:
        logger.error("Invalid webhook secret")
        return {"statusCode": 403, "body": "Forbidden"}

    try:
        if isinstance(event.get("body"), str):
            webhook_data = json.loads(event["body"])
        else:
            webhook_data = event["body"]

        message = webhook_data.get("message", {})
        text = message.get("text", "")
        chat_id = str(message.get("chat", {}).get("id", ""))
        message_unique_id = message.get("message_id", "")

        if not text:
            logger.warning("No text in message")
            return {"statusCode": 200, "body": "No text to process"}

        logger.info(
            f"[{message_id}] Processing message {message_unique_id}: {text[:50]}..."
        )

        for prefix, action in COMMAND_DISPATCH:
            if prefix is None or text.startswith(prefix):
                return action(
                    text=text,
                    send_telegram_message=send_telegram_message,
                    chat_id=chat_id,
                    table=table,
                    ANTHROPIC_API_KEY=ANTHROPIC_API_KEY,
                    process_message=process_message,
                    save_to_dynamodb_with_embedding=save_to_dynamodb_with_embedding,
                )

    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Message processed successfully"}),
    }
