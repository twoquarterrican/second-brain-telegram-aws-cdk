"""Embedding-based item matching for the processor Lambda.

Uses S3 Vectors for similarity search to find similar items and update
existing items instead of creating duplicates when similarity exceeds threshold.
"""

import math
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Dict, Any
import boto3

from common.environments import get_vector_bucket_name, get_vector_index_name, get_env
from lambdas.adapter.out.persistence.dynamo_table import (
    get_second_brain_table,
    get_s3vectors_client,
)


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

    bedrock_region = get_env("BEDROCK_REGION", required=True)

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


def _make_vector_id(pk: str, sk: str) -> str:
    """Create a unique vector ID from DynamoDB keys."""
    return f"{pk}#{sk}".replace("/", "_")


def index_vector(
    pk: str, sk: str, embedding: list[float], metadata: Dict[str, Any]
) -> None:
    """Index a vector in S3 Vectors."""
    vector_id = _make_vector_id(pk, sk)

    get_s3vectors_client().batch_put_vector(
        VectorIndexName=get_vector_index_name(),
        Vectors=[
            {
                "Id": vector_id,
                "Vector": embedding,
                "Metadata": {
                    "pk": pk,
                    "sk": sk,
                    "category": metadata.get("category", ""),
                    "name": metadata.get("name", "") or "",
                    "status": metadata.get("status", "open"),
                    **metadata,
                },
            }
        ],
    )


def delete_vector(pk: str, sk: str) -> None:
    """Delete a vector from S3 Vectors."""
    vector_id = _make_vector_id(pk, sk)

    get_s3vectors_client().batch_delete_vector(
        VectorIndexName=get_vector_index_name(),
        VectorIds=[vector_id],
    )


def find_similar_item(
    category: str, message_embedding: list[float], threshold: float = 0.85
) -> Optional[Dict[str, Any]]:
    """Find the most similar item in category using S3 Vectors similarity search.

    Args:
        category: The category to search within
        message_embedding: The embedding vector to search with
        threshold: Minimum similarity score (default 0.85)

    Returns:
        The most similar item dict, or None if no match above threshold

    Raises:
        ClientError: If S3 Vectors search fails
    """
    response = get_s3vectors_client().query_vectors(
        vectorBucketName=get_vector_bucket_name(),
        indexName=get_vector_index_name(),
        topK=5,
        queryVector={
            "float32": message_embedding,
        },
        filter={"key": "category", "value": category, "comparisonOperator": "EQUALS"},
        returnDistance=True,
        returnMetadata=True,
    )

    hits = response.get("hits", [])
    if not hits:
        return None

    best_hit = hits[0]
    score = best_hit.get("score", 0.0)

    if score >= threshold:
        metadata = best_hit.get("metadata", {})
        pk = metadata.get("pk")
        sk = metadata.get("sk")

        if pk and sk:
            response = get_second_brain_table().get_item(Key={"PK": pk, "SK": sk})
            item = response.get("Item")
            if item:
                return item

    return None


def update_item(
    pk: str, sk: str, item_data: Dict[str, Any], original_text: str
) -> None:
    """Update an existing item with new data."""
    timestamp = datetime.now(timezone.utc).isoformat()
    get_second_brain_table().update_item(
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

    timestamp = datetime.now(timezone.utc).isoformat()
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

    get_second_brain_table().put_item(Item=item)

    index_vector(
        pk=str(item["PK"]),
        sk=sk,
        embedding=embedding,
        metadata={
            "category": category,
            "name": item_data.get("name") or "",
            "status": item_data.get("status", "open"),
        },
    )

    return sk


def save_with_embedding_matching(
    item_data: Dict[str, Any], similarity_threshold: float = 0.85
) -> Dict[str, Any]:
    """Save item using S3 Vectors similarity matching.

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
        embedding_list = [float(e) for e in similar_item.get("embedding", [])]
        similarity = (
            cosine_similarity(embedding, embedding_list) if embedding_list else 0.0
        )
        return {
            "action": "updated",
            "sk": similar_item["SK"],
            "similarity": similarity,
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
    """Save item using S3 Vectors similarity matching with action-based status.

    Returns dict with action, sk, similarity, category, and status.
    """
    item_data["status"] = derive_status(action)
    result = save_with_embedding_matching(item_data, similarity_threshold)
    result["status"] = item_data["status"]
    return result
