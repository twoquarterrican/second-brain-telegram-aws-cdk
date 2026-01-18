# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Second Brain Telegram AWS is a serverless knowledge management system that captures thoughts via Telegram, classifies them with AI, and sends proactive digest summaries. The project is a Python monorepo using `uv` workspace with four packages (cdk, common, lambdas, scripts) deployed as AWS Lambda functions.

## Common Commands

### Development Setup

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Format code
uv run ruff format .

# Check types
uvx ty check

# Lint (import sorting, unused imports, print statements)
uv run ruff check .
```

### Pre-commit Hooks

```bash
# These run automatically before commit:
# - ruff format (auto-format Python)
# - ruff check (import sorting, I, E4, F, T201)
# - ty check (type checking)
# - trailing whitespace, EOF fixer, YAML check

# To bypass (not recommended): git commit --no-verify
```

### Single Test Run

```bash
# Run specific test file
uv run pytest packages/lambdas/tests/test_events.py -v

# Run specific test
uv run pytest packages/lambdas/tests/test_events.py::test_name -v

# Run tests matching pattern
uv run pytest -k "pattern" -v
```

### Building & Deployment

```bash
# Deploy with CDK (builds layer and deploys)
uv run deploy deploy

# View what will change
uv run deploy diff

# Synthesize CloudFormation template
uv run deploy synth

# Destroy stack
uv run deploy destroy

# Direct CDK commands
uv run cdkw deploy
uv run cdkw synth
uv run cdkw diff
```

### CLI Tools

```bash
# Setup Telegram webhook
setup-webhook          # Interactive mode
setup-webhook set --token TOKEN --auto-detect
setup-webhook info --token TOKEN

# Tail Lambda logs
tail-logs

# Manually trigger digest
uv run trigger-digest trigger --digest-type daily
uv run trigger-digest trigger --digest-type weekly --role-arn arn:aws:iam::ACCOUNT:role/SecondBrainTriggerRole

# Debug DynamoDB
dynamo-debug command [args]

# Backfill embeddings
backfill-embeddings

# Assume role for cross-account access
assume-role
```

## Architecture Overview

### High-Level System Flow

```
Telegram → Lambda Function URL → Processor Lambda
                                      ↓
                              [AI Classification]
                                  ↓ ↓ ↓
                        [Anthropic / OpenAI / Bedrock]
                                  ↓
                        [Embedding Matching via S3 Vectors]
                                  ↓
                        [DynamoDB] ← Update or Create
                                  ↓
                        [EventBridge Cron Triggers]
                                  ↓
                        [Digest Lambda] → Summarize & Send
```

### Package Structure

**packages/cdk** - Infrastructure as Code
- `app.py` - CDK app entry point, instantiates stack
- `second_brain_stack.py` - Defines all AWS resources (Lambda, DynamoDB, EventBridge, S3)
- Lambda layer built with Docker + `uv` containing shared dependencies
- Exports CloudFormation outputs: `TriggerRoleArn`, Lambda function names

**packages/common** - Shared Utilities
- `environments.py` - Loads `.env.local` via `DotEnv`, provides `get_env()` helper
- `logging.py` - JSON logging setup for CloudWatch
- `bedrock_embeddings.py` - Titan embedding generation for deduplication

**packages/lambdas** - Lambda Functions & Business Logic
- `processor.py:handler` - Main webhook handler, command dispatch table
- `digest.py:handler` - EventBridge-triggered digest generator
- `embedding_matcher.py` - S3 Vectors similarity search for deduplication
- `actions/` - Individual command handlers (process, merge, delete, debug_*)
- `adapter/` - Ports & Adapters pattern for AI providers and Telegram
- `app/` - Application class for dependency injection
- `telegram/` - Telegram API models and message builders
- `events.py` - Internal event models (ProcessResult, DigestResult)

**packages/scripts** - CLI Tools
- `setup_webhook.py` - Interactive Telegram webhook configuration
- `cdkw.py` - CDK wrapper that builds layer before running CDK
- `tail_logs.py` - Stream CloudWatch logs from recent Lambda executions
- `trigger_digest.py` - Manually invoke digest Lambda with optional role assumption
- `dynamo_debug.py` - Query/inspect DynamoDB table

### Key Architectural Patterns

**Command Dispatch**: `processor.py` uses a dispatch table pattern
```python
COMMAND_DISPATCH = [
    ("/digest", digest.handle),
    ("/open", open_items.handle),
    (None, process_action.handle),  # Default: classify message
]
```

**AI Provider Fallback Chain**:
1. Anthropic Claude (primary)
2. OpenAI GPT (secondary)
3. AWS Bedrock Claude (tertiary + embeddings)

**Embedding-Based Deduplication**:
- Generate embedding for incoming message with Bedrock Titan v2
- Query S3 Vectors for similar items in same category
- If similarity ≥ 0.85: update existing item
- Otherwise: create new item and index vector

**Ports & Adapters** (in `adapter/`):
- AI providers abstracted behind common interface
- Telegram API abstracted from business logic
- Dependency injection via `Application` class

**Dependency Injection** (composition root):
- Single entry point: `app()` function returns `DefaultApplication` instance
- Application provides: `get_ai_model_api()`, `get_event_repository()`
- All external dependencies wired here: EventRepository, EventStore, AI providers
- Benefits: Easy to mock in tests (replace `app()` with test double), single configuration point
- Use pattern: `app().get_event_repository().append_event(event)` throughout codebase

### DynamoDB Schema

**SecondBrainTable**:
- PK: `category#timestamp` (e.g., `PEOPLE#2025-01-18T10:30:00Z`)
- SK: `item_id` (UUID)
- Attributes: `original_text`, `name`, `status`, `next_action`, `notes`, `confidence`, `embedding_id`
- GSI: `StatusIndex` (category → status, enables status-based queries)

