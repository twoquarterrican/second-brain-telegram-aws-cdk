#!/usr/bin/env python3
"""
CLI to trigger the digest Lambda function for Second Brain.
Supports both CLI flags and interactive prompts.
"""

import os
import sys
import json
import click
from typing import Optional
from InquirerPy import inquirer
from InquirerPy.base.control import Choice

from common.environments import (
    get_aws_session,
    find_lambda_function,
    get_trigger_role_arn,
    assume_role,
    assume_second_brain_trigger_role,
)


@click.group(invoke_without_command=True)
@click.version_option(version="1.0.0")
@click.pass_context
def cli(ctx: click.Context):
    """Trigger Second Brain digest Lambda function."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(trigger_cmd)
    return


def get_digest_type_interactive() -> str:
    """Get digest type interactively."""
    return inquirer.select(
        message="Digest type:",
        choices=[
            Choice("daily", "Daily digest (last 24 hours)"),
            Choice("weekly", "Weekly digest (last 7 days)"),
        ],
        default="daily",
    ).execute()


def get_function_name_interactive() -> str:
    """Get Lambda function name interactively."""
    function_name = find_lambda_function("DigestLambda")

    if function_name:
        use_detected = inquirer.confirm(
            message=f"Detected function: {function_name}. Use this?",
            default=True,
        ).execute()
        if use_detected:
            return function_name

    return inquirer.text(
        message="Enter Lambda function name:",
        default="DigestLambda" if not function_name else function_name,
        validate=lambda x: len(x) >= 1,
        invalid_message="Function name cannot be empty",
    ).execute()


def get_role_arn_interactive(region: str) -> Optional[str]:
    """Get trigger role ARN interactively."""
    role_arn = get_trigger_role_arn()

    if role_arn:
        use_detected = inquirer.confirm(
            message=f"Detected trigger role: {role_arn}. Use this?",
            default=True,
        ).execute()
        if use_detected:
            return role_arn

    use_role = inquirer.confirm(
        message="Use a role for Lambda invocation?",
        default=False,
    ).execute()

    if use_role:
        return inquirer.text(
            message="Enter role ARN:",
            validate=lambda x: x.startswith("arn:aws:iam::"),
            invalid_message="Must be a valid IAM role ARN",
        ).execute()

    return None


@cli.command()
@click.option(
    "--digest-type",
    "-t",
    type=click.Choice(["daily", "weekly"]),
    help="Digest type (daily/weekly)",
)
@click.option("--interactive", "-i", is_flag=True, help="Force interactive mode")
def trigger_cmd(
    digest_type: Optional[str],
    interactive: bool,
):
    """Trigger the digest Lambda function."""
    session = assume_second_brain_trigger_role()

    # Get function name
    function_name = find_lambda_function("DigestLambda")
    if not function_name:
        click.echo(
            "❌ Could not detect Lambda function name.",
            err=True,
        )
        sys.exit(1)

    # Get digest type
    if not digest_type:
        if interactive:
            digest_type = get_digest_type_interactive()
        else:
            digest_type = "daily"

    # Summary
    click.echo("\n📋 Trigger Configuration:")
    click.echo(f"   Region: {region}")
    click.echo(f"   Function: {function_name}")
    click.echo(f"   Digest Type: {digest_type}")
    click.echo(f"   Role: {role_arn}")

    if (
        interactive
        and not inquirer.confirm(
            message="Proceed with triggering digest?",
            default=True,
        ).execute()
    ):
        click.echo("❌ Cancelled.")
        return

    # Trigger Lambda
    click.echo(f"\n⏳ Triggering {digest_type} digest...")

    try:
        lambda_client = session.client("lambda", region_name=region)

        # Prepare event
        event = {
            "digest_type": digest_type,
            "source": "cli-trigger",
        }

        # Invoke Lambda
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(event),
        )

        status_code = response.get("StatusCode", 0)
        function_error = response.get("FunctionError", "")
        log_result = response.get("LogResult", "")

        if function_error:
            click.echo(f"❌ Lambda function error: {function_error}", err=True)
            if log_result:
                click.echo(f"   Logs: {log_result}")
            sys.exit(1)

        if status_code == 200:
            payload = response.get("Payload")
            if payload:
                payload_bytes = payload.read()
                if payload_bytes:
                    payload_str = payload_bytes.decode("utf-8")
                    try:
                        payload_json = json.loads(payload_str)
                        click.echo(f"\n✅ Digest triggered successfully!")
                        click.echo(f"   Response: {json.dumps(payload_json, indent=2)}")
                    except json.JSONDecodeError:
                        click.echo(f"\n✅ Digest triggered successfully!")
                        click.echo(f"   Response: {payload_str}")
                else:
                    click.echo(f"\n✅ Digest triggered successfully! (no payload)")
            else:
                click.echo(f"\n✅ Digest triggered successfully! (no response body)")
        else:
            click.echo(f"❌ Unexpected status code: {status_code}", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"❌ Error triggering digest: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
