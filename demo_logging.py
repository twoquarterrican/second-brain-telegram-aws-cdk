#!/usr/bin/env python3
"""
Demo script for structured logging.
"""

import sys
import os

# Add the packages to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "packages", "common", "src"))

from common.logging import setup_logging, get_logger, log_error, log_warning, log_info


def main():
    print("=== STRUCTURED JSON LOGGING DEMO ===")
    print("This demonstrates the new structured logging system")
    print()

    # Setup structured JSON logging
    setup_logging(level="INFO", format_type="json")
    logger = get_logger("demo")

    # Also show what text format looks like
    print("=== TEXT FORMAT ===")
    setup_logging(level="INFO", format_type="text")
    logger.info("Sample text log", extra={"user_id": 123})
    print()

    print("=== JSON FORMAT ===")
    setup_logging(level="INFO", format_type="json")

    logger = get_logger("demo")

    # Log some structured messages
    logger.info("Application started", extra={"version": "1.0.0", "environment": "dev"})

    log_info("User action completed", user_id=123, action="login", duration_ms=250)

    log_warning("High memory usage detected", memory_mb=850, threshold_mb=800, service="web")

    # Test direct logger with extra
    logger.info("Direct logger call", extra={"custom_field": "test", "number": 42})

    try:
        # Simulate an error
        raise ValueError("Database connection failed")
    except ValueError as e:
        log_error(
            "Failed to connect to database",
            cause=str(e),
            database_host="localhost",
            database_port=5432,
            retry_count=3,
        )

    logger.error(
        "Critical system error",
        extra={"component": "database", "error_code": "DB_CONN_TIMEOUT", "affected_users": 150},
    )


if __name__ == "__main__":
    main()
