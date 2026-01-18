"""Process action - classify and save a message using AI."""

import logging
import json
from typing import Any, Mapping, Optional
from common.logging import log_warning_to_user
from lambdas.app import app
from lambdas.events import MessageClassified, MessageReceived
from lambdas.exceptions import MessageClassificationFailedException

# Import the event model
from lambdas.telegram.telegram_messages import TelegramWebhookEvent

logger = logging.getLogger(__name__)
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


def _classify(message: str, source_message: MessageReceived) -> MessageClassified:
    """Classify a message using AI and save classification event."""
    try:
        response = (
            app()
            .get_ai_model_api()
            .invoke_model(prompt=CLASSIFICATION_PROMPT.format(message=message))
        )
        content = response.content
    except Exception as e:
        error_msg = "AI classification attempt(s) failed"
        log_warning_to_user(error_msg, exc_info=True)
        raise MessageClassificationFailedException(error_msg) from e

    if content.startswith("```json"):
        content = content[7:-3].strip()
    else:
        error_msg = f"AI classification failed - invalid response format: {content}"
        log_warning_to_user(error_msg)
        raise MessageClassificationFailedException(error_msg)

    try:
        result = json.loads(content)
    except json.JSONDecodeError as e:
        error_msg = f"AI returned invalid JSON: {content}"
        log_warning_to_user(error_msg, exc_info=True)
        raise MessageClassificationFailedException(error_msg) from e

    # Extract classification result
    category = result.get("category", "")
    confidence_pct = result.get("confidence", 0)
    if not isinstance(confidence_pct, int):
        try:
            confidence_pct = int(float(confidence_pct))
        except (ValueError, TypeError):
            confidence_pct = 0
    confidence_pct = min(100, max(0, confidence_pct))

    # Create and save classification event
    classified_event = MessageClassified.create_from_classification(
        raw_text=message,
        category=category,
        confidence_pct=confidence_pct,
        classified_by=response.model_name,
        source_message=source_message,
    )

    app().get_event_repository().append_event(classified_event)

    return classified_event


def handle(
    event_model: TelegramWebhookEvent,
    message_received_event: Optional[MessageReceived] = None,
) -> Mapping[str, Any]:
    """Process and classify a message, then save using embedding matching."""
    from lambdas.telegram.telegram_messages import send_telegram_message
    from lambdas.embedding_matcher import save_to_dynamodb_with_embedding

    # Extract data from event model
    message = event_model.message
    if not message or not message.text:
        return {"statusCode": 400, "body": "No message text"}

    text = message.text
    chat_id = str(message.chat.id)

    if message_received_event is None:
        return {
            "statusCode": 500,
            "body": "Internal error: message_received_event not provided",
        }

    try:
        classified_event = _classify(text, message_received_event)
    except MessageClassificationFailedException:
        # Log warning already sent to user via log_warning_to_user
        # Don't retry - return 200 so Telegram doesn't keep resending
        return {"statusCode": 200, "body": "Classification failed, user notified"}

    # Extract classification data from event
    confidence_pct = int(classified_event.confidence_score * 100)

    if confidence_pct >= 60:
        # Convert event to dict format for save_to_dynamodb_with_embedding
        classification_result = {
            "category": classified_event.classification,
            "confidence": confidence_pct,
            "original_text": classified_event.raw_text,
            "name": None,  # TODO: Extract from event if needed
            "status": None,
            "next_action": None,
            "notes": None,
        }

        save_result = save_to_dynamodb_with_embedding(classification_result)

        if save_result["action"] == "updated":
            reply = f"🔄 Updated existing *{save_result['category']}* item (similarity: {save_result['similarity']:.0%})"
        else:
            reply = f"✅ Saved as *{save_result['category']}* (confidence: {confidence_pct}%)"

        send_telegram_message(chat_id, reply)
        logging.info(f"Successfully processed and saved message: {save_result}")
    else:
        snippet = text[:50]
        reply = f"⚠️ Low confidence ({confidence_pct}%) - not saved. Please rephrase `{snippet}`."
        send_telegram_message(chat_id, reply)

    return {"statusCode": 200, "body": "Message processed successfully"}


def process(event_model: TelegramWebhookEvent, **kwargs) -> Mapping[str, Any]:
    """Main process action handler - dispatches to handle with dependencies."""
    return handle(event_model, **kwargs)


# Export the process function so it can be called directly
__all__ = [
    "process",
    "handle",
    "_classify",
]
