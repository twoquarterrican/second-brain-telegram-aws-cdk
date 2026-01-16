# AGENTS.md

This file provides guidance for AI assistants when working with this codebase.

## Click CLI Pattern

When creating new CLI entry points, use Click with the following pattern:

1. **Use `@click.group` with `invoke_without_command=True`** to allow running the CLI without a subcommand, defaulting to the main command
2. **Add `@click.version_option`** for version support
3. **Use Click options for all arguments** with optional types
4. **Make arguments optional (`Optional[...]`) and prompt interactively when not provided**
5. **Use InquirerPy for interactive prompts** when values are missing
6. **Use `@cache` decorator** for expensive operations like AWS clients

### Example Structure

```python
#!/usr/bin/env python3
import click
from typing import Optional
from InquirerPy import inquirer
from functools import cache

@click.group(invoke_without_command=True)
@click.version_option(version="1.0.0")
@click.pass_context
def cli(ctx: click.Context):
    """CLI description."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(main_cmd)
    return

def get_value_interactive() -> str:
    """Get value from user interactively."""
    return inquirer.text(
        message="Enter value:",
        default="default",
    ).execute()

@cli.command()
@click.option("--value", "-v", help="Some value")
@click.option("--interactive", "-i", is_flag=True, help="Force interactive mode")
def main_cmd(value: Optional[str], interactive: bool):
    """Main command."""
    if not value:
        if interactive:
            value = get_value_interactive()
        else:
            value = "default"

    click.echo(f"Value: {value}")

if __name__ == "__main__":
    cli()
```

### Key Points

- Entry point should be `module:function` format in `pyproject.toml`
- Use `invoke_without_command=True` to allow running without subcommand
- Always use `@click.pass_context` for the group command
- Use InquirerPy for all interactive prompts
- Cache AWS clients and other expensive lookups with `@cache`

## Deployment

See [DEPLOY.md](./DEPLOY.md) for full deployment instructions.

**Deploy to AWS:**
```bash
uv run cdkw deploy
```

**Other useful commands:**
```bash
uv run cdkw synth      # Preview CloudFormation template
uv run cdkw diff       # Show changes before deploying
uv run cdkw destroy    # Delete the stack
```

## Environment Variables

**Always use `common.environments` for environment variables in scripts.**

When a script needs access to environment variables (API keys, AWS credentials, etc.), import from `common.environments` instead of using `os.getenv()` directly:

```python
import common.environments  # Loads .env.local automatically

# Access environment variables
api_key = common.environments.get_api_key("ANTHROPIC_API_KEY")
session = common.environments.get_aws_session()
```

Configure variables in `.env.local`:

```bash
# .env.local
AWS_PROFILE=myprofile
AWS_REGION=us-east-1
ANTHROPIC_API_KEY=your_key
TELEGRAM_BOT_TOKEN=your_token
```

Do not use `os.environ` or `os.getenv()` in scripts.

## AssumeRole Pattern for Scripts

For scripts that need elevated or scoped permissions, use the AssumeRole pattern:

1. **Define a role in CDK** with the specific permissions needed
2. **Export the role ARN** as a CloudFormation output
3. **Script assumes the role** to get temporary credentials

### CDK Role Example

```python
from aws_cdk import Stack, aws_iam as iam
import os

class SecondBrainStack(Stack):
    def __init__(self, scope, construct_id, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # Trust policy defaults to current account (self.account)
        # Set TRIGGER_ROLE_TRUST_ACCOUNT for cross-account access
        trust_account = os.getenv("TRIGGER_ROLE_TRUST_ACCOUNT", self.account)

        trigger_role = iam.Role(
            self,
            "TriggerRole",
            role_name="SecondBrainTriggerRole",
            assumed_by=iam.AccountPrincipal(trust_account),
        )

        # Add specific permissions
        trigger_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["lambda:InvokeFunction"],
                resources=["*"],
            )
        )

        # Export ARN
        CfnOutput(
            self,
            "TriggerRoleArn",
            value=trigger_role.role_arn,
        )
```

**Note**: When `TRIGGER_ROLE_TRUST_ACCOUNT` is not set, the role trusts the same account it's deployed in. This is the default and simplest setup. Set it to a different account ID for cross-account access.

### Script AssumeRole Pattern

