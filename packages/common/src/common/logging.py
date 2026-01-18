#!/usr/bin/env python3
"""
Structured logging utility with Telegram notification for critical errors.

Usage:
    from common.logging import setup_logging, get_logger, log_error, log_warning, log_info

Setup:
    setup_logging()  # Configure structured JSON logging

Logging:
    logger = get_logger(__name__)
    log_error("Database connection failed", cause="Timeout", user_id=123)
    log_warning("High memory usage", memory_mb=850, threshold_mb=800)
    log_info("User logged in", user_id=456, ip_address="192.168.1.1")

Functions:
    setup_logging(level="INFO", format_type="json") - Configure structured logging
    get_logger(name) - Get a structured logger instance
    log_error(message, cause=None, **extra) - Log error with structured data & Telegram
    log_warning(message, **extra) - Log warning with structured data & Telegram
    log_info(message, **extra) - Log info with structured data
"""

import logging
import os
import sys
from typing import Any, Optional

import requests

import pythonjsonlogger.json

# Service identification
SERVICE_NAME = "second-brain"
SERVICE_VERSION = "1.0.0"

# Telegram configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("USER_CHAT_ID")

# Global logger instance
logger = logging.getLogger(SERVICE_NAME)


def setup_logging(level: str = "INFO", format_type: str = "json"):
    """
    Configure structured logging.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: Log format - 'json' for structured logging, 'text' for human-readable
    """
    # Set log level
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create formatter based on type
    if format_type == "json":
        formatter = pythonjsonlogger.json.JsonFormatter(
            fmt="%(asctime)s %(name)s %(levelname)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%S%z"
        )
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )

    # Console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(f"{SERVICE_NAME}.{name}")


# Export public API
__all__ = [
    "setup_logging",
    "get_logger",
    "log_error",
    "log_warning_to_user",
    "log_info",
]


def _send_telegram(message: str, level: str = "INFO"):
    """Send message to Telegram if configured."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    # Format message for Telegram
    emoji = "❌" if level == "ERROR" else "⚠️" if level == "WARNING" else "ℹ️"
    telegram_message = f"{emoji} {SERVICE_NAME}: {message}"

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        response = requests.post(
            url,
            json={"chat_id": TELEGRAM_CHAT_ID, "text": telegram_message},
            timeout=10,
        )
        return response.status_code == 200
    except RequestException:
        log.error("Failed to send Telegram notification", exc_info=True)
        return False


def log_error(message: str, cause: Optional[str] = None, **extra: Any):
    """Log error with structured data and notify via Telegram.

    Args:
        message: Human-readable error message
        cause: Optional exception message or underlying cause
        **extra: Additional structured data to include in log
    """
    # Build structured log data
    log_data = {
        "level": "ERROR",
    }

    if cause:
        log_data["cause"] = cause

    # Add extra fields
    log_data.update(extra)

    # Log with structured data
    logger.error(message, extra=log_data)

    # Send Telegram notification
    telegram_message = message
    if cause:
        telegram_message += f" - Cause: {cause}"
    _send_telegram(telegram_message, "ERROR")


def log_warning_to_user(message: str, exc_info: bool = False, **extra: Any):
    """Log warning with structured data and notify via Telegram.

    Args:
        message: Human-readable warning message
        exc_info: If True, include exception info in log
        **extra: Additional structured data to include in log
    """
    # Build structured log data
    log_data = {
        "level": "WARNING",
    }

    # Add extra fields
    log_data.update(extra)

    if exc_info:
        log_data["traceback"] = traceback.format_exc()

    # Log with structured data
    logger.warning(message, extra=log_data)

    # Send Telegram notification
    _send_telegram(message, "WARNING")


def log_info(message: str, **extra: Any):
    """Log info with structured data.

    Args:
        message: Human-readable info message
        **extra: Additional structured data to include in log
    """
    # Build structured log data
    log_data = {
        "level": "INFO",
    }

    # Add extra fields
    log_data.update(extra)

    # Log with structured data
    logger.info(message, extra=log_data)
