#!/usr/bin/env python3
"""
Debug DynamoDB commands using SecondBrainTriggerRole.

Usage:
    eval "$(uv run dynamo-debug <command>)"

Commands:
    scan            - Scan all items from table
    query           - Query with optional key condition
    count           - Count items by status
    items           - Show all items with key fields
    gsi-query       - Query StatusIndex GSI
    completed       - Show completed items
"""

import click

from common.environments import get_table


@click.group(invoke_without_command=True)
@click.version_option(version="1.0.0")
@click.pass_context
def cli(ctx: click.Context):
    """Debug DynamoDB commands using SecondBrainTriggerRole."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(scan)
    return


@cli.command()
@click.option("--limit", "-l", default=50, help="Max items to return")
def scan(limit: int):
    """Scan all items from table."""
    table = get_table(second_brain_trigger_role=True)
    response = table.scan(Limit=limit)
    items = response.get("Items", [])

    click.echo(f"Found {len(items)} items:\n")
    for item in items:
        click.echo(f"- {item}")
    return items


@cli.command()
@click.option("--limit", "-l", default=20, help="Max items to return")
def items(limit: int):
    """Show all items with key fields (PK, SK, status, category, name)."""
    table = get_table()
    response = table.scan(Limit=limit)
    items = response.get("Items", [])

    for item in items:
        pk = item.get("PK", "N/A")
        sk = item.get("SK", "N/A")
        status = item.get("status", "none")
        category = item.get("category", "N/A")
        name = item.get("name", "N/A")
        click.echo(f"[{status:>10}] {category:>10} | {name:>30} | {pk} {sk}")


@cli.command()
def count():
    """Count items by status."""
    table = get_table()
    response = table.scan()
    items = response.get("Items", [])

    by_status: dict[str, int] = {}
    by_category_status: dict[str, dict[str, int]] = {}

    for item in items:
        status = item.get("status", "none")
        category = item.get("category", "Unknown")

        by_status[status] = by_status.get(status, 0) + 1

        if category not in by_category_status:
            by_category_status[category] = {}
        by_category_status[category][status] = (
            by_category_status[category].get(status, 0) + 1
        )

    click.echo("By status:")
    for status, count in sorted(by_status.items()):
        click.echo(f"  {status}: {count}")

    click.echo("\nBy category and status:")
    for category, statuses in sorted(by_category_status.items()):
        click.echo(f"  {category}:")
        for status, count in sorted(statuses.items()):
            click.echo(f"    {status}: {count}")


@cli.command()
@click.option("--status", default="completed", help="Status to query")
def gsi_query(status: str):
    """Query StatusIndex GSI."""
    table = get_table()
    response = table.query(
        IndexName="StatusIndex",
        KeyConditionExpression="#s = :s",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": status},
    )
    items = response.get("Items", [])

    click.echo(f"Found {len(items)} items with status={status}:\n")
    for item in items:
        pk = item.get("PK", "N/A")
        sk = item.get("SK", "N/A")
        name = item.get("name", "N/A")
        click.echo(f"[{status}] {name} | {pk} {sk}")


@cli.command()
def completed():
    """Show completed items."""
    table = get_table()
    response = table.query(
        IndexName="StatusIndex",
        KeyConditionExpression="#s = :s",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": "completed"},
    )
    items = response.get("Items", [])

    click.echo(f"Found {len(items)} completed items:\n")
    for item in items:
        pk = item.get("PK", "N/A")
        sk = item.get("SK", "N/A")
        name = item.get("name", "N/A")
        category = item.get("category", "N/A")
        click.echo(f"[{category}] {name} | {pk} {sk}")


@cli.command()
@click.argument("pk")
@click.argument("sk")
def get(pk: str, sk: str):
    """Get a specific item by PK and SK."""
    table = get_table()
    response = table.get_item(Key={"PK": pk, "SK": sk})
    item = response.get("Item")

    if item:
        import json

        click.echo(json.dumps(item, indent=2, default=str))
    else:
        click.echo("Item not found")


if __name__ == "__main__":
    cli()
