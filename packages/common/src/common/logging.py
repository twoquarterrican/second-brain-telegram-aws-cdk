#!/usr/bin/env python3
"""
Logging utility with Telegram notification for critical errors.

Usage:
    from common.logging import log_error, log_warning

Functions:
    log_error(message, cause=None) - Log error and notify via Telegram
    log_warning(message) - Log warning and notify via Telegram
"""

from typing import Optional

import logging
import os

import requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("USER_CHAT_ID")


def _send_telegram(message: str):
    """Send message to Telegram if configured."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        response = requests.post(
            url,
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message},
            timeout=10,
        )
        return response.status_code == 200
    except Exception:
        return False


def log_error(message: str, cause: Optional[str] = None):
    """Log error to CloudWatch and notify via Telegram.

    Args:
        message: Human-readable error message
        cause: Optional exception message or underlying cause
    """
    full_message = f"❌ {message}"
    if cause:
        full_message += f"\n\nCause: {cause}"

    logger.error(full_message)
    _send_telegram(full_message)


def log_warning(message: str):
    """Log warning to CloudWatch and notify via Telegram.

    Args:
        message: Human-readable warning message
    """
    full_message = f"⚠️ {message}"

    logger.warning(full_message)
    _send_telegram(full_message)
