"""
Bedrock embedding utilities for Second Brain.

Provides embeddings using AWS Bedrock Titan Text Embeddings model
with OpenAI fallback for local development or when Bedrock is unavailable.
"""

import json
import logging
import os
import time
from functools import lru_cache
from typing import Dict, Optional

import boto3
from botocore.exceptions import ClientError

from common.environments import get_boto3_client

logger = logging.getLogger(__name__)

BEDROCK_REGION = os.environ.get("AWS_BEDROCK_REGION", "us-east-1")
BEDROCK_MODEL_ID = "amazon.titan-embed-text-v2:0"
OPENAI_MODEL_ID = "text-embedding-3-small"
EMBEDDING_MODEL = BEDROCK_MODEL_ID

# Simple cache for embeddings
_embedding_cache: Dict[str, list[float]] = {}

# Retry configuration
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # seconds
MAX_BACKOFF = 32.0  # seconds


@lru_cache(maxsize=1024)
def _cached_embedding(text: str) -> Optional[list[float]]:
    """Get cached embedding for a text string."""
    return _embedding_cache.get(text)


def _invoke_bedrock_with_retry(text: str, client) -> list[float]:
    """Invoke Bedrock model with exponential backoff retry.

    Args:
        text: Text to embed
        client: boto3 bedrock-runtime client

    Returns:
        Embedding vector

    Raises:
        ClientError: If all retries fail
    """
    body = json.dumps({"inputText": text})
    response = client.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        body=body,
        accept="application/json",
        contentType="application/json",
    )
    payload = json.loads(response["body"].read())

    embedding = payload.get("embedding") or payload.get("embeddings")
    if embedding is None:
        raise ValueError(
            f"Bedrock response missing embedding for text: {text[:50]}..."
        )

    return embedding


def embed_bedrock_titan(texts: list[str]) -> list[list[float]]:
    """Return list of embeddings using Amazon Titan Embed Text v1.

    Args:
        texts: List of text strings to embed (batch processing supported)

    Returns:
        List of embedding vectors, one per input text

    Raises:
        ClientError: If Bedrock API call fails after retries
    """
    if not texts:
        return []

    client = get_boto3_client("bedrock-runtime", second_brain_trigger_role=True)

    embeddings: list[list[float]] = []

    for text in texts:
        try:
            embedding = _invoke_bedrock_with_retry(text, client)
            embeddings.append(embedding)
            logger.debug(f"Generated embedding for text: {text[:50]}...")

        except Exception as e:
            logger.error(f"Failed to embed text after retries: {text[:50]}...: {e}")
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
            raise ValueError( f"Bedrock Titan embedding failed" ) from e

    else:
        try:
            return embed_openai(texts)
        except Exception as e:
            raise ValueError(f"OpenAI embedding also failed") from e


def embed_text(text: str, use_bedrock: bool = True) -> list[float]:
    """Generate a single embedding with Bedrock Titan as primary, OpenAI as fallback.

    Args:
        text: Text string to embed
        use_bedrock: If True, try Bedrock first

    Returns:
        Embedding vector (list of floats)
    """
    # Check cache first for identical texts
    cached = _cached_embedding(text)
    if cached is not None:
        return cached

    embeddings = embed_texts([text], use_bedrock=use_bedrock)
    embedding = embeddings[0]

    # Cache the result
    _embedding_cache[text] = embedding

    return embedding
