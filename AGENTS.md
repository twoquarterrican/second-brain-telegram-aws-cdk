# AGENTS.md - Guidelines for Coding Agents

This document contains guidelines for agentic coding agents working on the Second Brain Telegram AWS project.

## Project Overview

This is a Python 3.13 serverless application that implements a personal second brain system using Telegram bots and AWS Lambda. The system captures thoughts via Telegram, processes them with AI, stores insights in DynamoDB, and generates automated digest summaries.

## Build, Lint, Test, and Typecheck Commands

### Environment Setup
```bash
# Install dependencies and create virtual environment
uv sync

# Install development dependencies
uv sync --group dev

# Activate virtual environment
source .venv/bin/activate  # Linux/macOS
# or .venv\Scripts\activate  # Windows
```

### Code Quality Commands
```bash
# Run formatter (Black)
black .

# Run linter (Ruff)
ruff check .
ruff check . --fix  # Auto-fix issues

# Run type checker (MyPy)
mypy .

# Run all quality checks together
black . && ruff check . --fix && mypy .
```

### Secret Management Commands
```bash
# Store/sync all secrets from env.json to Parameter Store
uv run scripts/secrets.py store

# Store secrets (force overwrite existing)
uv run scripts/secrets.py store --force

# List stored secrets (values hidden)
uv run scripts/secrets.py list

# List secrets with values (decrypted)
uv run scripts/secrets.py list --show-values

# Update a specific secret from env.json
uv run scripts/secrets.py update --parameter /second-brain/anthropic-api-key

# Sync secrets (alias for store)
uv run scripts/secrets.py sync

# Or use the script name (registered in pyproject.toml)
secrets store
secrets list --show-values
secrets update --parameter /second-brain/telegram-bot-token
```

### Testing Commands
```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=processor --cov=digest --cov=scripts

# Run specific test file
pytest tests/test_processor.py

# Run specific test function
pytest tests/test_processor.py::test_function_name

# Run tests with verbose output
pytest -v

# Run tests with specific marker
pytest -m unit
pytest -m integration
```

### Build and Deployment Commands
```bash
# Build SAM application
sam build

# Deploy SAM application (first time - guided)
sam deploy --guided

# Deploy SAM application (subsequent deployments)
sam deploy

# Local testing
sam local invoke ProcessorLambda -e events/test-event.json
sam local invoke DigestLambda -e events/test-event.json

# Start local API Gateway for testing
sam local start-api
```

## Code Style Guidelines

### Import Organization
- Use `isort`-style import organization (handled automatically by ruff)
- Group imports: standard library, third-party, local application
- Use absolute imports for local modules
- Import order: `os`, `sys`, `logging`, `boto3`, `requests`, third-party, local modules

```python
# Standard library
import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

# Third-party
import boto3
import requests
from anthropic import Anthropic

# Local application
from utils.helpers import process_message
```

### Formatting and Line Length
- **Line length**: 88 characters (Black default)
- **Indentation**: 4 spaces
- **String quotes**: Double quotes for consistency
- **Trailing commas**: Required in multi-line function calls and data structures

### Type Hints
- All functions must have proper type hints
- Use `Optional[T]` for nullable types
- Use `Dict`, `List`, `Any` from typing module
- Use `Union` for multiple possible types
- Return types are mandatory for all functions

```python
def process_message(
    message: str, 
    category: str, 
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Process a message and return structured data."""
    # Implementation
    return {"status": "success", "data": {}}
```

### Naming Conventions
- **Variables and functions**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private methods**: `_leading_underscore`
- **Environment variables**: `UPPER_SNAKE_CASE`

```python
MAX_RETRIES = 3

class MessageProcessor:
    def _process_internal(self, message_data: Dict[str, Any]) -> bool:
        # Implementation
        pass
    
    def process_webhook(self, webhook_data: str) -> Dict[str, Any]:
        # Implementation
        pass
```

### Error Handling Patterns
- Use specific exception types when possible
- Log errors with context information
- Use try-except blocks for external API calls
- Return consistent error response format in Lambda handlers
- Never let exceptions propagate to the user in production

```python
import logging

logger = logging.getLogger(__name__)

def call_ai_api(prompt: str) -> Optional[str]:
    """Call AI API with proper error handling."""
    try:
        response = anthropic_client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.error(f"AI API call failed: {e}")
        return None

def lambda_handler(event, context):
    """Lambda handler with proper error handling."""
    try:
        # Main logic
        result = process_event(event)
        return {"statusCode": 200, "body": json.dumps(result)}
    except ValueError as e:
        logger.warning(f"Invalid input: {e}")
        return {"statusCode": 400, "body": json.dumps({"error": str(e)})}
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return {"statusCode": 500, "body": json.dumps({"error": "Internal server error"})}
```

### Lambda Function Patterns
- Always use the same function signature: `def lambda_handler(event, context):`
- Validate environment variables early
- Use structured logging
- Return appropriate HTTP status codes
- Handle timeouts and rate limiting

