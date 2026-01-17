#!/usr/bin/env python3
"""
Specification:
- Let user pick action
- Actions include:
  - Set up webhook
  - Get webhook info
  - Delete webhook
  - Test bot connection
  - Add bot commands
- Environment should be read from common/environments.py, the way we do for other scripts
- Registered in scripts section of pyproject.toml so we can run with uv run...
- Uses click for CLI entry point, InquirerPy for interactive prompts
"""

import os
import sys
from typing import Any, Optional, Tuple

import click
import requests
from InquirerPy import inquirer
from InquirerPy.base.control import Choice

from common.environments import get_stack_output, get_telegram_bot_token


def get_webhook_url_from_stack() -> Optional[str]:
    """Get webhook URL from CDK stack outputs."""
    return get_stack_output("SecondBrainStack", "ProcessorFunctionUrl")


def get_secret_token() -> Optional[str]:
    """Get Telegram secret token from environment."""
    return os.getenv("TELEGRAM_SECRET_TOKEN")


def telegram_api_call(
    bot_token: str, method: str, payload: Optional[dict] = None
) -> Tuple[bool, Any]:
    """Make a Telegram Bot API call."""
    url = f"https://api.telegram.org/bot{bot_token}/{method}"
    try:
        if payload:
            response = requests.post(url, json=payload, timeout=30)
        else:
            response = requests.get(url, timeout=30)
        result = response.json()
        if result.get("ok"):
            return True, result.get("result", result.get("description", "Success"))
        else:
            return False, result.get("description", "Unknown error")
    except requests.RequestException as e:
        return False, str(e)


def set_webhook(
    bot_token: str, webhook_url: str, secret_token: Optional[str] = None
) -> Tuple[bool, str]:
    """Set Telegram webhook."""
    payload = {"url": webhook_url}
    if secret_token:
        payload["secret_token"] = secret_token
    success, result = telegram_api_call(bot_token, "setWebhook", payload)
    if success:
        return True, "Webhook set successfully!"
    return False, result


def get_webhook_info(bot_token: str) -> Tuple[bool, Any]:
    """Get current webhook information."""
    return telegram_api_call(bot_token, "getWebhookInfo")


def delete_webhook(bot_token: str) -> Tuple[bool, str]:
    """Delete Telegram webhook."""
    success, result = telegram_api_call(bot_token, "deleteWebhook", {})
    if success:
        return True, "Webhook deleted successfully!"
    return False, result


def get_bot_info(bot_token: str) -> Tuple[bool, Any]:
    """Get bot information to test connection."""
    return telegram_api_call(bot_token, "getMe")


def set_bot_commands(bot_token: str, commands: list[dict]) -> Tuple[bool, str]:
    """Set bot commands that appear in Telegram's command menu."""
    success, result = telegram_api_call(bot_token, "setMyCommands", {"commands": commands})
    if success:
        return True, "Bot commands set successfully!"
    return False, result


def get_bot_commands(bot_token: str) -> Tuple[bool, Any]:
    """Get current bot commands."""
    return telegram_api_call(bot_token, "getMyCommands")


# Default commands for the Second Brain bot
DEFAULT_BOT_COMMANDS = [
    {"command": "start", "description": "Start the bot and get welcome message"},
    {"command": "help", "description": "Show available commands"},
    {"command": "digest", "description": "Get your daily digest now"},
    {"command": "status", "description": "Check bot and webhook status"},
]


