#!/usr/bin/env python2
"""
Tail CloudWatch logs for Second Brain Lambda functions
"""

from datetime import datetime, timedelta, timezone
import boto3
import click
from datetime import datetime, timedelta
from typing import Optional, Iterable
import sys
import os
from common.environments import get_boto3_client
from InquirerPy import inquirer


def get_lambda_functions() -> Iterable[str]:
    """Get all Lambda functions in Second Brain stack"""
    cf_client = get_boto3_client("cloudformation")
    paginator = cf_client.get_paginator("list_stack_resources")
    # Use paginator to handle stacks with many resources
    page_iterator = paginator.paginate(StackName="SecondBrainStack")
    for page in page_iterator:
        for resource in page["StackResourceSummaries"]:
            if resource["ResourceType"] == "AWS::Lambda::Function":
                function_name = resource.get("PhysicalResourceId", "")
                if function_name:
                    yield function_name


def get_log_group_name(function_name: str) -> str:
    """Get CloudWatch log group name for Lambda function"""
    return f"/aws/lambda/{function_name}"


def get_log_streams(logs_client, log_group_name: str):
    """Get log streams from last N hours"""
    try:
        response = logs_client.describe_log_streams(
            logGroupName=log_group_name,
            orderBy="LastEventTime",
            descending=True,
            limit=5,
        )

        # Filter streams that have events in time window
        streams = []
        for stream in response["logStreams"]:
            if "lastEventTimestamp" in stream:
                streams.append(stream["logStreamName"])

        return streams
    except Exception as e:
        click.echo(f"⚠️  Error getting log streams: {e}", err=True)
        return []


def tail_logs(
    logs_client,
    log_group_name: str,
    log_stream_names: list,
    follow: bool = False,
    hours_back: float = 1,
):
    """Tail CloudWatch logs from specified streams"""
    try:
        start_time = datetime.now(timezone.utc) - timedelta(seconds=int(hours_back * 60 * 60))

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
            timestamp_ = event["timestamp"]
            timestamp = strf_epoch_millis(timestamp_)
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
                        timestamp = strf_epoch_millis(event["timestamp"])
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
        click.echo(f"❌ Error tailing logs: {e}", err=True)


def strf_epoch_millis(timestamp_):
    return datetime.fromtimestamp(timestamp_ / 1000).strftime("%Y-%m-%d %H:%M:%S")


@click.command()
@click.option("--lambda-name", "-l", help="Specific Lambda function name")
@click.option("--follow", "-f", is_flag=True, help="Follow logs (like tail -f)")
@click.option("--hours", "-h", default=1.0, help="Hours back to fetch logs (default: 1)")
def tail(lambda_name: Optional[str], follow: bool, hours: float):
    """Tail CloudWatch logs for Second Brain Lambda functions"""

    if not lambda_name:
        # Get all Lambda functions and let user choose
        functions = list(get_lambda_functions())
        if not functions:
            click.echo("❌ No Lambda functions found in SecondBrainStack", err=True)
            return

        try:
            lambda_name = inquirer.select(
                message="Select Lambda function to tail:",
                choices=functions,
            ).execute()
        except (KeyboardInterrupt, EOFError):
            click.echo("❌ No selection made", err=True)
            return

    click.echo(f"📊 Tailing logs for {lambda_name}...")
    click.echo(f"⏰  Showing logs from last {hours} hour(s)")
    if follow:
        click.echo("📡 Following logs (Ctrl+C to stop)")

    # Initialize CloudWatch Logs client
    logs_client = get_boto3_client("logs")
    if not lambda_name:
        click.echo("❌ No Lambda function selected", err=True)
        return
    log_group_name = get_log_group_name(lambda_name)

    # Get log streams
    log_streams = get_log_streams(logs_client, log_group_name)

    if not log_streams:
        click.echo(f"ℹ️  No recent log streams found for {lambda_name}")
        click.echo(
            f"💡 Try running: uv run tail-logs --lambda-name {lambda_name} --hours 24"
        )
        return

    click.echo(f"📂 Using log streams: {', '.join(log_streams[:3])}")
    click.echo("─" * 60)

    # Tail logs
    tail_logs(logs_client, log_group_name, log_streams, follow, hours)


if __name__ == "__main__":
    tail()
