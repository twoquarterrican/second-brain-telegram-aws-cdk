"""
Application layer for dependency injection and configuration.

This package contains the application composition root that wires up
all dependencies according to the ports and adapters architecture.
The Application class provides configured AiModelApi instances to
the domain logic.

Following hexagonal architecture principles:
- Application layer depends on ports (interfaces)
- Dependencies are injected at composition root
- No business logic - only dependency wiring
- Easy to test and configure different environments
"""

from lambdas.app.port.out import AiModelApi


class Application:
    """
    Application composition root for dependency injection.

    Provides configured AiModelApi instances to domain logic.
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


# Default application instance for convenience
DEFAULT_APP = Application()
