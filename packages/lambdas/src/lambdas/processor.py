import json
import uuid
from json import JSONDecodeError
from typing import Optional, Callable, Mapping, Any

from common.logging import get_logger
from common.timestamps import format_iso8601_zulu

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
from lambdas.events import MessageReceived
from lambdas.telegram.telegram_messages import TelegramWebhookEvent
from lambdas.app import app

TELEGRAM_SECRET_TOKEN = get_env("TELEGRAM_SECRET_TOKEN", required=False)
"""Use this to verify that the webhook is coming from Telegram."""

logger = get_logger(__name__)

COMMAND_DISPATCH: list[tuple[Optional[str], Callable[..., Mapping[str, Any]]]] = [
    ("/digest", digest.handle),
    ("/open", open_items.handle),
    ("/closed", closed_items.handle),
    ("/debug count", debug_count.handle),
    ("/debug backfill", debug_backfill.handle),
    ("/debug duplicates-auto", debug_duplicates_auto.handle),
    ("/debug duplicates", debug_duplicates.handle),
    ("/merge", merge.handle),
    ("/delete", delete.handle),
    (None, process_action.handle),
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
        logger.warning(
            "Invalid webhook request data",
            extra={"error": str(e), "message_id": message_id},
            exc_info=True,
        )
        response = {
            "statusCode": 400,
            "body": json.dumps({"error": "Invalid request format"}),
        }
    except Exception as e:
        # Unexpected errors - log and return 500
        logger.error(
            "Error processing webhook",
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
        webhook_data["message"] = webhook_data.get("message", {})
        webhook_data["message"]["message_id"] = message_id
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

    # Save message to event store (inbox log)
    now_iso = format_iso8601_zulu()
    message_event = MessageReceived(
        event_type="MessageReceived",
        timestamp=now_iso,
        raw_text=text,
        source="telegram",
        source_id=str(message_unique_id),
        chat_id=chat_id,
        received_at=now_iso,
    )
    app().get_event_repository().append_event(message_event)

    # Pass the message received event to actions
    for prefix, action in COMMAND_DISPATCH:
        if prefix is None or text.startswith(prefix):
            return action(message_received_event=message_event)

    return None