@click.group(invoke_without_command=True)
@click.version_option(version="1.0.0")
@click.pass_context
def cli(ctx: click.Context):
    """Telegram Webhook CLI for Second Brain Setup."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(interactive_cmd)


@cli.command(name="set")
@click.option("--webhook-url", "-w", help="Webhook URL (auto-detected from CDK if not provided)")
@click.option("--secret-token", "-s", help="Secret token (read from env if not provided)")
@click.option("--auto-detect", "-a", is_flag=True, help="Auto-detect URL and proceed without prompts")
def set_cmd(webhook_url: Optional[str], secret_token: Optional[str], auto_detect: bool):
    """Set up Telegram webhook."""
    click.echo("🔧 Setting up Telegram webhook...")

    # Get bot token from environment
    try:
        token = get_telegram_bot_token()
        click.echo(f"📋 Bot token: {token[:15]}...")
    except ValueError as e:
        click.echo(f"❌ {e}", err=True)
        sys.exit(1)

    # Get webhook URL
    if not webhook_url:
        click.echo("🔍 Auto-detecting webhook URL from CDK stack...")
        webhook_url = get_webhook_url_from_stack()
        if not webhook_url:
            click.echo("❌ Could not get webhook URL from CDK stack.", err=True)
            click.echo("💡 Make sure you've deployed: uv run cdkw deploy", err=True)
            if not auto_detect:
                webhook_url = inquirer.text(
                    message="Enter webhook URL manually:",
                    validate=lambda x: x.startswith("https://"),
                    invalid_message="URL must start with https://",
                ).execute()
            else:
                sys.exit(1)
    click.echo(f"📋 Webhook URL: {webhook_url}")

    # Get secret token
    if not secret_token:
        secret_token = get_secret_token()
    if secret_token:
        click.echo("📋 Secret token: configured")
    else:
        click.echo("📋 Secret token: not configured")

    # Confirmation (skip if auto_detect)
    if not auto_detect:
        if not inquirer.confirm(message="Proceed with webhook setup?", default=True).execute():
            click.echo("❌ Cancelled.")
            return

    # Set webhook
    click.echo("⏳ Setting webhook...")
    success, message = set_webhook(token, webhook_url, secret_token)

    if success:
        click.echo(f"✅ {message}")
        click.echo(f"   URL: {webhook_url}")
        click.echo("\n🎉 Your Second Brain bot is ready to receive messages!")
    else:
        click.echo(f"❌ Failed to set webhook: {message}", err=True)
        sys.exit(1)


@cli.command(name="info")
def info_cmd():
    """Get current webhook information."""
    try:
        token = get_telegram_bot_token()
    except ValueError as e:
        click.echo(f"❌ {e}", err=True)
        sys.exit(1)

    click.echo("🔍 Getting webhook information...")
    success, result = get_webhook_info(token)

    if success:
        click.echo("\n📋 Current webhook info:")
        click.echo(f"   URL: {result.get('url') or 'Not set'}")
        click.echo(f"   Has custom certificate: {result.get('has_custom_certificate', False)}")
        click.echo(f"   Pending updates: {result.get('pending_update_count', 0)}")
        if result.get("last_error_date"):
            click.echo(f"   Last error: {result.get('last_error_message', 'Unknown')}")
        else:
            click.echo("   Last error: None")
        click.echo(f"   Max connections: {result.get('max_connections', 'Default')}")
    else:
        click.echo(f"❌ Failed to get webhook info: {result}", err=True)
        sys.exit(1)


@cli.command(name="delete")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
def delete_cmd(force: bool):
    """Delete Telegram webhook."""
    try:
        token = get_telegram_bot_token()
    except ValueError as e:
        click.echo(f"❌ {e}", err=True)
        sys.exit(1)

    if not force:
        if not inquirer.confirm(
            message="Are you sure you want to delete the webhook?", default=False
        ).execute():
            click.echo("❌ Cancelled.")
            return

    click.echo("🗑️  Deleting webhook...")
    success, message = delete_webhook(token)

    if success:
        click.echo(f"✅ {message}")
    else:
        click.echo(f"❌ Failed to delete webhook: {message}", err=True)
        sys.exit(1)


@cli.command(name="test")
def test_cmd():
    """Test bot connection."""
    try:
        token = get_telegram_bot_token()
    except ValueError as e:
        click.echo(f"❌ {e}", err=True)
        sys.exit(1)

    click.echo("🔍 Testing bot connection...")
    success, result = get_bot_info(token)

    if success:
        click.echo(f"✅ Bot is accessible!")
        click.echo(f"   Username: @{result.get('username', 'Unknown')}")
        click.echo(f"   Name: {result.get('first_name', 'Unknown')}")
        click.echo(f"   Bot ID: {result.get('id', 'Unknown')}")
        click.echo(f"   Can join groups: {result.get('can_join_groups', False)}")
        click.echo(f"   Can read group messages: {result.get('can_read_all_group_messages', False)}")
    else:
        click.echo(f"❌ Failed to connect to bot: {result}", err=True)
        sys.exit(1)


@cli.command(name="commands")
@click.option("--set-defaults", "-s", is_flag=True, help="Set default Second Brain commands")
@click.option("--clear", "-c", is_flag=True, help="Clear all bot commands")
def commands_cmd(set_defaults: bool, clear: bool):
    """Add or view bot commands."""
    try:
        token = get_telegram_bot_token()
    except ValueError as e:
        click.echo(f"❌ {e}", err=True)
        sys.exit(1)

    if clear:
        click.echo("🗑️  Clearing bot commands...")
        success, message = set_bot_commands(token, [])
        if success:
            click.echo("✅ Bot commands cleared!")
        else:
            click.echo(f"❌ Failed to clear commands: {message}", err=True)
            sys.exit(1)
        return

    if set_defaults:
        click.echo("🔧 Setting default bot commands...")
        click.echo("\n📋 Commands to set:")
        for cmd in DEFAULT_BOT_COMMANDS:
            click.echo(f"   /{cmd['command']} - {cmd['description']}")

        success, message = set_bot_commands(token, DEFAULT_BOT_COMMANDS)
        if success:
            click.echo(f"\n✅ {message}")
        else:
            click.echo(f"❌ Failed to set commands: {message}", err=True)
            sys.exit(1)
        return

    # Default: show current commands
    click.echo("🔍 Getting current bot commands...")
    success, result = get_bot_commands(token)

    if success:
        if result:
            click.echo("\n📋 Current bot commands:")
            for cmd in result:
                click.echo(f"   /{cmd['command']} - {cmd['description']}")
        else:
            click.echo("\n📋 No commands configured.")
            click.echo("💡 Use --set-defaults to add default Second Brain commands.")
    else:
        click.echo(f"❌ Failed to get commands: {result}", err=True)
        sys.exit(1)


@cli.command(name="interactive")
def interactive_cmd():
    """Launch interactive setup (default when no subcommand given)."""
    click.echo("🤖 Telegram Webhook Setup for Second Brain")
    click.echo("=" * 50)

    # Check for bot token
    try:
        token = get_telegram_bot_token()
        click.echo(f"✅ Bot token found: {token[:15]}...")
    except ValueError:
        click.echo("❌ TELEGRAM_BOT_TOKEN not set in environment.")
        click.echo("💡 Add it to .env.local or set the environment variable.")
        sys.exit(1)

    # Choose action
    action = inquirer.select(
        message="What would you like to do?",
        choices=[
            Choice("set", "Set up webhook"),
            Choice("info", "Get webhook info"),
            Choice("delete", "Delete webhook"),
            Choice("test", "Test bot connection"),
            Choice("commands", "Add bot commands"),
        ],
    ).execute()

    click.echo()

    if action == "set":
        # Get webhook URL
        webhook_url = get_webhook_url_from_stack()
        if webhook_url:
            click.echo(f"🔍 Found webhook URL: {webhook_url}")
            use_detected = inquirer.confirm(
                message="Use this URL?", default=True
            ).execute()
            if not use_detected:
                webhook_url = inquirer.text(
                    message="Enter webhook URL:",
                    validate=lambda x: x.startswith("https://"),
                    invalid_message="URL must start with https://",
                ).execute()
        else:
            click.echo("⚠️  Could not auto-detect webhook URL from CDK stack.")
            webhook_url = inquirer.text(
                message="Enter webhook URL:",
                validate=lambda x: x.startswith("https://"),
                invalid_message="URL must start with https://",
            ).execute()

        # Get secret token
        secret_token = get_secret_token()
        if secret_token:
            click.echo("✅ Secret token found in environment.")
        else:
            click.echo("⚠️  No TELEGRAM_SECRET_TOKEN in environment.")
            use_secret = inquirer.confirm(
                message="Enter a secret token manually?", default=False
            ).execute()
            if use_secret:
                secret_token = inquirer.secret(
                    message="Enter secret token:",
                    validate=lambda x: len(x) >= 8,
                    invalid_message="Secret token should be at least 8 characters",
                ).execute()

        # Confirm and set
        click.echo(f"\n📋 Summary:")
        click.echo(f"   Webhook URL: {webhook_url}")
        click.echo(f"   Secret token: {'Yes' if secret_token else 'No'}")

        if inquirer.confirm(message="Proceed?", default=True).execute():
            click.echo("\n⏳ Setting webhook...")
            success, message = set_webhook(token, webhook_url, secret_token)
            if success:
                click.echo(f"✅ {message}")
            else:
                click.echo(f"❌ {message}", err=True)

    elif action == "info":
        success, result = get_webhook_info(token)
        if success:
            click.echo("\n📋 Current webhook info:")
            click.echo(f"   URL: {result.get('url') or 'Not set'}")
            click.echo(f"   Pending updates: {result.get('pending_update_count', 0)}")
            if result.get("last_error_message"):
                click.echo(f"   Last error: {result.get('last_error_message')}")
        else:
            click.echo(f"❌ {result}", err=True)

    elif action == "delete":
        if inquirer.confirm(message="Delete webhook?", default=False).execute():
            success, message = delete_webhook(token)
            if success:
                click.echo(f"✅ {message}")
            else:
                click.echo(f"❌ {message}", err=True)

    elif action == "test":
        click.echo("🔍 Testing connection...")
        success, result = get_bot_info(token)
        if success:
            click.echo(f"✅ Connected to @{result.get('username')}")
        else:
            click.echo(f"❌ {result}", err=True)

    elif action == "commands":
        cmd_action = inquirer.select(
            message="What would you like to do with commands?",
            choices=[
                Choice("view", "View current commands"),
                Choice("set", "Set default Second Brain commands"),
                Choice("clear", "Clear all commands"),
            ],
        ).execute()

        if cmd_action == "view":
            success, result = get_bot_commands(token)
            if success and result:
                click.echo("\n📋 Current commands:")
                for cmd in result:
                    click.echo(f"   /{cmd['command']} - {cmd['description']}")
            elif success:
                click.echo("📋 No commands configured.")
            else:
                click.echo(f"❌ {result}", err=True)

        elif cmd_action == "set":
            click.echo("\n📋 Setting these commands:")
            for cmd in DEFAULT_BOT_COMMANDS:
                click.echo(f"   /{cmd['command']} - {cmd['description']}")
            if inquirer.confirm(message="Proceed?", default=True).execute():
                success, message = set_bot_commands(token, DEFAULT_BOT_COMMANDS)
                if success:
                    click.echo(f"✅ {message}")
                else:
                    click.echo(f"❌ {message}", err=True)

        elif cmd_action == "clear":
            if inquirer.confirm(message="Clear all commands?", default=False).execute():
                success, message = set_bot_commands(token, [])
                if success:
                    click.echo("✅ Commands cleared!")
                else:
                    click.echo(f"❌ {message}", err=True)


if __name__ == "__main__":
    cli()
