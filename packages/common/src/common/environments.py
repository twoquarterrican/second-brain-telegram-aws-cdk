#!/usr/bin/env python3
"""
AWS helper for Second Brain project
Reads configuration from env.json and provides boto3 session helpers
"""

import os
import json
import boto3
from functools import cache
from pathlib import Path

ENV_JSON_PATH: Path = Path(__file__).parents[1] / "env.json"


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
def load_env_config():
    """Load configuration from env.json"""
    try:
        with open(ENV_JSON_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        raise ValueError(
            f"Missing {ENV_JSON_PATH.as_posix()}. This file is required for AWS operations. See README for more info."
        )


@cache
def get_aws_session() -> boto3.Session:
    """Get AWS session with preferred configuration"""
    # Load from env.json
    env_config = load_env_config()

    # Get profile from env.json, then environment, then default
    profile = env_config.get("AWS_PROFILE", os.getenv("AWS_PROFILE"))

    # Get region from env.json, then environment, then default
    region = env_config.get("AWS_REGION", os.getenv("AWS_REGION"))

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


def print_aws_config():
    """Print current AWS configuration"""
    env_config = load_env_config()
    profile = env_config.get("AWS_PROFILE", os.getenv("AWS_PROFILE", "default"))
    region = env_config.get("AWS_REGION", os.getenv("AWS_REGION", "us-east-1"))

    print("🔧 AWS Configuration:")
    print(f"  Profile: {profile}")
    print(f"  Region: {region}")

    # Show env.json status
    if env_config:
        print("  Config: ✅ Loaded from env.json")
    else:
        print("  Config: ⚠️  No env.json found (using defaults)")

    print("\n💡 Usage in Python:")
    print("  from aws_helper import get_boto3_client")
    print("  client = get_boto3_client('lambda')")
    print(f"  # Uses profile: {profile}, region: {region}")


if __name__ == "__main__":
    print_aws_config()
