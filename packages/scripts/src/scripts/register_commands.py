#!/usr/bin/env python3
"""
Register Telegram bot commands for Second Brain.

Commands:
- /digest - Generate a digest summary
- /query - Ask your second brain anything
- /recent - Recent items by time
- /open - Open items needing action
- /stalled - Things you've been putting off
- /at - Items by location (work, home, store)
- /waiting - Waiting on others
- /decisions - Help me decide on something
"""

import click
from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from typing import Optional
import requests
import traceback
import common.environments


def get_bot_token() -> str:
    """Get bot token from environment or raise error."""
    from common.environments import get_telegram_bot_token

    return get_telegram_bot_token()


class CommandError(click.ClickException):
    """Custom exception with full traceback."""

    def __init__(self, message: str, cause: Exception | None = None):
        super().__init__(message)
        self.cause = cause

    def format_message(self):
        if self.cause:
            return f"{self.message}\n\nCause: {type(self.cause).__name__}: {self.cause}"
        return self.message


def set_commands(bot_token: str, commands: list) -> str:
    """Set bot commands via Telegram API."""
    url = f"https://api.telegram.org/bot{bot_token}/setMyCommands"

    command_objects = []
    for cmd in commands:
        command_objects.append({"command": cmd.command, "description": cmd.description})

    try:
        response = requests.post(url, json={"commands": command_objects}, timeout=30)
        response.raise_for_status()
        result = response.json()
    except requests.RequestException as e:
        raise CommandError("Failed to connect to Telegram API", e)

    if not result.get("ok"):
        raise CommandError(result.get("description", "Failed to set commands"))

    return f"Registered {len(commands)} commands successfully"


def get_commands(bot_token: str) -> list:
    """Get current bot commands."""
    url = f"https://api.telegram.org/bot{bot_token}/getMyCommands"

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        result = response.json()
    except requests.RequestException as e:
        raise CommandError("Failed to connect to Telegram API", e)

    if not result.get("ok"):
        raise CommandError(result.get("description", "Failed to get commands"))

    return result.get("result", [])


class Command:
    def __init__(self, command: str, description: str):
        self.command = command
        self.description = description


AVAILABLE_COMMANDS = [
    Command("digest", "Generate a daily or weekly digest summary"),
    Command("query", "Ask your second brain anything"),
    Command("recent", "Recent items by time"),
    Command("open", "Open items needing action"),
    Command("closed", "Recently completed items"),
    Command("stalled", "Things you've been putting off"),
    Command("at", "Items by location (work, home, store)"),
    Command("waiting", "Waiting on others"),
    Command("decisions", "Help me decide on something"),
]


@click.group(invoke_without_command=True)
@click.version_option(version="1.0.0")
@click.pass_context
def cli(ctx: click.Context):
    """Register Telegram bot commands for Second Brain."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(register_cmd)
    return


@cli.command()
@click.option("--token", "-t", help="Telegram bot token")
@click.option("--all", "-a", is_flag=True, help="Register all available commands")
def register_cmd(token: Optional[str], all: bool):
    """Register bot commands."""

    if not token:
        token = get_bot_token()
    else:
        click.echo(f"Using provided bot token: {token[:15]}...")

    commands_to_register = AVAILABLE_COMMANDS if all else [AVAILABLE_COMMANDS[0]]

    if not all:
        selected = inquirer.checkbox(
            message="Select commands to register:",
            choices=[
                Choice(cmd, f"/{cmd.command} - {cmd.description}")
                for cmd in AVAILABLE_COMMANDS
            ],
            validate=lambda x: len(x) > 0,
            invalid_message="Select at least one command",
        ).execute()

        commands_to_register = [cmd for cmd in selected]

    if not commands_to_register:
        click.echo("No commands selected.")
        return

    click.echo(f"\nRegistering {len(commands_to_register)} commands:")
    for cmd in commands_to_register:
        click.echo(f"   /{cmd.command} - {cmd.description}")

    if not inquirer.confirm("Proceed with registration?", default=True):
        click.echo("Cancelled.")
        return

    click.echo("\nRegistering commands...")
    message = set_commands(token, commands_to_register)
    click.echo(f"✅ {message}")


@cli.command()
@click.option("--token", "-t", help="Telegram bot token")
def list_cmd(token: Optional[str]):
    """List currently registered commands."""

    if not token:
        token = get_bot_token()
    else:
        click.echo(f"Using provided bot token: {token[:15]}...")

    click.echo("Getting current commands...")
    commands = get_commands(token)

    if commands:
        click.echo("\nRegistered commands:")
        for cmd in commands:
            click.echo(f"   /{cmd['command']} - {cmd['description']}")
    else:
        click.echo("No commands registered.")


if __name__ == "__main__":
    cli()
