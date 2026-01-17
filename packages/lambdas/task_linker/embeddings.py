"""
Embedding utilities for task linking.

Uses AWS Bedrock Titan Text Embeddings as primary provider,
with OpenAI text-embedding-3-small as fallback.
"""

import os
import logging

logger = logging.getLogger(__name__)

_USE_BEDROCK = None  # Lazy evaluation flag


def _should_use_bedrock() -> bool:
    """Check if Bedrock should be used (lazy evaluation)."""
    global _USE_BEDROCK
    if _USE_BEDROCK is not None:
        return _USE_BEDROCK

    # Check if Bedrock region is configured
    bedrock_region = os.environ.get("AWS_BEDROCK_REGION")
    _USE_BEDROCK = bedrock_region is not None
    return _USE_BEDROCK


def embed_text(text: str) -> list[float]:
    """Generate a vector embedding for text.

    Uses Bedrock Titan Text Embeddings by default (if AWS_BEDROCK_REGION is set),
    with OpenAI text-embedding-3-small as fallback.

    Args:
        text: Text string to embed

    Returns:
        Embedding vector (list of 1536 floats)
    """
    if not text:
        return [0.0] * 1536

    # Try Bedrock first if configured
    if _should_use_bedrock():
        try:
            from common.bedrock_embeddings import embed_text as bedrock_embed

            return bedrock_embed(text, use_bedrock=True)
        except Exception as e:
            raise ValueError(f"Bedrock embedding failed: {e}") from e

    # Fallback to OpenAI
    try:
        from openai import OpenAI

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")

        client = OpenAI(api_key=api_key)
        resp = client.embeddings.create(model="text-embedding-3-small", input=text)
        return resp.data[0].embedding

    except Exception as e:
        logger.error(f"OpenAI embedding also failed: {e}")
        raise ValueError(f"Failed to generate embedding: {e}") from e
