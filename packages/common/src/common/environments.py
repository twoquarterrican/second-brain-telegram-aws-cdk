#!/usr/bin/env python3
"""
AWS helper for Second Brain project
Reads configuration from env.json and provides boto3 session helpers
"""

import os
import json
import boto3
from typing import Optional
from functools import cache
from pathlib import Path
from dotenv import load_dotenv


load_dotenv(dotenv_path=(Path(__file__).parents[1] / "env.local"))


@cache
def project_root() -> Path:
    """Load configuration from env.json and return project root"""
    path = Path(__file__).parent
    while not (path / ".git").exists():
        path = path.parent
    return path


def bedrock_iam_policy() -> str:
    """IAM policy for Bedrock access"""
    return """{
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "bedrock:ListFoundationModels"
                ],
                "Resource": "*"
            }
        ]
    }"""


@cache
def cdk_dir() -> Path:
    """Get the CDK package directory"""
    return project_root() / "packages" / "cdk"


@cache
def cdk_src_dir() -> Path:
    """Get the CDK package directory"""
    return cdk_dir() / "src"


@cache
def scripts_dir() -> Path:
    """Get the scripts package directory"""
    return project_root() / "packages" / "scripts"


@cache
def common_dir() -> Path:
    """Get the common package directory"""
    return project_root() / "packages" / "common"


@cache
def lambdas_dir() -> Path:
    """Get the lambdas package directory"""
    return project_root() / "packages" / "lambdas"


@cache
def lambdas_src_dir() -> Path:
    """Get the lambdas package directory"""
    return lambdas_dir() / "src"


@cache
def layer_dir() -> Path:
    """Get the Lambda layer output directory"""
    return cdk_dir() / "layer"


@cache
def get_aws_session() -> boto3.Session:
    """Get AWS session with preferred configuration"""

    # Get profile from env.json, then environment, then default
    profile = os.getenv("AWS_PROFILE")

    # Get region from env.json, then environment, then default
    region = os.getenv("AWS_REGION")

    return boto3.session.Session(profile_name=profile, region_name=region)


@cache
def get_boto3_client(service_name: str, **kwargs):
    """Get boto3 client with preferred configuration"""
    session = get_aws_session()
    return session.client(service_name, **kwargs)


@cache
def get_boto3_resource(service_name: str, **kwargs):
    """Get boto3 resource with preferred configuration"""
    session = get_aws_session()
    return session.resource(service_name, **kwargs)


@cache
def get_lambda_client(region: Optional[str] = None):
    """Get AWS Lambda client with configured session."""
    session = get_aws_session()
    region = region or os.getenv("AWS_REGION", "us-east-1")
    return session.client("lambda", region_name=region)


@cache
def get_cfn_client(region: str):
    """Get CloudFormation client."""
    session = get_aws_session()
    return session.client("cloudformation", region_name=region)


@cache
def get_sts_client(region: str = "us-east-1"):
    """Get STS client."""
    session = get_aws_session()
    return session.client("sts", region_name=region)


def get_stack_output(stack_name: str, output_key: str) -> Optional[str]:
    """Get a specific output from CloudFormation stack."""
    region = os.getenv("AWS_REGION", "us-east-1")
    cfn = get_cfn_client(region)
    response = cfn.describe_stacks(StackName=stack_name)
    stacks = response.get("Stacks", [])
    if not stacks:
        return None

    outputs = stacks[0].get("Outputs", [])
    for output in outputs:
        if output.get("OutputKey") == output_key:
            return output.get("OutputValue")
    return None


def get_function_name() -> Optional[str]:
    """Get the digest Lambda function name from CDK stack outputs."""
    return get_stack_output("SecondBrainStack", "DigestLambdaFunctionName")


def get_trigger_role_arn() -> Optional[str]:
    """Get the trigger role ARN from CDK stack outputs."""
    return get_stack_output("SecondBrainStack", "TriggerRoleArn")


def list_stack_resources(stack_name: str):
    """Generator that yields all resources in a CloudFormation stack.

    Uses paginator to handle stacks with more than 100 resources.
    Yields dicts with 'LogicalResourceId', 'ResourceType', and 'PhysicalResourceId'.
    """
    region = os.getenv("AWS_REGION", "us-east-1")
    cfn = get_cfn_client(region)

    paginator = cfn.get_paginator("list_stack_resources")
    page_iterator = paginator.paginate(StackName=stack_name)

    for page in page_iterator:
        for resource in page.get("StackResourceSummaries", []):
            yield resource


def find_lambda_function(logical_id_prefix: str) -> Optional[str]:
    """Find a Lambda function in the stack by logical resource ID prefix.

    Args:
        logical_id_prefix: Prefix to match (e.g., 'DigestLambda')

    Returns:
        Physical resource ID (function name) or None if not found
    """
    for resource in list_stack_resources("SecondBrainStack"):
        logical_id = resource.get("LogicalResourceId", "")
        resource_type = resource.get("ResourceType", "")
        physical_id = resource.get("PhysicalResourceId", "")

        if resource_type == "AWS::Lambda::Function" and logical_id.startswith(
            logical_id_prefix
        ):
            return physical_id

    return None


def assume_second_brain_trigger_role(
    session_name: str = "SecondBrainTrigger"
) -> boto3.Session:
    """Assume a role and return a session with temporary credentials."""

    role_arn = get_trigger_role_arn()
    if not role_arn:
        raise ValueError(
            "❌ Trigger role not found. Deploy CDK with TRIGGER_ROLE_TRUST_ACCOUNT set, or use --role-arn",
        )

    # Assume role if provided
    click.echo(f"🔐 Assuming role: {role_arn}")
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


def get_telegram_bot_token() -> str:
    """Get Telegram bot token from environment.

    Returns:
        The bot token string.

    Raises:
        ValueError: If TELEGRAM_BOT_TOKEN is not set.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set")
    return token


if __name__ == "__main__":
    print_aws_config()
