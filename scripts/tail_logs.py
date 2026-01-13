#!/usr/bin/env python3
"""
Tail CloudWatch logs for Second Brain Lambda functions
"""

import boto3
import click
from datetime import datetime, timedelta
from typing import Optional
import sys
import os


# Simple boto3 client
def get_boto3_client(service_name: str, **kwargs):
    """Get boto3 client"""
    return boto3.client(service_name, **kwargs)


def get_lambda_functions() -> list:
    """Get all Lambda functions in Second Brain stack"""
    try:
        cf_client = get_boto3_client("cloudformation")
        response = cf_client.describe_stacks(StackName="SecondBrainStack")

        functions = []
        for resource in response["Stacks"][0]["Resources"]:
            if resource["ResourceType"] == "AWS::Lambda::Function":
                function_name = resource.get("PhysicalResourceId", "")
                if function_name:
                    functions.append(function_name)

        return functions
    except Exception as e:
        click.echo(f"❌ Error getting Lambda functions: {e}", err=True)
        return []


def get_log_group_name(function_name: str) -> str:
    """Get CloudWatch log group name for Lambda function"""
    return f"/aws/lambda/{function_name}"


def get_log_streams(logs_client, log_group_name: str, hours_back: int = 1):
    """Get log streams from last N hours"""
    try:
        start_time = datetime.utcnow() - timedelta(hours=hours_back)

        response = logs_client.describe_log_streams(
            logGroupName=log_group_name,
            orderBy="LastEventTime",
            descending=True,
            limit=10,
        )

        # Filter streams that have events in time window
        streams = []
        for stream in response["logStreams"]:
            if "lastEventTimestamp" in stream:
                if stream["lastEventTimestamp"] > start_time:
                    streams.append(stream["logStreamName"])

        return streams[:5]  # Return latest 5 streams
    except Exception as e:
        click.echo(f"⚠️  Error getting log streams: {e}", err=True)
        return []


def tail_logs(
    logs_client,
    log_group_name: str,
    log_stream_names: list,
    follow: bool = False,
    hours_back: int = 1,
):
    """Tail CloudWatch logs from specified streams"""
    try:
        start_time = datetime.utcnow() - timedelta(hours=hours_back)

        kwargs = {
            "logGroupName": log_group_name,
            "logStreamNames": log_stream_names,
            "startTime": int(start_time.timestamp() * 1000),
            "interleaved": True,
        }

        if not follow:
            kwargs["limit"] = 1000

        response = logs_client.filter_log_events(**kwargs)

        events = response["events"]

        # Display events
        for event in events:
            timestamp = event["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
            message = event["message"]

            click.echo(f"{timestamp} - {message}")

        # If following, keep polling for new events
        if follow and "nextToken" in response:
            click.echo("📡 Following logs (Ctrl+C to stop)...")
            kwargs["nextToken"] = response["nextToken"]

            try:
                while True:
                    response = logs_client.filter_log_events(**kwargs)

                    for event in response["events"]:
                        timestamp = event["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                        message = event["message"]
                        click.echo(f"{timestamp} - {message}")

                    if "nextToken" not in response:
                        click.echo("📝 End of log stream")
                        break

                    kwargs["nextToken"] = response["nextToken"]

                    # Add a small delay to avoid hitting API limits
                    import time

                    time.sleep(1)

            except KeyboardInterrupt:
                click.echo("\n👋 Stopped following logs")

    except Exception as e:
        print(f"❌ Error tailing logs: {e}", err=True)


@click.command()
@click.option("--lambda-name", "-l", help="Specific Lambda function name")
@click.option("--follow", "-f", is_flag=True, help="Follow logs (like tail -f)")
@click.option("--hours", "-h", default=1, help="Hours back to fetch logs (default: 1)")
def tail(lambda_name: Optional[str], follow: bool, hours: int):
    """Tail CloudWatch logs for Second Brain Lambda functions"""

    if not lambda_name:
        # Get all Lambda functions and let user choose
        functions = get_lambda_functions()
        if not functions:
            click.echo("❌ No Lambda functions found in SecondBrainStack", err=True)
            return

        click.echo("📋 Available Lambda functions:")
        for i, func in enumerate(functions, 1):
            click.echo(f"  {i}. {func}")

        try:
            choice = click.prompt(
                "Select Lambda function to tail", type=click.IntRange(1, len(functions))
            )
            lambda_name = functions[choice - 1]
        except (click.Abort, click.exceptions.ClickException):
            click.echo("❌ No selection made", err=True)
            return

    click.echo(f"📊 Tailing logs for {lambda_name}...")
    click.echo(f"⏰  Showing logs from last {hours_back} hour(s)")
    if follow:
        click.echo("📡 Following logs (Ctrl+C to stop)")

    # Initialize CloudWatch Logs client
    logs_client = get_boto3_client("logs")
    log_group_name = get_log_group_name(lambda_name)

    # Get log streams
    log_streams = get_log_streams(logs_client, log_group_name, hours_back)

    if not log_streams:
        click.echo(f"ℹ️  No recent log streams found for {lambda_name}")
        click.echo(
            f"💡 Try running: uv run tail-logs --lambda-name {lambda_name} --hours 24"
        )
        return

    click.echo(f"📂 Using log streams: {', '.join(log_streams[:3])}")
    click.echo("─" * 60)

    # Tail logs
    tail_logs(logs_client, log_group_name, log_streams, follow, hours_back)


if __name__ == "__main__":
    tail()
