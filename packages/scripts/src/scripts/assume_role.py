#!/usr/bin/env python3
"""
Assume SecondBrainTriggerRole and print temporary credentials as export statements.

Usage:
    eval "$(python assume_role.py)"
"""

import boto3
from functools import cache


@cache
def get_sts_client():
    return boto3.client("sts")


def get_role_arn() -> str:
    """Get the trigger role ARN from CloudFormation stack."""
    cfn = boto3.client("cloudformation")
    response = cfn.describe_stacks(StackName="SecondBrainStack")
    stacks = response.get("Stacks", [])
    if not stacks:
        raise Exception("SecondBrainStack not found")

    for output in stacks[0].get("Outputs", []):
        if output.get("OutputKey") == "TriggerRoleArn":
            return output.get("OutputValue")

    raise Exception("TriggerRoleArn not found in stack outputs")


def assume_role(role_arn: str | None = None) -> dict:
    """Assume the trigger role and return credentials."""
    sts = get_sts_client()
    if role_arn is None:
        role_arn = get_role_arn()

    response = sts.assume_role(
        RoleArn=role_arn,
        RoleSessionName="DebugSession",
    )

    return response["Credentials"]


def main():
    import sys

    role_arn = None
    if len(sys.argv) > 1:
        role_arn = sys.argv[1]

    credentials = assume_role(role_arn)

    print(f'export AWS_ACCESS_KEY_ID="{credentials["AccessKeyId"]}"')
    print(f'export AWS_SECRET_ACCESS_KEY="{credentials["SecretAccessKey"]}"')
    print(f'export AWS_SESSION_TOKEN="{credentials["SessionToken"]}"')


if __name__ == "__main__":
    main()
