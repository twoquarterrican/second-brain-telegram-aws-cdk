"""
Ports and Adapters Architecture - Output Ports

This package contains output port interfaces (contracts) that define how the application
interacts with external services and infrastructure. These are abstract interfaces that
represent what the application needs from the outside world.

Following hexagonal architecture principles:
- Ports define "what" the application needs (interfaces)
- Adapters implement "how" those needs are fulfilled (concrete implementations)
- The application depends only on ports, not on adapters
- Adapters depend on both ports and external systems

This allows for:
- Easy testing with mock adapters
- Pluggable implementations (different AI providers)
- Clean separation of concerns
- Framework independence
"""

from abc import ABC, abstractmethod
from typing import Any, List


class AiModelApi(ABC):
    """
    Output port for AI model interactions.

    This abstract interface defines the contract for AI model operations
    that the application requires. Concrete implementations (adapters) will
    provide the actual integration with specific AI providers.
    """

    @abstractmethod
    def invoke_model(self, prompt: str, **kwargs: Any) -> str:
        """
        Invoke an AI model with a text prompt.

        Args:
            prompt: The text prompt to send to the AI model
            **kwargs: Additional parameters specific to the model provider

        Returns:
            The model's text response

        Raises:
            Exception: If the model invocation fails
        """
        pass

    @abstractmethod
    def compute_embedding(self, text: str, **kwargs: Any) -> List[float]:
        """
        Compute vector embeddings for the given text.

        Args:
            text: The text to compute embeddings for
            **kwargs: Additional parameters specific to the embedding model

        Returns:
            List of floats representing the text embedding vector

        Raises:
            Exception: If embedding computation fails
        """
        pass
