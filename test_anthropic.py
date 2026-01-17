#!/usr/bin/env python3
"""
Unit test to verify anthropic import works with pinned version
"""

import os
import sys


def test_anthropic_import():
    """Test importing anthropic with pinned version"""
    print("🧪 Testing anthropic import...")

    try:
        import anthropic

        print(f"✅ Successfully imported anthropic version: {anthropic.__version__}")

        # Test basic functionality
        client = anthropic.Anthropic(api_key="test_key")
        print(f"✅ Successfully created Anthropic client")

        return True
    except ImportError as e:
        print(f"❌ Failed to import anthropic: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error importing anthropic: {e}")
        return False


def test_environment():
    """Test environment variables"""
    print(f"🌍 Environment variables:")
    print(f"  ANTHROPIC_API_KEY: {os.getenv('ANTHROPIC_API_KEY', 'None')}")
    print(f"  OPENAI_API_KEY: {os.getenv('OPENAI_API_KEY', 'None')}")
    print(f"  BEDROCK_REGION: {os.getenv('BEDROCK_REGION', 'None')}")
    print(
        f"  TELEGRAM_BOT_TOKEN: {'Set' if os.getenv('TELEGRAM_BOT_TOKEN') else 'None'}"
    )
    print(
        f"  TELEGRAM_SECRET_TOKEN: {'Set' if os.getenv('TELEGRAM_SECRET_TOKEN') else 'None'}"
    )


if __name__ == "__main__":
    print("🧪 Running anthropic import test...")
    success = test_anthropic_import()

    print("\n📊 Environment test:")
    test_environment()

    if success:
        print("\n✅ Test PASSED - anthropic import works!")
        sys.exit(0)
    else:
        print("\n❌ Test FAILED - anthropic import issue detected!")
        sys.exit(1)
