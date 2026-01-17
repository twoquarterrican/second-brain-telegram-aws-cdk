"""Embedding-based item matching for the processor Lambda.

Uses vector embeddings to find similar items and update existing items
instead of creating duplicates when similarity exceeds threshold.
"""

import math
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Dict, Any, List
import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ.get("DDB_TABLE_NAME", "SecondBrain"))


def serialize_embedding(embedding: list[float]) -> list:
    """Convert embedding floats to DynamoDB-compatible format."""
    return [Decimal(str(x)) for x in embedding]


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not vec_a or not vec_b:
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a * norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def embed_text(text: str) -> list[float]:
    """Generate embedding for text using Bedrock Titan or OpenAI fallback."""
    if not text:
        return [0.0] * 1536

    bedrock_region = os.environ.get("BEDROCK_REGION")

    if bedrock_region:
        try:
            return _embed_bedrock(text, bedrock_region)
        except Exception as e:
            import logging

            logging.warning(f"Bedrock embedding failed: {e}, falling back to OpenAI")

    return _embed_openai(text)


def _embed_bedrock(text: str, region: str) -> list[float]:
    """Generate embedding using Bedrock Titan."""
    import json
    import botocore

    client = boto3.client("bedrock-runtime", region_name=region)
    body = json.dumps({"inputText": text})
    response = client.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        body=body,
        accept="application/json",
        contentType="application/json",
    )
    payload = json.loads(response["body"].read())
    embedding = payload.get("embedding") or payload.get("embeddings")
    if not embedding:
        raise ValueError("Bedrock response missing embedding")
    return embedding


def _embed_openai(text: str) -> list[float]:
    """Generate embedding using OpenAI."""
    import openai

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")

    client = openai.OpenAI(api_key=api_key)
    resp = client.embeddings.create(model="text-embedding-3-small", input=text)
    return resp.data[0].embedding


def list_items_with_embeddings(category: str) -> List[Dict[str, Any]]:
    """List all items in a category that have embeddings."""
    response = table.query(
        KeyConditionExpression=Key("PK").eq(f"CATEGORY#{category}"),
    )
    items = response.get("Items", [])
    return [item for item in items if item.get("embedding")]


def find_similar_item(
    category: str, message_embedding: list[float], threshold: float = 0.85
) -> Optional[Dict[str, Any]]:
    """Find the most similar item in category with embedding above threshold."""
    items = list_items_with_embeddings(category)

    best_score = 0.0
    best_item = None

    for item in items:
        embedding = item.get("embedding")
        if not embedding:
            continue
        score = cosine_similarity(message_embedding, list(embedding))
        if score > best_score:
            best_score = score
            best_item = item

    if best_item and best_score >= threshold:
        return best_item

    return None


def update_item(
    pk: str, sk: str, item_data: Dict[str, Any], original_text: str
) -> None:
    """Update an existing item with new data."""
    timestamp = datetime.now(timezone.utc).isoformat()
    table.update_item(
        Key={"PK": pk, "SK": sk},
        UpdateExpression="SET #status = :status, #next_action = :next_action, #notes = :notes, updated_at = :updated_at, original_text = :original_text",
        ExpressionAttributeNames={
            "#status": "status",
            "#next_action": "next_action",
            "#notes": "notes",
        },
        ExpressionAttributeValues={
            ":status": item_data.get("status", "open"),
            ":next_action": item_data.get("next_action"),
            ":notes": item_data.get("notes"),
            ":updated_at": timestamp,
            ":original_text": original_text,
        },
    )


def create_item(
    category: str, item_data: Dict[str, Any], embedding: list[float]
) -> str:
    """Create a new item with embedding."""
    from datetime import datetime, timezone
    import uuid

    timestamp = datetime.now(timezone.utc).isoformat()
    uuid_part = str(uuid.uuid4())[:8]
    sk = f"{timestamp}#{category}#{hash(item_data.get('original_text', '')) % 10000}"

    item = {
        "PK": f"CATEGORY#{category}",
        "SK": sk,
        "created_at": timestamp,
        "status": item_data.get("status", "open"),
        "name": item_data.get("name"),
        "next_action": item_data.get("next_action"),
        "notes": item_data.get("notes"),
        "original_text": item_data["original_text"],
        "confidence": item_data.get("confidence", 0),
        "category": category,
        "embedding": serialize_embedding(embedding),
    }

    table.put_item(Item=item)
    return sk


def save_with_embedding_matching(
    item_data: Dict[str, Any], similarity_threshold: float = 0.85
) -> Dict[str, Any]:
    """Save item using embedding similarity matching.

    Returns dict with:
        - action: "created" or "updated"
        - sk: the item's sort key
        - similarity: the similarity score
        - category: the item category
    """
    category = item_data["category"]
    original_text = item_data["original_text"]

    if not item_data.get("name"):
        sk = create_item(category, item_data, [0.0] * 1536)
        return {"action": "created", "sk": sk, "similarity": 0.0, "category": category}

    embedding = embed_text(item_data["name"])

    similar_item = find_similar_item(
        category, embedding, threshold=similarity_threshold
    )

    if similar_item:
        update_item(similar_item["PK"], similar_item["SK"], item_data, original_text)
        return {
            "action": "updated",
            "sk": similar_item["SK"],
            "similarity": cosine_similarity(embedding, list(similar_item["embedding"])),
            "category": category,
        }

    sk = create_item(category, item_data, embedding)
    return {"action": "created", "sk": sk, "similarity": 0.0, "category": category}


def derive_status(action: str) -> str:
    """Derive status from action keywords."""
    mapping = {
        "start": "in_progress",
        "started": "in_progress",
        "done": "completed",
        "complete": "completed",
    }
    return mapping.get(action.lower(), "open")


def save_to_dynamodb_with_embedding(
    item_data: Dict[str, Any],
    action: str = "open",
    similarity_threshold: float = 0.85,
) -> Dict[str, Any]:
    """Save item using embedding similarity matching with action-based status.

    Returns dict with action, sk, similarity, category, and status.
    """
    item_data["status"] = derive_status(action)
    result = save_with_embedding_matching(item_data, similarity_threshold)
    result["status"] = item_data["status"]
    return result
