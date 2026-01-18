import json
import uuid
from json import JSONDecodeError
from typing import Optional

from pydantic import BaseModel, Field
from common.logging import get_logger
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
from common.environments import get_env


# Pydantic models for Telegram webhook events
class TelegramChat(BaseModel):
    """Telegram chat information."""

    id: int = Field(..., description="Unique chat identifier")


class TelegramMessage(BaseModel):
    """Telegram message structure."""

    message_id: int = Field(..., description="Unique message identifier")
    text: Optional[str] = Field(None, description="Message text content")
    chat: TelegramChat = Field(..., description="Chat information")


class TelegramWebhookEvent(BaseModel):
    """Telegram webhook event structure."""

    message: Optional[TelegramMessage] = Field(None, description="Message data")


TELEGRAM_SECRET_TOKEN = get_env("TELEGRAM_SECRET_TOKEN", required=False)
# Export bot token for telegram_messages module
TELEGRAM_BOT_TOKEN = TELEGRAM_SECRET_TOKEN

logger = get_logger(__name__)

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
    message_id = str(uuid.uuid4())[:8]
    logger.info("Received event", extra={"message_id": message_id, "event": event})

    headers = event.get("headers", {})
    received_secret = headers.get("x-telegram-bot-api-secret-token")
    expected_secret = TELEGRAM_SECRET_TOKEN

    if expected_secret and received_secret != expected_secret:
        logger.error("Invalid webhook secret")
        return {"statusCode": 403, "body": "Forbidden"}

    try:
        response = _handle_authorized_event(event, message_id)
    except (ValueError, KeyError, TypeError, JSONDecodeError) as e:
        # Expected parsing/validation errors
        log_warning_to_user(
            "Error parsing webhook data",
            extra={"error": str(e), "message_id": message_id},
            exc_info=True,
        )
        response = {
            "statusCode": 400,
            "body": json.dumps({"error": "Invalid request format"}),
        }
    except Exception as e:
        # Unexpected errors - log and return 500
        log_warning_to_user(
            "Unexpected error processing webhook",
            extra={"error": str(e), "message_id": message_id},
            exc_info=True,
        )
        response = {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }

    return response or {
        "statusCode": 200,
        "body": json.dumps({"message": "Message ignored"}),
    }


def _handle_authorized_event(event, message_id):
    # Parse the webhook event into our pydantic model
    if isinstance(event.get("body"), str):
        webhook_data = json.loads(event["body"])
    else:
        webhook_data = event["body"]

    try:
        telegram_event = TelegramWebhookEvent(**webhook_data)
    except Exception as e:
        logger.error(
            "Failed to parse webhook event",
            extra={
                "error": str(e),
                "message_id": message_id,
                "webhook_data": webhook_data,
            },
            exc_info=True,
        )
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Invalid webhook event format"}),
        }

    # Extract message data
    message = telegram_event.message
    if not message or not message.text:
        logger.warning(
            "No text in message",
            extra={"message_id": message_id, "has_message": message is not None},
        )
        return {"statusCode": 200, "body": "No text to process"}

    text = message.text
    chat_id = str(message.chat.id)
    message_unique_id = message.message_id

    logger.info(
        "Processing message",
        extra={
            "message_id": message_id,
            "telegram_message_id": message_unique_id,
            "text_preview": text[:50],
            "chat_id": chat_id,
        },
    )

    # Pass the parsed event model to actions
    for prefix, action in COMMAND_DISPATCH:
        if prefix is None or text.startswith(prefix):
            return action(event_model=telegram_event)

    return None
