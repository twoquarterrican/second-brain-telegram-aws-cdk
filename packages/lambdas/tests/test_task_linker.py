import os
import sys
import uuid
import pytest
from moto import mock_aws
import boto3

os.environ["OPENAI_API_KEY"] = "test_api_key"
os.environ["SECOND_BRAIN_TABLE_NAME"] = "SecondBrainTable"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from task_linker.linker import link_task
from task_linker.task_store import make_task_keys


@mock_aws
def test_link_task_existing_match(monkeypatch):
    # Setup table
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table_name = "SecondBrainTable"
    table = dynamodb.create_table(
        TableName=table_name,
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    os.environ["SECOND_BRAIN_TABLE_NAME"] = table_name

    user_id = "testuser"
    task_id = str(uuid.uuid4())
    embedding1 = [0.1, 0.2, 0.3]
    table.put_item(
        Item={
            "PK": f"USER#{user_id}",
            "SK": f"TASK#{task_id}",
            "taskId": task_id,
            "entityType": "Task",
            "name": "write report draft",
            "status": "open",
            "embedding": embedding1,
        }
    )

    # Monkeypatch embeddings + similarity for determinism
    monkeypatch.setattr(
        "task_linker.embeddings.embed_text",
        lambda text: [0.1, 0.21, 0.29],
    )
    monkeypatch.setattr(
        "task_linker.similarity.cosine_similarity", lambda a, b: 0.9
    )  # force match

    result = link_task(user_id, "finish the report", "done")

    assert "matched_task" in result
    assert result["confidence"] > 0.85


@mock_aws
def test_link_task_creates_new(monkeypatch):
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table_name = "SecondBrainTable"
    table = dynamodb.create_table(
        TableName=table_name,
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    os.environ["SECOND_BRAIN_TABLE_NAME"] = table_name

    monkeypatch.setattr(
        "task_linker.embeddings.embed_text",
        lambda text: [0.4, 0.4, 0.4],
    )
    monkeypatch.setattr("task_linker.similarity.cosine_similarity", lambda a, b: 0.5)

    result = link_task("testuser", "start cleaning project", "start")

    assert "created_task" in result
    assert 0 <= result["confidence"] <= 1
