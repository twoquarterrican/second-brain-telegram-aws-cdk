#!/usr/bin/env python3
"""
Script to set up Telegram webhook for the Second Brain processor Lambda.
"""

import os
import sys
import requests
import argparse


def get_function_url(function_name: str, region: str = "us-east-1") -> str:
    """Get the Function URL for a Lambda function using AWS CLI"""
    import subprocess

    try:
        result = subprocess.run(
            [
                "aws",
                "lambda",
                "get-function-url-config",
                "--function-name",
                function_name,
                "--region",
                region,
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        import json

        config = json.loads(result.stdout)
        return config["FunctionUrl"]
    except subprocess.CalledProcessError as e:
        print(f"Error getting function URL: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing function URL response: {e}")
        return None


def set_webhook(bot_token: str, webhook_url: str, secret_token: str = None) -> bool:
    """Set the Telegram webhook"""
    url = f"https://api.telegram.org/bot{bot_token}/setWebhook"

    payload = {"url": webhook_url}
    if secret_token:
        payload["secret_token"] = secret_token

    try:
        response = requests.post(url, json=payload, timeout=30)
        result = response.json()

        if result.get("ok"):
            print(f"✅ Webhook set successfully!")
            print(f"   URL: {webhook_url}")
            if secret_token:
                print(f"   Secret token configured")
            return True
        else:
            print(
                f"❌ Failed to set webhook: {result.get('description', 'Unknown error')}"
            )
            return False

    except Exception as e:
        print(f"❌ Error setting webhook: {e}")
        return False


def get_webhook_info(bot_token: str) -> bool:
    """Get current webhook information"""
    url = f"https://api.telegram.org/bot{bot_token}/getWebhookInfo"

    try:
        response = requests.get(url, timeout=30)
        result = response.json()

        if result.get("ok"):
            info = result["result"]
            print("📋 Current webhook info:")
            print(f"   URL: {info.get('url', 'Not set')}")
            print(f"   Custom certificate: {info.get('has_custom_certificate', False)}")
            print(f"   Pending update count: {info.get('pending_update_count', 0)}")
            print(f"   Last error: {info.get('last_error_message', 'None')}")
            return True
        else:
            print(
                f"❌ Failed to get webhook info: {result.get('description', 'Unknown error')}"
            )
            return False

    except Exception as e:
        print(f"❌ Error getting webhook info: {e}")
        return False


def delete_webhook(bot_token: str) -> bool:
    """Delete the Telegram webhook"""
    url = f"https://api.telegram.org/bot{bot_token}/deleteWebhook"

    try:
        response = requests.post(url, timeout=30)
        result = response.json()

        if result.get("ok"):
            print("✅ Webhook deleted successfully!")
            return True
        else:
            print(
                f"❌ Failed to delete webhook: {result.get('description', 'Unknown error')}"
            )
            return False

    except Exception as e:
        print(f"❌ Error deleting webhook: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Manage Telegram webhook for Second Brain"
    )
    parser.add_argument("--token", required=True, help="Telegram bot token")
    parser.add_argument(
        "--function-name", default="SecondBrainProcessor", help="Lambda function name"
    )
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--secret-token", help="Secret token for webhook verification")
    parser.add_argument(
        "--webhook-url", help="Custom webhook URL (auto-detected if not provided)"
    )
    parser.add_argument("--delete", action="store_true", help="Delete the webhook")
    parser.add_argument("--info", action="store_true", help="Show current webhook info")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation for dangerous operations",
    )

    args = parser.parse_args()

    # Handle info command
    if args.info:
        return get_webhook_info(args.token)

    # Handle delete command
    if args.delete:
        if not args.force:
            confirm = input("Are you sure you want to delete the webhook? (y/N): ")
            if confirm.lower() != "y":
                print("Cancelled.")
                return False
        return delete_webhook(args.token)

    # Set webhook
    webhook_url = args.webhook_url
    if not webhook_url:
        print("🔍 Getting function URL from AWS...")
        webhook_url = get_function_url(args.function_name, args.region)
        if not webhook_url:
            print(
                "❌ Could not get function URL. Please provide --webhook-url or check AWS CLI configuration."
            )
            return False

    print(f"🔧 Setting webhook to: {webhook_url}")
    return set_webhook(args.token, webhook_url, args.secret_token)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
