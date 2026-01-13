#!/usr/bin/env python3
"""
Telegram Webhook CLI for Second Brain using Click + InquirerPy.
Provides both traditional CLI commands and interactive prompts.
"""

import os
import sys
import subprocess
import json
from typing import Optional, Tuple, Any

import click

from InquirerPy import inquirer
from InquirerPy.base.control import Choice


def load_env_config() -> dict:
    """Load configuration from env.json file"""
    env_file = "env.json"
    if os.path.exists(env_file):
        try:
            with open(env_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            click.echo(f"⚠️  Warning: Could not read env.json: {e}", err=True)
    return {}


def get_function_url(function_name: str, region: str = "us-east-1") -> Optional[str]:
    """Get Function URL for a Lambda function using AWS CLI"""
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

        config = json.loads(result.stdout)
        return config["FunctionUrl"]
    except subprocess.CalledProcessError as e:
        click.echo(f"❌ Error getting function URL: {e.stderr}", err=True)
        return None
    except json.JSONDecodeError as e:
        click.echo(f"❌ Error parsing function URL response: {e}", err=True)
        return None


def get_function_url_from_cdk(
    stack_name: str = "SecondBrainStack", region: str = "us-east-1"
) -> Optional[str]:
    """Get Function URL from CDK stack outputs using AWS CLI"""
    try:
        result = subprocess.run(
            [
                "aws",
                "cloudformation",
                "describe-stacks",
                "--stack-name",
                stack_name,
                "--region",
                region,
                "--query",
                "Stacks[0].Outputs[?OutputKey=='ProcessorFunctionUrl'].OutputValue",
                "--output",
                "text",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        # The output is already the URL string from the query
        function_url = result.stdout.strip()
        return function_url if function_url else None

    except subprocess.CalledProcessError as e:
        click.echo(f"❌ Error getting CDK stack outputs: {e.stderr}", err=True)
        click.echo(
            f"💡 Make sure you've deployed the CDK stack first: 'cdk deploy'", err=True
        )
        return None
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)
        return None


def set_webhook(
    bot_token: str, webhook_url: str, secret_token: Optional[str] = None
) -> Tuple[bool, str]:
    """Set Telegram webhook"""
    import requests

    url = f"https://api.telegram.org/bot{bot_token}/setWebhook"

    payload = {"url": webhook_url}
    if secret_token:
        payload["secret_token"] = secret_token

    try:
        response = requests.post(url, json=payload, timeout=30)
        result = response.json()

        if result.get("ok"):
            return True, "Webhook set successfully!"
        else:
            return False, result.get("description", "Unknown error")

    except Exception as e:
        return False, str(e)


def get_webhook_info(bot_token: str) -> Tuple[bool, Any]:
    """Get current webhook information"""
    import requests

    url = f"https://api.telegram.org/bot{bot_token}/getWebhookInfo"

    try:
        response = requests.get(url, timeout=30)
        result = response.json()

        if result.get("ok"):
            return True, result["result"]
        else:
            return False, result.get("description", "Unknown error")

    except Exception as e:
        return False, str(e)


def delete_webhook(bot_token: str) -> Tuple[bool, str]:
    """Delete Telegram webhook"""
    import requests

    url = f"https://api.telegram.org/bot{bot_token}/deleteWebhook"

    try:
        response = requests.post(url, timeout=30)
        result = response.json()

        if result.get("ok"):
            return True, "Webhook deleted successfully!"
        else:
            return False, result.get("description", "Unknown error")

    except Exception as e:
        return False, str(e)


def get_bot_token_interactive() -> str:
    """Get bot token from user input"""
    return inquirer.text(
        message="Enter your Telegram Bot Token:",
        validate=lambda x: len(x) > 10 and ":" in x,
        invalid_message="Please enter a valid Telegram bot token (should contain ':')",
        transformer=lambda x: f"{x[:15]}..." if len(x) > 15 else x,
    ).execute()


def get_bot_token(env_config: dict) -> str:
    """Get bot token from env.json or interactive input"""
    default_token = env_config.get("TelegramBotToken", "")

    if default_token:
        click.echo(f"📋 Found bot token in env.json: {default_token[:15]}...")
        use_env_token = inquirer.confirm(
            message="Use bot token from env.json?", default=True
        ).execute()

        if use_env_token:
            return default_token

    click.echo("📋 Getting bot token from user input...")
    return get_bot_token_interactive()


def get_secret_token_interactive(env_config: dict) -> Optional[str]:
    """Get secret token from user input"""
    if inquirer.confirm("Generate random secret token?", default=True):
        import secrets

        secret_token = secrets.token_urlsafe(32)
        click.echo(f"🔑 Generated secret token: {secret_token}")
        return secret_token
    else:
        # Try to read from env.json
        env_secret = env_config.get("TelegramSecretToken", "")
        if env_secret:
            click.echo(f"📋 Found secret token in env.json: {env_secret[:8]}...")
            use_env_secret = inquirer.confirm(
                message="Use secret token from env.json?", default=True
            ).execute()

            if use_env_secret:
                return env_secret

        return inquirer.text(
            message="Enter secret token:",
            validate=lambda x: len(x) >= 8,
            invalid_message="Secret token must be at least 8 characters",
        ).execute()


@click.group(invoke_without_command=True)
@click.version_option(version="1.0.0")
@click.pass_context
def cli(ctx: click.Context):
    """Telegram Webhook CLI for Second Brain Setup."""
    if ctx.invoked_subcommand is None:
        # Default to interactive mode when no subcommand is specified
        ctx.invoke(interactive_cmd)
        return


@cli.command()
@click.option("--token", "-t", help="Telegram bot token")
@click.option("--webhook-url", "-w", help="Webhook URL")
@click.option("--secret-token", "-s", help="Secret token for webhook verification")
@click.option(
    "--function-name",
    "-f",
    default="ProcessorLambda",
    help="AWS Lambda function name",
)
@click.option("--region", "-r", default="us-east-1", help="AWS region")
@click.option(
    "--auto-detect",
    "-a",
    is_flag=True,
    help="Auto-detect webhook URL from CDK stack outputs",
)
def set_cmd(
    token: Optional[str],
    webhook_url: Optional[str],
    secret_token: Optional[str],
    function_name: str,
    region: str,
    auto_detect: bool,
):
    """Set up Telegram webhook."""

    click.echo("🔧 Setting up Telegram webhook...")

    # Load env.json config
    env_config = load_env_config()

    # Get bot token
    if not token:
        token = get_bot_token(env_config)
    else:
        click.echo(f"📋 Using provided bot token: {token[:15]}...")

    # Get webhook URL
    if not webhook_url:
        if auto_detect:
            click.echo("🔍 Auto-detecting webhook URL from CDK stack...")
            webhook_url = get_function_url_from_cdk("SecondBrainStack", region)
            if not webhook_url:
                click.echo(
                    "❌ Could not get function URL from CDK stack. Please check AWS CLI configuration and permissions.",
                    err=True,
                )
                click.echo(
                    "💡 Make sure you've deployed the CDK stack first: 'cdk deploy'",
                    err=True,
                )
                sys.exit(1)
        else:
            source = inquirer.select(
                message="How do you want to get webhook URL?",
                choices=[
                    Choice("cdk", "Auto-detect from CDK stack outputs (recommended)"),
                    Choice("lambda", "Direct Lambda function lookup"),
                    Choice("manual", "Enter manually"),
                ],
            ).execute()

            if source == "cdk":
                webhook_url = get_function_url_from_cdk("SecondBrainStack", region)
                if not webhook_url:
                    click.echo(
                        "❌ Could not get function URL from CDK stack. Please check AWS CLI configuration and permissions.",
                        err=True,
                    )
                    click.echo(
                        "💡 Make sure you've deployed the CDK stack first: 'cdk deploy'",
                        err=True,
                    )
                    sys.exit(1)
            elif source == "lambda":
                function_name = inquirer.text(
                    message="Lambda function name:",
                    default=function_name,
                ).execute()
                region = inquirer.text(
                    message="AWS region:",
                    default=region,
                ).execute()

                webhook_url = get_function_url(function_name, region)
                if not webhook_url:
                    click.echo(
                        "❌ Could not get function URL. Please check AWS CLI configuration and permissions.",
                        err=True,
                    )
                    sys.exit(1)
            else:
                webhook_url = inquirer.text(
                    message="Enter webhook URL:",
                    validate=lambda x: x.startswith("https://"),
                    invalid_message="Please enter a valid HTTPS URL",
                ).execute()
    else:
        click.echo(f"📋 Using provided webhook URL: {webhook_url}")

    # Get secret token
    if not secret_token:
        use_secret = inquirer.confirm(
            message="Use secret token for webhook security?", default=True
        ).execute()

        if use_secret:
            secret_token = get_secret_token_interactive(env_config)
    else:
        click.echo("📋 Using provided secret token")

    # Ensure webhook_url is not None
    if webhook_url is None:
        click.echo("❌ Webhook URL is required.", err=True)
        return

    # Confirmation
    click.echo(f"\n📋 Webhook Configuration Summary:")
    click.echo(f"   Bot Token: {token[:15]}...")
    click.echo(f"   Webhook URL: {webhook_url}")
    click.echo(f"   Secret Token: {'Yes' if secret_token else 'No'}")

    if not inquirer.confirm("Proceed with webhook setup?", default=True):
        click.echo("❌ Cancelled.")
        return

    # Set webhook
    click.echo("⏳ Setting webhook...")
    success, message = set_webhook(token, webhook_url, secret_token)

    if success:
        click.echo("✅ Webhook set successfully!")
        click.echo(f"   URL: {webhook_url}")
        if secret_token:
            click.echo("   Secret token configured")
        click.echo("\n🎉 Your Second Brain bot is ready to receive messages!")
    else:
        click.echo(f"❌ Failed to set webhook: {message}", err=True)


@cli.command()
@click.option("--token", "-t", help="Telegram bot token")
def info_cmd(token: Optional[str]):
    """Get current webhook information."""

    if not token:
        env_config = load_env_config()
        token = get_bot_token(env_config)
    else:
        click.echo(f"📋 Using provided bot token: {token[:15]}...")

    click.echo("🔍 Getting webhook information...")
    success, result = get_webhook_info(token)

    if success:
        click.echo("\n📋 Current webhook info:")
        click.echo(f"   URL: {result.get('url', 'Not set')}")
        click.echo(
            f"   Has custom certificate: {result.get('has_custom_certificate', False)}"
        )
        click.echo(f"   Pending updates: {result.get('pending_update_count', 0)}")
        click.echo(f"   Last error: {result.get('last_error_message', 'None')}")
        click.echo(f"   Custom secret: {'Yes' if result.get('secret_token') else 'No'}")
    else:
        click.echo(f"❌ Failed to get webhook info: {result}", err=True)


@cli.command()
@click.option("--token", "-t", help="Telegram bot token")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
def delete_cmd(token: Optional[str], force: bool):
    """Delete Telegram webhook."""

    if not token:
        env_config = load_env_config()
        token = get_bot_token(env_config)
    else:
        click.echo(f"📋 Using provided bot token: {token[:15]}...")

    if not force:
        confirm = inquirer.confirm(
            message="Are you sure you want to delete webhook?", default=False
        ).execute()

        if not confirm:
            click.echo("❌ Cancelled.")
            return

    click.echo("🗑️  Deleting webhook...")
    success, message = delete_webhook(token)

    if success:
        click.echo(f"✅ {message}")
    else:
        click.echo(f"❌ Failed to delete webhook: {message}", err=True)


@cli.command()
@click.option("--token", "-t", help="Telegram bot token")
def test_cmd(token: Optional[str]):
    """Test bot connection."""

    if not token:
        env_config = load_env_config()
        token = get_bot_token(env_config)
    else:
        click.echo(f"📋 Using provided bot token: {token[:15]}...")

    click.echo("🔍 Testing bot connection...")
    success, result = get_webhook_info(token)

    if success:
        webhook_url = result.get("url", "Not configured")
        click.echo(f"✅ Bot is accessible! Webhook URL: {webhook_url}")
    else:
        click.echo(f"❌ Failed to connect to bot: {result}", err=True)


@cli.command(name="interactive")
def interactive_cmd():
    """Launch interactive setup (recommended for first-time users)."""

    click.echo("🤖 Telegram Webhook Setup for Second Brain")
    click.echo("=" * 50)

    # Load env.json config
    env_config = load_env_config()

    # Get bot token
    token = get_bot_token(env_config)

    # Choose action
    action = inquirer.select(
        message="What would you like to do?",
        choices=[
            Choice("set", "Set up new webhook"),
            Choice("info", "Get current webhook info"),
            Choice("delete", "Delete webhook"),
            Choice("test", "Test bot connection"),
        ],
    ).execute()

    if action == "set":
        # Use set command logic without arguments to trigger interactive mode
        click.echo("🔧 Setting up webhook interactively...")
        set_cmd(None, None, None, "ProcessorLambda", "us-east-1", False)
    elif action == "info":
        info_cmd(token)
    elif action == "delete":
        delete_cmd(token, False)
    elif action == "test":
        test_cmd(token)


if __name__ == "__main__":
    cli()