**S3 Vectors**:
- Stores vector embeddings for items
- Index named `SecondBrainItemsIndex` (created separately, not in CDK)
- Similarity search returns top 5 results in same category

### Error Handling Philosophy

From AGENTS.md guidelines:
- Let exceptions propagate (users need to see errors)
- Add context before re-raising (log then re-raise)
- Catch specific exceptions (never bare `except:`)
- Retry with backoff for transient API failures

### Environment Variables

**Required**:
- `ANTHROPIC_API_KEY` - Claude API key
- `OPENAI_API_KEY` - OpenAI API key (fallback)
- `TELEGRAM_BOT_TOKEN` - Bot token from BotFather
- `TELEGRAM_SECRET_TOKEN` - Webhook verification secret
- `USER_CHAT_ID` - Telegram chat ID for digest messages

**Optional**:
- `BEDROCK_REGION` - AWS region for Bedrock (defaults to AWS_REGION)
- `AWS_PROFILE` - AWS credential profile (for scripts)
- `AWS_REGION` - AWS region (defaults to us-east-1)

**Auto-set by CDK**:
- `DDB_TABLE_NAME` - DynamoDB table name

Scripts automatically load `.env.local` via `common.environments.get_env()`. Do not manually call `os.environ` in scripts.

### Deploy Process

1. **Build Lambda Layer**: `deploy` script runs Docker to build layer with `uv pip install`
2. **Copy common package**: Layer includes `packages/common` for shared utilities
3. **Synth CDK**: Generates CloudFormation template
4. **Deploy**: Creates/updates CloudFormation stack

Lambda layer is at `packages/lambdas/asset-output/` and includes all dependencies + common package.

### Configuration & Customization

- **Digest schedules**: Edit `second_brain_stack.py` for EventBridge cron expressions
- **Lambda memory**: Configure in `second_brain_stack.py` resource definitions
- **AI model selection**: Edit `adapter/ai_provider.py` to change models
- **Bedrock region hardcoded**: `us-east-2` in S3 Vectors IAM policy (technical debt)

### Testing

Tests located in `packages/lambdas/tests/`:
- `test_events.py` - Tests for event models and Telegram parsing
- Uses `pytest` with `moto` for AWS mocking
- Run with: `uv run pytest packages/lambdas/tests/ -v`

### Known Limitations & Technical Debt

- S3 Vector Index cannot be created via CDK (must be created separately)
- No dedicated encryption keys (uses AWS-managed keys)
- Lambda handlers lack comprehensive test coverage
- Bedrock region hardcoded in IAM policy

## Important Notes

- **Pre-commit hooks** enforce ruff formatting, import sorting, and type checking before commit
- **No schema migrations**: Flexibility is by design; use event sourcing approach (INBOX_LOG) for schema changes
- **DynamoDB pay-per-request**: No capacity provisioning needed
- **Function URL is public**: Security depends on `X-Telegram-Bot-Api-Secret-Token` header validation
- **Confidence scoring**: AI confidence < 60% items marked as `needs_review`
