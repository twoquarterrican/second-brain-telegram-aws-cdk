"""Domain layer - Models for Second Brain.

This package contains the core domain models including:
- Events: Event sourcing models for audit trail and replay
- Items: Pydantic models for People, Projects, Ideas, Admin items
"""

from lambdas.domain.model.events import (
    ClassificationModel,
    Event,
    MessageReceived,
    MessageClassified,
    MessageSimilar,
    EventRepository,
)
from lambdas.domain.model.items import Item, People, Projects, Ideas, Admin

__all__ = [
    "ClassificationModel",
    "Event",
    "MessageReceived",
    "MessageClassified",
    "MessageSimilar",
    "EventRepository",
    "Item",
    "People",
    "Projects",
    "Ideas",
    "Admin",
]
