import uuid
import os
from datetime import datetime, timezone
from decimal import Decimal
import boto3
from boto3.dynamodb.conditions import Key, Attr

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["SECOND_BRAIN_TABLE_NAME"])

PK_PREFIX_USER = "USER#"
SK_PREFIX_TASK = "TASK#"


def serialize_embedding(embedding: list[float]) -> list:
    """Convert embedding floats to DynamoDB-compatible format."""
    return [Decimal(str(x)) for x in embedding]


def make_task_keys(user_id: str, task_id: str):
    return {"PK": f"{PK_PREFIX_USER}{user_id}", "SK": f"{SK_PREFIX_TASK}{task_id}"}


def list_open_tasks(user_id: str):
    """Return all non-completed tasks for a given user."""
    response = table.query(
        KeyConditionExpression=Key("PK").eq(f"{PK_PREFIX_USER}{user_id}")
        & Key("SK").begins_with(SK_PREFIX_TASK),
        FilterExpression=Attr("status").ne("completed"),
    )
    return response.get("Items", [])


def update_task_status(user_id: str, task_id: str, new_status: str):
    keys = make_task_keys(user_id, task_id)
    table.update_item(
        Key=keys,
        UpdateExpression="SET #s = :s",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": new_status},
    )


def create_task(user_id: str, name: str, status: str, embedding: list[float]):
    task_id = str(uuid.uuid4())
    keys = make_task_keys(user_id, task_id)
    item = {
        **keys,
        "taskId": task_id,
        "entityType": "Task",
        "name": name,
        "status": status,
        "embedding": serialize_embedding(embedding),
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    table.put_item(Item=item)
    return task_id
