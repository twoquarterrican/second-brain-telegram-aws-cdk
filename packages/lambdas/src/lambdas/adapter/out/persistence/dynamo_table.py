from functools import cache
from common.environments import get_env


@cache
def get_dynamodb_resource():
    import boto3

    return boto3.resource("dynamodb")


@cache
def get_second_brain_table():
    table_name = get_env("DDB_TABLE_NAME", default="SecondBrain", required=True)
    return get_dynamodb_resource().Table(table_name)


@cache
def get_s3vectors_client():
    import boto3

    return boto3.client("s3vectors")
