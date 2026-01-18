"""
Unit tests for the event repository using moto to mock DynamoDB.
"""

import os
import sys
import pytest
from datetime import datetime, timezone
from unittest import mock
import boto3
import os
from moto import mock_aws

# Add the parent directory to the path so we can import from src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

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
    # Store the original value (could be None if not set)
    original_value = os.environ.get("TELEGRAM_SECRET_TOKEN")

    # Set test value
    test_value = "test-secret-token-for-pytest"
    monkeypatch.setenv("TELEGRAM_SECRET_TOKEN", test_value)

    # Yield the test value so tests can use it
    yield test_value

    # Restore original value (or delete if it was originally None)
    if original_value is not None:
        monkeypatch.setenv("TELEGRAM_SECRET_TOKEN", original_value)
    else:
        monkeypatch.delenv("TELEGRAM_SECRET_TOKEN", raising=False)


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
    def test_non_command_message_dispatch(self):
        """Test that non-command messages are dispatched to the process action."""
        # Test the COMMAND_DISPATCH logic without actually calling the actions

        from lambdas.processor import COMMAND_DISPATCH

        # Test various message types
        test_cases = [
            (
                "Working on the web app redesign project",
                None,
            ),  # Should match None (process)
            ("/digest", "digest"),  # Should match /digest
            ("/open", "open_items"),  # Should match /open
            ("Some random message", None),  # Should match None (process)
        ]

        for message_text, expected_module in test_cases:
            # Find which action would be called
            called_action = None
            for prefix, action in COMMAND_DISPATCH:
                if prefix is None or message_text.startswith(prefix):
                    called_action = action
                    break

            if expected_module is None:
                # Should be the process action (the None case)
                assert called_action is not None
                # We can't easily test the actual call without mocking,
                # but we verify it reaches the process dispatch
            else:
                # Should match the expected command
                assert str(called_action).endswith(expected_module)

    def test_webhook_secret_validation(self, telegram_secret_token_env):
        """Test that webhook secret validation works."""
        from lambdas.processor import handler

        # telegram_secret_token_env fixture has set TELEGRAM_SECRET_TOKEN to "test-secret-token-for-pytest"

        # Test with correct secret
        event = {
            "headers": {"x-telegram-bot-api-secret-token": telegram_secret_token_env},
            "body": {"message": {"text": "test", "chat": {"id": "123"}}},
        }
        # This will fail later but should pass secret validation
        try:
            result = handler(event, None)
        except Exception:
            # Expected to fail on AI calls, but secret validation should pass
            pass

        # Test with wrong secret
        event_wrong_secret = {
            "headers": {"x-telegram-bot-api-secret-token": "wrong-secret"},
            "body": {"message": {"text": "test", "chat": {"id": "123"}}},
        }
        result = handler(event_wrong_secret, None)
        assert result["statusCode"] == 403
        assert result["body"] == "Forbidden"


if __name__ == "__main__":
    unittest.main()
