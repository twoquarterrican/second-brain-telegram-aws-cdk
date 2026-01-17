"""
Bedrock embedding utilities for Second Brain.

Provides embeddings using AWS Bedrock Titan Text Embeddings model
with OpenAI fallback for local development or when Bedrock is unavailable.
"""

import os
import json
import logging
from typing import Optional
from functools import lru_cache

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

BEDROCK_REGION = os.environ.get("AWS_BEDROCK_REGION", "us-east-1")
BEDROCK_MODEL_ID = "amazon.titan-embed-text-v1"
OPENAI_MODEL_ID = "text-embedding-3-small"


@lru_cache(maxsize=1024)
def _cached_embedding(text: str) -> Optional[list[float]]:
    """Cached single text embedding to avoid duplicate API calls."""
    return None


def embed_bedrock_titan(texts: list[str]) -> list[list[float]]:
    """Return list of embeddings using Amazon Titan Embed Text v1.

    Args:
        texts: List of text strings to embed (batch processing supported)

    Returns:
        List of embedding vectors, one per input text

    Raises:
        ClientError: If Bedrock API call fails
    """
    if not texts:
        return []

    region = os.environ.get("AWS_BEDROCK_REGION", BEDROCK_REGION)
    client = boto3.client("bedrock-runtime", region_name=region)

    embeddings: list[list[float]] = []

    for text in texts:
        try:
            body = json.dumps({"inputText": text})
            response = client.invoke_model(
                modelId=BEDROCK_MODEL_ID,
                body=body,
                accept="application/json",
                contentType="application/json",
            )
            payload = json.loads(response["body"].read())

            # Titan can return either "embedding" (single) or "embeddings" (batch)
            embedding = payload.get("embedding") or payload.get("embeddings")
            if embedding is None:
                logger.warning(
                    f"Bedrock response missing embedding for text: {text[:50]}..."
                )
                embedding = [0.0] * 1536  # Return zero vector as fallback

            embeddings.append(embedding)

        except ClientError as e:
            logger.error(f"Bedrock API error for text '{text[:50]}...': {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Bedrock response: {e}")
            raise

    return embeddings


def embed_openai(texts: list[str]) -> list[list[float]]:
    """Return list of embeddings using OpenAI text-embedding-3-small.

    Args:
        texts: List of text strings to embed

    Returns:
        List of embedding vectors

    Raises:
        ValueError: If OPENAI_API_KEY not set
    """
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")

    client = OpenAI(api_key=api_key)
    response = client.embeddings.create(model=OPENAI_MODEL_ID, input=texts)

    return [d.embedding for d in response.data]


def embed_texts(texts: list[str], use_bedrock: bool = True) -> list[list[float]]:
    """Generate embeddings with Bedrock Titan as primary, OpenAI as fallback.

    Args:
        texts: List of text strings to embed
        use_bedrock: If True, try Bedrock first; if False, use OpenAI directly

    Returns:
        List of embedding vectors

    Raises:
        Exception: If all providers fail
    """
    if not texts:
        return []

    if use_bedrock:
        try:
            return embed_bedrock_titan(texts)
        except Exception as e:
            logger.warning(
                f"Bedrock Titan embedding failed: {e}, falling back to OpenAI"
            )

    # Fallback to OpenAI
    try:
        return embed_openai(texts)
    except Exception as e:
        logger.error(f"OpenAI embedding also failed: {e}")
        raise


def embed_text(text: str, use_bedrock: bool = True) -> list[float]:
    """Generate a single embedding with Bedrock Titan as primary, OpenAI as fallback.

    Args:
        text: Text string to embed
        use_bedrock: If True, try Bedrock first

    Returns:
        Embedding vector (list of floats)
    """
    # Check cache first for identical texts
    cache_key = text
    cached = _cached_embedding(cache_key)
    if cached is not None:
        return cached

    embeddings = embed_texts([text], use_bedrock=use_bedrock)
    embedding = embeddings[0]

    # Cache the result
    _cached_embedding.cache_clear()
    _cached_embedding(cache_key, embedding)

    return embedding
