import os
import sys
import uuid
from moto import mock_aws
import boto3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def serialize_embedding(embedding):
    """Convert embedding list to DynamoDB serializable format."""
    return {"L": [{"N": str(x)} for x in embedding]}


@mock_aws
def test_link_task_existing_match(monkeypatch):
    os.environ["OPENAI_API_KEY"] = "test_api_key"
    os.environ["SECOND_BRAIN_TABLE_NAME"] = "SecondBrainTable"

    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    mock_table = dynamodb.create_table(
        TableName="SecondBrainTable",
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

    user_id = "testuser"
    task_id = str(uuid.uuid4())
    embedding1 = [0.1, 0.2, 0.3]
    mock_table.put_item(
        Item={
            "PK": f"USER#{user_id}",
            "SK": f"TASK#{task_id}",
            "taskId": task_id,
            "entityType": "Task",
            "name": "write report draft",
            "status": "open",
            "embedding": serialize_embedding(embedding1),
        }
    )

    monkeypatch.setattr(
        "task_linker.linker.embed_text",
        lambda text: [0.1, 0.21, 0.29],
    )
    monkeypatch.setattr("task_linker.linker.cosine_similarity", lambda a, b: 0.9)
    monkeypatch.setattr("task_linker.task_store.table", mock_table)

    from task_linker.linker import link_task

    result = link_task(user_id, "finish the report", "done")

    assert "matched_task" in result
    assert result["confidence"] > 0.85


@mock_aws
def test_link_task_creates_new(monkeypatch):
    os.environ["OPENAI_API_KEY"] = "test_api_key"
    os.environ["SECOND_BRAIN_TABLE_NAME"] = "SecondBrainTable"

    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    mock_table = dynamodb.create_table(
        TableName="SecondBrainTable",
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

    monkeypatch.setattr(
        "task_linker.linker.embed_text",
        lambda text: [0.4, 0.4, 0.4],
    )
    monkeypatch.setattr("task_linker.linker.cosine_similarity", lambda a, b: 0.5)
    monkeypatch.setattr("task_linker.task_store.table", mock_table)

    from task_linker.linker import link_task

    result = link_task("testuser", "start cleaning project", "start")

    assert "created_task" in result
    assert 0 <= result["confidence"] <= 1


@mock_aws
def test_bedrock_embedding_fallback(monkeypatch):
    """Test that Bedrock embeddings work with OpenAI fallback."""
    os.environ["OPENAI_API_KEY"] = "test_api_key"

    import task_linker.embeddings as emb_module
    from common import bedrock_embeddings

    assert hasattr(emb_module, "embed_text")
    assert callable(emb_module.embed_text)

    def mock_bedrock_embed_text(text, use_bedrock=True):
        raise Exception("Bedrock unavailable")

    def mock_openai_embedding(text):
        return [0.1, 0.2, 0.3]

    bedrock_embeddings._USE_BEDROCK = True
    monkeypatch.setattr(
        "common.bedrock_embeddings.embed_text",
        mock_bedrock_embed_text,
    )
    monkeypatch.setattr(
        "task_linker.embeddings.embed_text",
        mock_openai_embedding,
    )

    result = emb_module.embed_text("test text")
    assert result == [0.1, 0.2, 0.3]

    bedrock_embeddings._USE_BEDROCK = None
    bedrock_embeddings._cached_embedding.cache_clear()
