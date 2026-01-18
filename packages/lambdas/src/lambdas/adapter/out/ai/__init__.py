"""
Ports and Adapters Architecture - Output Adapters for AI Services

This package contains output adapters that implement the AiModelApi port interface.
Each adapter provides concrete implementations for interacting with specific AI providers:

- AnthropicModelApi: Integration with Anthropic's Claude models
- OpenaiModelApi: Integration with OpenAI's GPT models
- BedrockModelApi: Integration with AWS Bedrock models

These adapters translate between the application's domain language and the external
AI service APIs. They handle:
- Authentication and connection management
- Request/response format conversion
- Error handling and retries
- Provider-specific parameter mapping

The application depends only on the AiModelApi interface, making it easy to:
- Switch between AI providers
- Add new providers
- Mock AI services for testing
- Implement circuit breakers and fallbacks
"""

import anthropic
import json
from openai import OpenAI
import boto3
from typing import Any, List
from lambdas.app.port.out import AiModelApi
from common.environments import get_env


class AnthropicModelApi(AiModelApi):
    """
    Adapter for Anthropic's Claude AI models.

    Provides integration with Anthropic's API for text generation and embeddings.
    Uses the official Anthropic Python SDK.
    """

    def __init__(self):
        self.api_key = get_env("ANTHROPIC_API_KEY")
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = "claude-3-sonnet-20240229"  # Default model

    def invoke_model(self, prompt: str, **kwargs: Any) -> str:
        """Invoke Claude model for text generation."""
        model = kwargs.get("model", self.model)
        max_tokens = kwargs.get("max_tokens", 1000)

        try:
            response = self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            raise Exception(f"Anthropic API error: {str(e)}")

    def compute_embedding(self, text: str, **kwargs: Any) -> List[float]:
        """Compute embeddings using Anthropic's embedding model."""
        # Note: Anthropic doesn't have a dedicated embedding API yet
        # This is a placeholder - would need to use Voyage AI or similar
        raise NotImplementedError("Anthropic embeddings not yet implemented")


class OpenaiModelApi(AiModelApi):
    """
    Adapter for OpenAI's GPT models.

    Provides integration with OpenAI's API for text generation and embeddings.
    Uses the official OpenAI Python SDK.
    """

    def __init__(self):
        self.api_key = get_env("OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-4"  # Default model
        self.embedding_model = "text-embedding-ada-002"  # Default embedding model

    def invoke_model(self, prompt: str, **kwargs: Any) -> str:
        """Invoke GPT model for text generation."""
        model = kwargs.get("model", self.model)
        max_tokens = kwargs.get("max_tokens", 1000)
        temperature = kwargs.get("temperature", 0.7)

        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")

    def compute_embedding(self, text: str, **kwargs: Any) -> List[float]:
        """Compute embeddings using OpenAI's embedding API."""
        model = kwargs.get("model", self.embedding_model)

        try:
            response = self.client.embeddings.create(input=text, model=model)
            return response.data[0].embedding
        except Exception as e:
            raise Exception(f"OpenAI embedding API error: {str(e)}")


class BedrockModelApi(AiModelApi):
    """
    Adapter for AWS Bedrock AI models.

    Provides integration with AWS Bedrock service for various AI models
    including Anthropic Claude, AI21 Labs, Cohere, etc.
    """

    def __init__(self):
        self.client = boto3.client("bedrock-runtime")
        self.model_id = (
            "anthropic.claude-3-sonnet-20240229-v1:0"  # Default Claude model
        )
        self.embedding_model_id = (
            "amazon.titan-embed-text-v2:0"  # Default embedding model
        )

    def invoke_model(self, prompt: str, **kwargs: Any) -> str:
        """Invoke Bedrock model for text generation."""
        model_id = kwargs.get("model_id", self.model_id)
        max_tokens = kwargs.get("max_tokens", 1000)

        # Format request for Claude via Bedrock
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }

        try:
            response = self.client.invoke_model(
                modelId=model_id,
                body=json.dumps(request_body),
                contentType="application/json",
            )

            response_body = json.loads(response["body"].read())
            return response_body["content"][0]["text"]
        except Exception as e:
            raise Exception(f"AWS Bedrock API error: {str(e)}")

    def compute_embedding(self, text: str, **kwargs: Any) -> List[float]:
        """Compute embeddings using Bedrock's embedding models."""
        model_id = kwargs.get("model_id", self.embedding_model_id)

        request_body = {"inputText": text}

        try:
            response = self.client.invoke_model(
                modelId=model_id,
                body=json.dumps(request_body),
                contentType="application/json",
            )

            response_body = json.loads(response["body"].read())
            return response_body["embedding"]
        except Exception as e:
            raise Exception(f"AWS Bedrock embedding API error: {str(e)}")


class CompositeAiModelApi(AiModelApi):
    """
    Composite adapter that delegates to two AiModelApi instances.

    Delegates specific operations to specific APIs:
    - invoke_model: Uses the text generation API
    - compute_embedding: Uses the embedding API

    This allows using different providers for different AI operations,
    optimizing for the best model for each use case.
    """

    def __init__(self, text_api: AiModelApi, embedding_api: AiModelApi):
        """
        Initialize composite API with separate providers for different operations.

        Args:
            text_api: The AI API to use for text generation (invoke_model)
            embedding_api: The AI API to use for embeddings (compute_embedding)
        """
        self.text_api = text_api
        self.embedding_api = embedding_api

    def invoke_model(self, prompt: str, **kwargs: Any) -> str:
        """
        Invoke AI model for text generation using the text API.
        """
        return self.text_api.invoke_model(prompt, **kwargs)

    def compute_embedding(self, text: str, **kwargs: Any) -> List[float]:
        """
        Compute embeddings using the embedding API.
        """
        return self.embedding_api.compute_embedding(text, **kwargs)
