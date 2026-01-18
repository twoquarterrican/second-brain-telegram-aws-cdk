"""
Unit tests for the event repository using moto to mock DynamoDB.
"""

import os
import sys
import pytest
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest import mock
import boto3
from moto import mock_aws
from lambdas import processor
from lambdas.actions import process

from lambdas.events import (
    EventRepository,
    MessageReceived,
    MessageClassified,
    MessageSimilar,
)


def create_test_repo():
    """Helper to create EventRepository with test table."""
    dynamodb_resource = boto3.resource("dynamodb", region_name="us-east-1")

    # Create table with correct schema
    dynamodb_resource.create_table(
        TableName="test-events",
        KeySchema=[
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    # Create client within the mock context
    dynamodb_client = boto3.client("dynamodb", region_name="us-east-1")
    return EventRepository("test-events", dynamodb_client)


@pytest.fixture
def telegram_secret_token_env(monkeypatch):
    """Fixture to handle TELEGRAM_SECRET_TOKEN environment variable.

    Stores the original value, sets it to a test value for the test,
    and restores the original value after the test completes.
    Handles both cases where the variable exists or doesn't exist.
    """
    value = "test-secret-token"
    monkeypatch.setattr(processor, "TELEGRAM_SECRET_TOKEN", value)
    return value


@pytest.fixture
def anthropic_api_key_env(monkeypatch):
    """Fixture to handle ANTHROPIC_API_KEY environment variable."""
    value = "test-anthropic-api-key"
    monkeypatch.setattr(process, "ANTHROPIC_API_KEY", value)
    return value


@contextmanager
def monkey_patch_env(key: str, test_value: str, monkeypatch):
    """Context manager to handle environment variable setup/cleanup."""
    # Store the original value (could be None if not set)
    original_value = os.environ.get(key)

    # Set test value
    monkeypatch.setenv(key, test_value)

    try:
        # Yield the test value so tests can use it
        yield test_value
    finally:
        # Always restore original value (or delete if it was originally None)
        if original_value is not None:
            monkeypatch.setenv(key, original_value)
        else:
            monkeypatch.delenv(key, raising=False)


class TestMessageReceived:
    def test_message_received_creation(self):
        """Test MessageReceived event creation and validation."""
        timestamp = datetime.now(timezone.utc).isoformat()

        event = MessageReceived(
            event_type="MessageReceived",
            timestamp=timestamp,
            raw_text="Hello, this is a test message",
            source="telegram",
            source_id="12345",
            chat_id="chat_001",
            received_at=timestamp,
        )

        assert event.event_type == "MessageReceived"
        assert event.get_pk() == "EVENT#telegram"
        assert event.get_sk() == f"{timestamp}#12345"

    @mock_aws
    def test_message_received_storage(self):
        """Test storing MessageReceived event in DynamoDB."""
        event_repo = create_test_repo()
        timestamp = datetime.now(timezone.utc).isoformat()

        event = MessageReceived(
            event_type="MessageReceived",
            timestamp=timestamp,
            raw_text="Test message content",
            source="telegram",
            source_id="msg_001",
            chat_id="chat_123",
            received_at=timestamp,
        )

        # Should not raise an exception
        event_repo.append_event(event)

        # Verify the item was stored
        dynamodb = boto3.client("dynamodb", region_name="us-east-1")
        response = dynamodb.get_item(
            TableName="test-events",
            Key={"pk": {"S": event.get_pk()}, "sk": {"S": event.get_sk()}},
        )

        assert "Item" in response
        item = response["Item"]
        assert item["event_type"]["S"] == "MessageReceived"
        assert item["raw_text"]["S"] == "Test message content"
        assert item["source"]["S"] == "telegram"
        assert item["source_id"]["S"] == "msg_001"
        assert item["chat_id"]["S"] == "chat_123"


class TestMessageClassified:
    def test_message_classified_creation(self):
        """Test MessageClassified event creation and validation."""
        timestamp = datetime.now(timezone.utc).isoformat()

        event = MessageClassified(
            event_type="MessageClassified",
            timestamp=timestamp,
            classification="People",
            confidence_score=0.95,
            classified_by="claude-sonnet-4-20250514",
            classified_at=timestamp,
            item_pk="PEOPLE#john-doe",
            item_sk="PROFILE",
            source_event_sk="2024-01-17T10:00:00Z#msg_001",
        )

        assert event.event_type == "MessageClassified"
        assert event.classification == "People"
        assert event.confidence_score == 0.95

    @mock_aws
    def test_message_classified_storage(self):
        """Test storing MessageClassified event in DynamoDB."""
        event_repo = create_test_repo()
        timestamp = datetime.now(timezone.utc).isoformat()

        event = MessageClassified(
            event_type="MessageClassified",
            timestamp=timestamp,
            classification="Projects",
            confidence_score=0.87,
            classified_by="claude-sonnet-4-20250514",
            classified_at=timestamp,
            item_pk="PROJECTS#web-app",
            item_sk="PROFILE",
            source_event_sk="2024-01-17T10:00:00Z#msg_001",
        )

        event_repo.append_event(event)

        # Verify storage
        dynamodb = boto3.client("dynamodb", region_name="us-east-1")
        response = dynamodb.get_item(
            TableName="test-events",
            Key={"pk": {"S": event.get_pk()}, "sk": {"S": event.get_sk()}},
        )

        assert "Item" in response
        item = response["Item"]
        assert item["event_type"]["S"] == "MessageClassified"
        assert item["classification"]["S"] == "Projects"
        assert item["confidence_score"]["N"] == "0.87"
        assert item["item_pk"]["S"] == "PROJECTS#web-app"


class TestMessageSimilar:
    def test_message_similar_creation(self):
        """Test MessageSimilar event creation and validation."""
        timestamp = datetime.now(timezone.utc).isoformat()

        event = MessageSimilar(
            event_type="MessageSimilar",
            timestamp=timestamp,
            similar_event_sk="2024-01-17T09:00:00Z#msg_002",
            similarity_score=0.92,
            threshold_used=0.80,
            search_model="text-embedding-ada-002",
            searched_at=timestamp,
            link_created=True,
            linked_item_pk="PEOPLE#john-doe",
            linked_item_sk="PROFILE",
            source_event_sk="2024-01-17T10:00:00Z#msg_001",
        )

        assert event.event_type == "MessageSimilar"
        assert event.similarity_score == 0.92
        assert event.link_created is True

    @mock_aws
    def test_message_similar_no_match(self):
        """Test MessageSimilar event when no similar message is found."""
        event_repo = create_test_repo()
        timestamp = datetime.now(timezone.utc).isoformat()

        event = MessageSimilar(
            event_type="MessageSimilar",
            timestamp=timestamp,
            similar_event_sk=None,
            similarity_score=0.0,
            threshold_used=0.80,
            search_model="text-embedding-ada-002",
            searched_at=timestamp,
            link_created=False,
            linked_item_pk=None,
            linked_item_sk=None,
            source_event_sk="2024-01-17T10:00:00Z#msg_001",
        )

        event_repo.append_event(event)

        # Verify storage
        dynamodb = boto3.client("dynamodb", region_name="us-east-1")
        response = dynamodb.get_item(
            TableName="test-events",
            Key={"pk": {"S": event.get_pk()}, "sk": {"S": event.get_sk()}},
        )

        assert "Item" in response
        item = response["Item"]
        assert item["event_type"]["S"] == "MessageSimilar"
        assert item["similarity_score"]["N"] == "0.0"
        assert item["link_created"]["BOOL"] is False
        assert "similar_event_sk" not in item  # Should not be present when None


class TestEventRepository:
    @mock_aws
    def test_append_multiple_events(self):
        """Test appending multiple different event types."""
        event_repo = create_test_repo()
        base_time = datetime.now(timezone.utc)

        # Create events with slightly different timestamps
        events = []

        # MessageReceived
        timestamp1 = (base_time).isoformat()
        event1 = MessageReceived(
            event_type="MessageReceived",
            timestamp=timestamp1,
            raw_text="First message",
            source="telegram",
            source_id="msg_001",
            received_at=timestamp1,
        )
        events.append(event1)

        # MessageClassified
        timestamp2 = (base_time).isoformat()
        event2 = MessageClassified(
            event_type="MessageClassified",
            timestamp=timestamp2,
            classification="Ideas",
            confidence_score=0.91,
            classified_by="claude-sonnet-4-20250514",
            classified_at=timestamp2,
            item_pk="IDEAS#ai-integration",
            item_sk="PROFILE",
            source_event_sk=event1.get_sk(),
        )
        events.append(event2)

        # MessageSimilar
        timestamp3 = (base_time).isoformat()
        event3 = MessageSimilar(
            event_type="MessageSimilar",
            timestamp=timestamp3,
            similar_event_sk=None,
            similarity_score=0.0,
            threshold_used=0.80,
            search_model="text-embedding-ada-002",
            searched_at=timestamp3,
            link_created=False,
            linked_item_pk=None,
            linked_item_sk=None,
            source_event_sk=event1.get_sk(),
        )
        events.append(event3)

        # Store all events
        for event in events:
            event_repo.append_event(event)

        # Verify all events are stored
        dynamodb = boto3.client("dynamodb", region_name="us-east-1")
        for event in events:
            response = dynamodb.get_item(
                TableName="test-events",
                Key={"pk": {"S": event.get_pk()}, "sk": {"S": event.get_sk()}},
            )
            assert "Item" in response
            assert response["Item"]["event_type"]["S"] == event.event_type

    def test_invalid_confidence_score(self):
        """Test that invalid confidence scores are rejected."""
        timestamp = datetime.now(timezone.utc).isoformat()

        with pytest.raises(ValueError):
            MessageClassified(
                event_type="MessageClassified",
                timestamp=timestamp,
                classification="People",
                confidence_score=1.5,  # Invalid: > 1.0
                classified_by="test-model",
                classified_at=timestamp,
                item_pk="PEOPLE#test",
                item_sk="PROFILE",
                source_event_sk="2024-01-17T10:00:00Z#msg_001",
            )


class TestProcessorHandler:
    def test_non_command_message_dispatch(self, telegram_secret_token_env, anthropic_api_key_env):
        """Test that non-command messages are dispatched to the process action."""
        # Test the COMMAND_DISPATCH logic without actually calling the actions
        print(telegram_secret_token_env)
        response = processor.handler(
            {
                "headers": {
                    "x-telegram-bot-api-secret-token": telegram_secret_token_env
                },
                "body": {"message": {"text": "test", "chat": {"id": "123"}}},
            },
            None,
        )
        print(response)

    def test_webhook_secret_validation_wrong_secret(self, telegram_secret_token_env):
        """Test that webhook secret validation works."""

        # Test with wrong secret
        event_wrong_secret = {
            "headers": {"x-telegram-bot-api-secret-token": "wrong-secret"},
            "body": {"message": {"text": "test", "chat": {"id": "123"}}},
        }
        result = processor.handler(event_wrong_secret, None)
        assert result["statusCode"] == 403
        assert result["body"] == "Forbidden"
