"""Process action - classify and save a message using AI."""

import logging
import json
from anthropic.types import MessageParam
from typing import Any, Dict, Optional
from common.environments import get_env


logger = logging.getLogger(__name__)
ANTHROPIC_API_KEY = get_env("ANTHROPIC_API_KEY", required=False)
OPENAI_API_KEY = get_env("OPENAI_API_KEY", required=False)
BEDROCK_REGION = get_env("BEDROCK_REGION", required=True)
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
        from botocore.config import Config

        bedrock_config = {
            "region_name": BEDROCK_REGION,
            "config": Config(read_timeout=60, retries={"max_attempts": 3}),
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


def handle(
    text: str,
    send_telegram_message,
    chat_id: str,
    save_to_dynamodb_with_embedding,
    **_kwargs,
):
    """Process and classify a message, then save using embedding matching."""
    result = process_message(text)

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


def process(event_model, **kwargs):
    """Main process action handler - dispatches to handle with dependencies."""
    from lambdas.telegram.telegram_messages import send_telegram_message
    from lambdas.embedding_matcher import save_to_dynamodb_with_embedding

    # Extract data from the event model
    message = event_model.message
    if not message or not message.text:
        return {"statusCode": 400, "body": "No message text"}

    text = message.text
    chat_id = str(message.chat.id)

    return handle(
        text=text,
        send_telegram_message=send_telegram_message,
        chat_id=chat_id,
        save_to_dynamodb_with_embedding=save_to_dynamodb_with_embedding,
        **kwargs,
    )


# Export the process function so it can be called directly
__all__ = [
    "process",
    "handle",
    "classify_with_anthropic",
    "classify_with_openai",
    "classify_with_bedrock",
    "process_message",
]
