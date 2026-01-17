"""Process action - classify and save a message using AI."""

import logging


def handle(
    text: str,
    send_telegram_message,
    chat_id: str,
    process_message,
    save_to_dynamodb_with_embedding,
    **kwargs,
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
