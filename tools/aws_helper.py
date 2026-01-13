#!/usr/bin/env python3
"""
AWS helper for Second Brain project
Reads configuration from env.json and provides boto3 session helpers
"""

import os
import json
import boto3
from typing import Optional, Dict, Any

# Default configuration
DEFAULT_PROFILE = "mtp-cdk"
DEFAULT_REGION = "us-east-2"


def load_env_config() -> Dict[str, Any]:
    """Load configuration from env.json"""
    try:
        with open("env.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        print(f"⚠️  Error parsing env.json: {e}")
        return {}


def get_aws_session() -> boto3.Session:
    """Get AWS session with preferred configuration"""
    # Load from env.json
    env_config = load_env_config()

    # Get profile from env.json, then environment, then default
    profile = env_config.get("AWS_PROFILE", os.getenv("AWS_PROFILE", DEFAULT_PROFILE))

    # Get region from env.json, then environment, then default
    region = env_config.get("AWS_REGION", os.getenv("AWS_REGION", DEFAULT_REGION))

    # Create session with profile
    session = boto3.Session(profile_name=profile)

    # Set region in session environment
    os.environ["AWS_REGION"] = region
    os.environ["AWS_PROFILE"] = profile

    return session


def get_boto3_client(service_name: str, **kwargs):
    """Get boto3 client with preferred configuration"""
    session = get_aws_session()
    region = os.getenv("AWS_REGION", DEFAULT_REGION)

    # Override region if not specified
    if "region_name" not in kwargs:
        kwargs["region_name"] = region

    return session.client(service_name, **kwargs)


def get_boto3_resource(service_name: str, **kwargs):
    """Get boto3 resource with preferred configuration"""
    session = get_aws_session()
    region = os.getenv("AWS_REGION", DEFAULT_REGION)

    # Override region if not specified
    if "region_name" not in kwargs:
        kwargs["region_name"] = region

    return session.resource(service_name, **kwargs)


def print_aws_config():
    """Print current AWS configuration"""
    env_config = load_env_config()
    profile = env_config.get("AWS_PROFILE", os.getenv("AWS_PROFILE", DEFAULT_PROFILE))
    region = env_config.get("AWS_REGION", os.getenv("AWS_REGION", DEFAULT_REGION))

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


# Create module-level session
session = get_aws_session()

# Export common functions
__all__ = [
    "get_aws_session",
    "get_boto3_client",
    "get_boto3_resource",
    "print_aws_config",
    "session",
]

if __name__ == "__main__":
    print_aws_config()
