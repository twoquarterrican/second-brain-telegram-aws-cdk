"""Digest action - generate daily/weekly digest."""

from lambdas.digest import generate_digest_summary


def handle(text: str, send_telegram_message, chat_id: str, **kwargs):
    """Generate and send digest."""
    digest_type = "daily" if "daily" in text.lower() else "weekly"
    summary = generate_digest_summary(digest_type)
    if summary:
        send_telegram_message(chat_id, summary)
    else:
        send_telegram_message(chat_id, "❌ Failed to generate digest")
    return {"statusCode": 200, "body": f"{digest_type} digest command processed"}
