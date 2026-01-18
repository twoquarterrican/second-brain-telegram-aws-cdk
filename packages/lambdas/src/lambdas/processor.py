import json
import logging

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

logger = logging.getLogger()
logger.setLevel(logging.INFO)


TELEGRAM_SECRET_TOKEN = get_env("TELEGRAM_SECRET_TOKEN", required=False)
# Export bot token for telegram_messages module
TELEGRAM_BOT_TOKEN = TELEGRAM_SECRET_TOKEN

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
    logger.info("Received event", extra={"message_id": message_id, "event": event})

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
            "Processing message",
            extra={
                "message_id": message_id,
                "telegram_message_id": message_unique_id,
                "text_preview": text[:50],
                "chat_id": chat_id,
            },
        )

        for prefix, action in COMMAND_DISPATCH:
            if prefix is None or text.startswith(prefix):
                return action(
                    text=text,
                    chat_id=chat_id,
                )

    except Exception as e:
        logger.error(
            "Error processing webhook",
            extra={"error": str(e), "message_id": message_id},
            exc_info=True,
        )
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Message processed successfully"}),
    }
