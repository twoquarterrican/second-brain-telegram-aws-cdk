"""
Event sourcing models and repository for Second Brain.

This module implements the event store pattern as defined in ADR-001.
Events are stored in a single DynamoDB table with PK/SK patterns.
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple
from pydantic import BaseModel, Field
import boto3
from botocore.exceptions import ClientError
from common.timestamps import format_iso8601_zulu


class Event(BaseModel, ABC):
    """Base class for all events in the system."""

    event_type: str = Field(..., description="Type of event")
    timestamp: str = Field(..., description="ISO timestamp when event occurred")

    @abstractmethod
    def get_pk(self) -> str:
        """Return the partition key for this event."""
        pass

    @abstractmethod
    def get_sk(self) -> str:
        """Return the sort key for this event."""
        pass


class MessageReceived(Event):
    """Event fired when a message is received from a source."""

    # Message content
    raw_text: str = Field(..., description="Original message text, unmodified")

    # Source information
    source: str = Field(..., description="Source system: 'telegram', 'email', 'voice'")
    source_id: str = Field(..., description="Unique ID from source system")
    chat_id: Optional[str] = Field(None, description="Chat/room identifier")

    # Metadata
    received_at: str = Field(..., description="ISO timestamp when message was received")

    def get_pk(self) -> str:
        return self.build_pk(self.source)

    def get_sk(self) -> str:
        return self.build_sk(self.received_at, self.source_id)

    @staticmethod
    def build_pk(source: str) -> str:
        """Build PK from source."""
        return f"EVENT#{source}"

    @staticmethod
    def build_sk(received_at: str, source_id: str) -> str:
        """Build SK from timestamp and source ID."""
        return f"{received_at}#{source_id}"

    @staticmethod
    def parse_pk(pk: str) -> str:
        """Parse source from PK."""
        return pk.split("#", 1)[1]

    @staticmethod
    def parse_sk(sk: str) -> Tuple[str, str]:
        """Parse received_at and source_id from SK."""
        received_at, source_id = sk.split("#", 1)
        return received_at, source_id


class MessageClassified(Event):
    """Event fired when a message is classified by AI."""

    # Classification results
    classification: str = Field(
        ..., description="AI classification: 'People', 'Projects', 'Ideas', 'Admin'"
    )
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="AI confidence score"
    )

    # Model information
    classified_by: str = Field(..., description="AI model used for classification")
    classified_at: str = Field(
        ..., description="ISO timestamp when classification occurred"
    )

    # Links to related entities
    item_pk: str = Field(..., description="PK of the created/updated item")
    item_sk: str = Field(..., description="SK of the created/updated item")

    # Reference to source message
    source_event_sk: str = Field(..., description="SK of the MessageReceived event")
    source: str = Field(..., description="Source system: 'telegram', 'email', 'voice'")

    # Original message for replay capability
    raw_text: str = Field(..., description="Original message text, unmodified")

    def get_pk(self) -> str:
        return self.build_pk(self.source)

    def get_sk(self) -> str:
        return self.build_sk(self.classified_at)

    @staticmethod
    def build_pk(source: str) -> str:
        """Build PK from source."""
        return f"EVENT#{source}"

    @staticmethod
    def build_sk(classified_at: str, sequence: int = 1) -> str:
        """Build SK from timestamp and sequence number."""
        return f"{classified_at}#CLASSIFIED#{sequence}"

    @staticmethod
    def parse_pk(pk: str) -> str:
        """Parse source from PK."""
        return pk.split("#", 1)[1]

    @staticmethod
    def parse_sk(sk: str) -> Tuple[str, int]:
        """Parse classified_at and sequence from SK."""
        # Format: "timestamp#CLASSIFIED#sequence"
        parts = sk.split("#")
        classified_at = parts[0]
        sequence = int(parts[2])
        return classified_at, sequence

    @classmethod
    def create_from_classification(
        cls,
        raw_text: str,
        category: str,
        confidence_pct: int,
        classified_by: str,
        source_message: "MessageReceived",
    ) -> "MessageClassified":
        """Factory method to create a MessageClassified event from classification result."""
        now_iso = format_iso8601_zulu()
        confidence_score = min(100, max(0, confidence_pct)) / 100.0

        # Create item identifiers
        category_lower = category.lower()
        item_id = source_message.source_id[:16]  # Use first 16 chars of source ID
        item_pk = f"{category_lower}#{item_id}"
        item_sk = "PROFILE"

        return cls(
            event_type="MessageClassified",
            timestamp=now_iso,
            classification=category,
            confidence_score=confidence_score,
            classified_by=classified_by,
            classified_at=now_iso,
            item_pk=item_pk,
            item_sk=item_sk,
            source_event_sk=source_message.get_sk(),
            source=source_message.source,
            raw_text=raw_text,
        )


class MessageSimilar(Event):
    """Event fired when similarity search finds related messages."""

    # Similarity results
    similar_event_sk: Optional[str] = Field(
        None, description="SK of similar MessageReceived event, if found"
    )
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Similarity score")
    threshold_used: float = Field(
        ..., ge=0.0, le=1.0, description="Minimum score threshold"
    )

    # Search metadata
    search_model: str = Field(..., description="Embedding/vector model used")
    searched_at: str = Field(..., description="ISO timestamp when search was performed")

    # Linking results
    link_created: bool = Field(False, description="Whether a new item link was created")
    linked_item_pk: Optional[str] = Field(
        None, description="PK of item that got linked"
    )
    linked_item_sk: Optional[str] = Field(
        None, description="SK of item that got linked"
    )

    # Reference to source message
    source_event_sk: str = Field(
        ..., description="SK of the MessageReceived event being analyzed"
    )

    def get_pk(self) -> str:
        return "EVENT#telegram"  # TODO: derive from source_event_sk

    def get_sk(self) -> str:
        # Format: "{timestamp}#{source_id}#SIMILAR#{sequence}"
        return f"{self.searched_at}#SIMILAR#1"  # TODO: handle sequence numbers


class EventRepository:
    """Repository for storing and retrieving events from DynamoDB."""

    def __init__(self, table_name: str, dynamodb_client=None):
        self.table_name = table_name
        self.dynamodb = dynamodb_client or boto3.client("dynamodb")

    def append_event(self, event: Event) -> None:
        """
        Append an event to the event store.

        Args:
            event: The event to store

        Raises:
            ClientError: If the DynamoDB operation fails
        """
        item = {
            "pk": {"S": event.get_pk()},
            "sk": {"S": event.get_sk()},
            "event_type": {"S": event.event_type},
            "timestamp": {"S": event.timestamp},
        }

        # Add event-specific attributes
        if isinstance(event, MessageReceived):
            item.update(
                {
                    "raw_text": {"S": event.raw_text},
                    "source": {"S": event.source},
                    "source_id": {"S": event.source_id},
                    "received_at": {"S": event.received_at},
                }
            )
            if event.chat_id:
                item["chat_id"] = {"S": event.chat_id}

        elif isinstance(event, MessageClassified):
            item.update(
                {
                    "classification": {"S": event.classification},
                    "confidence_score": {"N": str(event.confidence_score)},
                    "classified_by": {"S": event.classified_by},
                    "classified_at": {"S": event.classified_at},
                    "item_pk": {"S": event.item_pk},
                    "item_sk": {"S": event.item_sk},
                    "source_event_sk": {"S": event.source_event_sk},
                    "source": {"S": event.source},
                    "raw_text": {"S": event.raw_text},
                }
            )

        elif isinstance(event, MessageSimilar):
            item.update(
                {
                    "similarity_score": {"N": str(event.similarity_score)},
                    "threshold_used": {"N": str(event.threshold_used)},
                    "search_model": {"S": event.search_model},
                    "searched_at": {"S": event.searched_at},
                    "link_created": {"BOOL": event.link_created},
                    "source_event_sk": {"S": event.source_event_sk},
                }
            )
            if event.similar_event_sk:
                item["similar_event_sk"] = {"S": event.similar_event_sk}
            if event.linked_item_pk:
                item["linked_item_pk"] = {"S": event.linked_item_pk}
            if event.linked_item_sk:
                item["linked_item_sk"] = {"S": event.linked_item_sk}

        try:
            self.dynamodb.put_item(TableName=self.table_name, Item=item)
        except ClientError as e:
            raise e


# TODO: Hook up event repository to lambda functions
# - processor.py should use EventRepository to store MessageReceived events
# - embedding_matcher.py should use EventRepository to store MessageClassified events
# - Add similarity search lambda to store MessageSimilar events</content>
