"""Process action - classify and save a message using AI."""

import logging
import json
from typing import Any, Dict, Mapping
from common.environments import get_env
from lambdas.app import app

# Import the event model
from lambdas.telegram.telegram_messages import TelegramWebhookEvent

logger = logging.getLogger(__name__)
ANTHROPIC_API_KEY = get_env("ANTHROPIC_API_KEY", required=False)
OPENAI_API_KEY = get_env("OPENAI_API_KEY", required=False)
BEDROCK_REGION = get_env("BEDROCK_REGION", required=False)
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


def _classify(message: str) -> Dict[str, Any]:
    """Process and classify a message."""
    try:
        content = (
            app()
            .get_ai_model_api()
            .invoke_model(prompt=CLASSIFICATION_PROMPT.format(message=message))
        )
    except Exception as e:
        raise Exception("AI classification attempt(s) failed") from e

    if content.startswith("```json"):
        content = content[7:-3].strip()
    else:
        logger.error(f"AI classification failed - invalid response format: {content}")
        raise Exception("AI classification failed - invalid response format")

    result = json.loads(content)
    result["original_text"] = message

    confidence = result.get("confidence", 0)
    if not isinstance(confidence, int):
        try:
            confidence = int(float(confidence))
        except (ValueError, TypeError):
            confidence = 0

    result["confidence"] = min(100, max(0, confidence))

    return result


def handle(event_model: TelegramWebhookEvent) -> Mapping[str, Any]:
    """Process and classify a message, then save using embedding matching."""
    from lambdas.telegram.telegram_messages import send_telegram_message
    from lambdas.embedding_matcher import save_to_dynamodb_with_embedding

    # Extract data from event model
    message = event_model.message
    if not message or not message.text:
        return {"statusCode": 400, "body": "No message text"}

    text = message.text
    chat_id = str(message.chat.id)
    result = _classify(text)

    if result["confidence"] >= 60:
        save_result = save_to_dynamodb_with_embedding(result)

        if save_result["action"] == "updated":
            reply = f"🔄 Updated existing *{save_result['category']}* item (similarity: {save_result['similarity']:.0%})"
        else:
            reply = f"✅ Saved as *{save_result['category']}* (confidence: {result['confidence']}%)"

        if result.get("name"):
            reply += f"\n📝 *{result['name']}*"

        send_telegram_message(chat_id, reply)
        logging.info(f"Successfully processed and saved message: {save_result}")
    else:
        snippet = text[:50]
        reply = f"⚠️ Low confidence ({result['confidence']}%) - not saved. Please rephrase `{snippet}`."
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