```python
import boto3
from functools import cache

@cache
def get_sts_client():
    return boto3.client("sts")

def assume_role(role_arn: str, session_name: str = "ScriptSession"):
    """Assume a role and return a session with temporary credentials."""
    sts = get_sts_client()
    response = sts.assume_role(
        RoleArn=role_arn,
        RoleSessionName=session_name,
    )

    credentials = response["Credentials"]

    return boto3.Session(
        aws_access_key_id=credentials["AccessKeyId"],
        aws_secret_access_key=credentials["SecretAccessKey"],
        aws_session_token=credentials["SessionToken"],
    )

# Usage
session = assume_role("arn:aws:iam::123456789:role/SecondBrainTriggerRole")
lambda_client = session.client("lambda")
```

### Benefits

- **Least privilege**: User only needs `sts:AssumeRole` on one ARN
- **Maintainable**: Permissions defined in CDK, version controlled, auto-deployed
- **Audit trail**: CloudTrail logs role assumption events
- **No IAM user modifications**: Changes via CDK deploy

## Environment Variables

All Python files outside the `lambdas` package should use `common.environments` for environment variables. Simply importing it loads `.env.local` via dotenv:

```python
from common.environments import get_aws_session

# Environment variables (AWS_PROFILE, AWS_REGION, etc.) are now available
session = get_aws_session()
```

Do not manually set `os.environ` values in scripts. Configure them in `.env.local` instead:

```bash
# .env.local
AWS_PROFILE=myprofile
AWS_REGION=us-east-1
ANTHROPIC_API_KEY=your_key
```

This ensures consistent configuration across all scripts.

## Stack Resource Utilities

All common CloudFormation stack functions should go in `common.environments`. Use paginators when dealing with resources that may exceed the default page size:

```python
def list_stack_resources(stack_name: str):
    """Generator that yields all resources in a CloudFormation stack.

    Uses paginator to handle stacks with more than 100 resources.
    Yields dicts with 'LogicalResourceId', 'ResourceType', and 'PhysicalResourceId'.
    """
    cfn = get_cfn_client(region)
    paginator = cfn.get_paginator("list_stack_resources")
    page_iterator = paginator.paginate(StackName=stack_name)

    for page in page_iterator:
        for resource in page.get("StackResourceSummaries", []):
            yield resource


def find_lambda_function(logical_id_prefix: str) -> Optional[str]:
    """Find a Lambda function by logical resource ID prefix."""
    for resource in list_stack_resources("SecondBrainStack"):
        logical_id = resource.get("LogicalResourceId", "")
        resource_type = resource.get("ResourceType", "")
        physical_id = resource.get("PhysicalResourceId", "")

        if resource_type == "AWS::Lambda::Function" and logical_id.startswith(logical_id_prefix):
            return physical_id

    return None
```

## Exception Handling

**Critical: Let exceptions propagate. Do not suppress them.**

Avoid wrapping statements in `try/except` without a very good reason. Users need to see errors to understand and fix problems. Swallowed exceptions make debugging impossible.

### Good Reasons for try/except

- **Retrying** on transient failures (with limit)
- **Adding context** before re-raising
- **Processing batch items** where some may fail (continue processing others)
- **Expected, handleable conditions** (not general Exception)

### Bad Patterns (Don't Do This)

```python
# BAD: Swallows all errors, no visibility
try:
    do_something()
except Exception:
    return None

# BAD: Uses bare Exception, too broad
try:
    do_something()
except:
    return None

# BAD: Silently fails
try:
    result = client.request()
except Exception:
    pass
```

### Good Patterns

```python
# GOOD: Let caller handle errors
def do_something():
    client.make_request()
    return result

# GOOD: Add context before re-raising
def do_something():
    try:
        result = client.make_request()
    except ClientError as e:
        logger.error(f"Request failed: {e}")
        raise

# GOOD: Handle specific expected conditions
def process_items(items):
    results = []
    for item in items:
        try:
            results.append(process(item))
        except ValidationError as e:
            logger.warning(f"Skipping invalid item: {e}")
            continue
    return results
```

### Key Principles

1. **Never use bare `except:`** - always catch specific exceptions
2. **Never catch `Exception`** - catch specific subclasses
3. **Never swallow exceptions** - always either re-raise or handle specifically
4. **Let failures surface** - users need to see errors to fix them
5. **Add context when re-raising** - help users understand what failed and why
