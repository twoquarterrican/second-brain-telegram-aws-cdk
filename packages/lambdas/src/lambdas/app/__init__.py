"""
Application layer for dependency injection and configuration.

This package contains the application composition root that wires up
all dependencies according to the ports and adapters architecture.
The Application class provides configured AiModelApi instances and
event repositories to the domain logic.

Following hexagonal architecture principles:
- Application layer depends on ports (interfaces)
- Dependencies are injected at composition root
- No business logic - only dependency wiring
- Easy to test and configure different environments
"""

from lambdas.adapter.out.ai import (
    CompositeAiModelApi,
    AnthropicModelApi,
    BedrockModelApi,
)
from lambdas.app.port.out import AiModelApi
from lambdas.events import EventRepository
from common.environments import get_env


class Application:
    """
    Application composition root for dependency injection.

    Provides configured AiModelApi and EventRepository instances to domain logic.
    Acts as the single point where all external dependencies are wired.
    """

    def get_ai_model_api(self) -> AiModelApi:
        """
        Get the configured AI model API instance.

        Returns:
            Configured AiModelApi instance ready for use by domain logic.

        Note:
            Currently stubbed - will be implemented when wiring up adapters.
        """
        # TODO: Wire up actual AiModelApi implementation based on configuration
        # This could be:
        # - Single provider (AnthropicModelApi, OpenaiModelApi, BedrockModelApi)
        # - Composite provider (CompositeAiModelApi with different APIs for different operations)
        # - Configuration-driven selection based on environment variables
        raise NotImplementedError("AiModelApi wiring not yet implemented")

    def get_event_repository(self) -> EventRepository:
        """
        Get the configured event repository instance for inbox log.

        Returns:
            EventRepository instance for storing and retrieving events.
        """
        raise NotImplementedError("EventRepository wiring not yet implemented")


class DefaultApplication(Application):
    """Default application instance with configured dependencies."""

    def get_ai_model_api(self) -> AiModelApi:
        return CompositeAiModelApi(
            text_api=AnthropicModelApi(),
            embedding_api=BedrockModelApi(),
        )

    def get_event_repository(self) -> EventRepository:
        table_name = get_env("DDB_TABLE_NAME", required=True)
        assert table_name is not None
        return EventRepository(table_name=table_name)


# Default application instance for convenience
def app() -> Application:
    return DefaultApplication()