```python
def lambda_handler(event, context):
    """Standard Lambda handler pattern."""
    # Environment validation
    if not validate_environment():
        return {"statusCode": 500, "body": "Configuration error"}
    
    logger.info(f"Processing event: {event}")
    
    try:
        # Core logic
        result = process_business_logic(event)
        return {"statusCode": 200, "body": json.dumps(result)}
    except Exception as e:
        logger.error(f"Lambda processing failed: {e}", exc_info=True)
        return {"statusCode": 500, "body": "Internal server error"}
```

### AWS Integration Patterns
- Use boto3 clients and resources
- Handle AWS service exceptions specifically
- Use proper IAM policies (least privilege)
- Implement retries with exponential backoff for AWS calls

```python
import boto3
from botocore.exceptions import ClientError

def save_to_dynamodb(table_name: str, item: Dict[str, Any]) -> bool:
    """Save item to DynamoDB with proper error handling."""
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)
        
        table.put_item(Item=item)
        logger.info(f"Successfully saved item to {table_name}")
        return True
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        logger.error(f"DynamoDB error {error_code}: {e}")
        return False
```

### Configuration Management
- Use environment variables for all configuration
- Provide sensible defaults
- Validate required environment variables on startup
- Never hardcode secrets or API keys

```python
def get_config() -> Dict[str, str]:
    """Load and validate configuration from environment."""
    required_vars = ["ANTHROPIC_API_KEY", "TELEGRAM_BOT_TOKEN"]
    config = {}
    
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            raise ValueError(f"Required environment variable {var} is missing")
        config[var] = value
    
    # Optional variables with defaults
    config["LOG_LEVEL"] = os.getenv("LOG_LEVEL", "INFO")
    config["DDB_TABLE_NAME"] = os.getenv("DDB_TABLE_NAME", "SecondBrain")
    
    return config
```

### Logging Standards
- Use the logging module, not print statements
- Include context in log messages
- Use appropriate log levels (DEBUG, INFO, WARNING, ERROR)
- Structure log messages for easy parsing

```python
import logging

logger = logging.getLogger(__name__)

def process_user_message(user_id: str, message: str):
    logger.info(f"Processing message from user {user_id}")
    
    try:
        result = classify_message(message)
        logger.info(f"Message classified as: {result['category']}")
    except Exception as e:
        logger.error(f"Failed to process message for user {user_id}: {e}")
        raise
```

## Project Structure

```
second-brain-telegram-aws/
├── processor/
│   └── app.py              # Telegram webhook processor
├── digest/
│   └── app.py              # Scheduled digest generator
├── scripts/
│   └── setup_webhook.py    # Webhook setup utility
├── tests/                  # Test files (create as needed)
├── events/                 # Sample events for local testing
├── pyproject.toml          # Project configuration
├── template.yaml           # AWS SAM template
├── samconfig.toml          # SAM CLI configuration
└── env.json               # Environment variables (for local dev)
```

## Testing Guidelines

- Write unit tests for all business logic functions
- Use pytest fixtures for test setup
- Mock external services (Telegram API, AWS services, AI APIs)
- Test error conditions and edge cases
- Use descriptive test names that explain the scenario

```python
import pytest
from unittest.mock import Mock, patch
from processor.app import process_message

def test_process_message_valid_input():
    """Test process_message with valid input returns expected structure."""
    message = "Schedule team meeting for project review"
    result = process_message(message)
    
    assert result["status"] == "success"
    assert "category" in result["data"]
    assert result["data"]["category"] in ["People", "Projects", "Ideas", "Admin"]

@patch('processor.app.anthropic_client')
def test_process_message_ai_failure(mock_client):
    """Test process_message handles AI API failure gracefully."""
    mock_client.messages.create.side_effect = Exception("AI API error")
    
    with pytest.raises(Exception):
        process_message("test message")
```

## Security Considerations

- Never commit API keys or secrets to the repository
- Use environment variables for all sensitive configuration
- Validate webhook signatures using secret tokens
- Implement proper IAM policies with least privilege
- Sanitize user inputs before processing
- Use HTTPS for all external communications

## Performance Guidelines

- Keep Lambda functions under 30 seconds when possible
- Use connection pooling for external API calls
- Implement proper caching where appropriate
- Monitor DynamoDB consumption and costs
- Use efficient data structures and algorithms
- Consider cold start optimization for critical paths

## Adding New Features

1. Create feature branch from main
2. Write tests first (TDD approach when possible)
3. Implement the feature following code style guidelines
4. Run full test suite and quality checks
5. Update documentation if needed
6. Submit pull request with clear description

## When to Ask for Clarification

- Requirements are ambiguous or missing details
- Security implications of a change are unclear
- Performance impact might be significant
- Database schema changes are required
- Breaking changes to existing APIs are proposed
- Cost implications for AWS resources are unclear