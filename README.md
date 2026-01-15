# 🧠 Second Brain with Telegram & AWS

A personal second brain system that captures thoughts via Telegram and processes them with AI, storing insights in DynamoDB with automated digest summaries.

Inspired by [Tiago Forte's Building a Second Brain](https://www.buildingasecondbrain.com/).

## 🏗️ Architecture

```
┌─────────────┐    Webhook     ┌─────────────┐    AI API     ┌─────────────┐
│  Telegram   │ ──────────────► │  AWS Lambda │ ───────────► │ Claude/GPT  │
│    Bot      │                │  Processor  │   (Bedrock)  │   (APIs)    │
└─────────────┘                └─────────────┘              └─────────────┘
                                        │
                                        ▼
                               ┌─────────────┐
                               │  DynamoDB   │
                               │  SecondBrain│
                               └─────────────┘
                                        ▲
                               Scheduled │  EventBridge
                                        ▼
                               ┌─────────────┐
                               │  AWS Lambda │ ──► Telegram
                               │   Digest    │      Chat
                               └─────────────┘
```

## 🚀 Features

- **Capture**: Send text messages to your personal Telegram bot
- **AI Classification**: Automatically categorizes thoughts into People/Projects/Ideas/Admin using Anthropic Claude, OpenAI GPT, or AWS Bedrock
- **Smart Extraction**: Extracts name, status, next actions, and notes with confidence scoring
- **Automated Digests**: Daily (8AM UTC) and weekly (Sunday 9AM UTC) summaries
- **Three-Tier AI Fallback**: Primary (Anthropic), Secondary (OpenAI), Tertiary (Bedrock)
- **Serverless**: AWS CDK deployment with Lambda and DynamoDB
- **Pay-per-use**: Typically $0-5/month

## 📋 Prerequisites

- AWS account with appropriate permissions
- GitHub account with GitHub CLI (`gh`) installed and authenticated
- Python 3.12+
- **uv** (modern Python package manager) installed
- AWS CDK CLI installed (`npm install -g aws-cdk`)
- Telegram account

### Installing uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## 🛠️ Setup Instructions

### 1. Clone and Setup Development Environment

```bash
git clone https://github.com/twoquarterrican/second-brain-telegram-aws.git
cd second-brain-telegram-aws

uv sync
```

### 2. Create Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` and follow instructions
3. Save your bot token (looks like `123456789:ABC...`)
4. Get your chat ID: Start a conversation with `@userinfobot`

### 3. Configure Environment Variables

Create `.env.local` in the project root:

```bash
# AWS Configuration
AWS_PROFILE=yourprofile        # AWS profile name (optional)
AWS_REGION=us-east-1           # AWS region

# API Keys
ANTHROPIC_API_KEY=your_anthropic_api_key
OPENAI_API_KEY=your_openai_api_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_SECRET_TOKEN=your_random_secret_token
USER_CHAT_ID=your_telegram_chat_id
BEDROCK_REGION=us-east-1       # Optional, defaults to AWS_REGION
```

**Note**: Python scripts automatically load `.env.local` via `common.environments`. Do not manually set `os.environ` in scripts.

**API Keys**:
- **Anthropic Claude**: Get from [console.anthropic.com](https://console.anthropic.com/)
- **OpenAI**: Get from [platform.openai.com](https://platform.openai.com/)

### 4. Deploy with CDK

```bash
uv run deploy deploy
```

Or using the CDK wrapper directly:

```bash
uv run cdkw deploy
```

### 5. Trigger Role for Scripts

CDK creates a `SecondBrainTriggerRole` with `lambda:InvokeFunction` permissions on the stack's Lambdas. The role trusts the same account by default.

For cross-account access, set your AWS account ID before deploying:

```bash
export TRIGGER_ROLE_TRUST_ACCOUNT=123456789012
uv run deploy deploy
```

Give your IAM user permission to assume this role:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": "sts:AssumeRole",
            "Resource": "arn:aws:iam::123456789012:role/SecondBrainTriggerRole"
        }
    ]
}
```

**Note**: The role ARN is exported as `TriggerRoleArn` in CloudFormation outputs.

## CLI Commands

### Webhook Setup

```bash
# Interactive mode (recommended)
setup-webhook

# Set webhook with parameters
setup-webhook set --token YOUR_TOKEN --auto-detect

# Get current webhook info
setup-webhook info --token YOUR_TOKEN

# Test bot connection
setup-webhook test --token YOUR_TOKEN

# Delete webhook
setup-webhook delete --token YOUR_TOKEN --force
```

### Tail Logs

```bash
tail-logs
```

### CDK Wrapper

```bash
# Run any CDK command
uv run cdkw synth
uv run cdkw diff
uv run cdkw deploy
uv run cdkw destroy
```

### Deploy Script (Builds Layer + CDK)

```bash
uv run deploy deploy
uv run deploy synth
uv run deploy diff
uv run deploy destroy
```

## 📱 Usage

### Capturing Thoughts

Send natural language messages to your bot:

```
• "Need to schedule team meeting for Q4 planning"
• "Sarah's birthday is next month, buy gift"
• "Research quantum computing applications in finance"
• "File taxes before April deadline"
```

### Receiving Digests

- **Daily Digest**: Sent at 8AM UTC with recent items and open tasks
- **Weekly Digest**: Sent Sundays at 9AM UTC with comprehensive summary

### Trigger Digest Manually

```bash
# Interactive mode (prompts for missing values, auto-detects role)
uv run trigger-digest

# With flags
uv run trigger-digest trigger --digest-type daily

# With role assumption (recommended for limited permissions)
uv run trigger-digest trigger --role-arn arn:aws:iam::123456789012:role/SecondBrainTriggerRole

# Weekly digest
uv run trigger-digest trigger --digest-type weekly

# Force interactive mode
uv run trigger-digest trigger --interactive
```

Options:
- `-t, --digest-type`: `daily` or `weekly`
- `-f, --function-name`: Lambda function name (auto-detected)
- `--role-arn`: Role ARN to assume (auto-detected if `TriggerRoleArn` output exists)
- `-i, --interactive`: Force interactive prompts

Using `--role-arn` uses STS AssumeRole for temporary credentials with scoped permissions.

Configure `AWS_REGION` and `AWS_PROFILE` in `.env.local` (see Environment Variables section).

### Categories

The AI classifies messages into four categories:

- **People**: Contacts, relationships, personal notes
- **Projects**: Work initiatives, goals, deliverables
- **Ideas**: Creative thoughts, concepts, brainstorming
- **Admin**: Scheduling, logistics, maintenance tasks

## 🔧 Configuration

### Environment Variables

| Variable               | Description                        | Required |
|------------------------|------------------------------------|----------|
| `ANTHROPIC_API_KEY`    | Claude API key                     | ✅        |
| `OPENAI_API_KEY`       | OpenAI API key (fallback)          | ✅        |
| `TELEGRAM_BOT_TOKEN`   | Bot token from BotFather           | ✅        |
| `TELEGRAM_SECRET_TOKEN`| Webhook verification secret        | ✅        |
| `USER_CHAT_ID`         | Your Telegram chat ID for digests  | ✅        |
| `DDB_TABLE_NAME`       | DynamoDB table name (auto-set)     | ❌        |
| `BEDROCK_REGION`       | AWS region for Bedrock (optional)  | ❌        |

### CDK Stack Customization

Edit `packages/cdk/src/cdk/second_brain/second_brain_stack.py` to modify:

- Schedule times (daily/weekly digests)
- Lambda memory allocation
- AWS region
- IAM permissions

## 🐛 Troubleshooting

### Common Issues

**Webhook 400 Error**
```
Solution: Check bot token, verify Lambda URL is accessible, ensure no trailing slashes
```

**AI Classification Fails**
```
Solution: Verify API keys are valid, check network connectivity, try different provider
```

**No Digest Messages**
```
Solution: Verify chat ID, check CloudWatch logs, ensure EventBridge rules are active
```

**Python Version Issues**
```
Solution: Ensure Python 3.12 is available
python3 --version  # Should show 3.12.x
```

**DynamoDB Permission Errors**
```
Solution: Check IAM policies, ensure Lambda has proper table access
```

### Cost Estimation

- **DynamoDB**: $0-2/month (pay-per-request)
- **Lambda**: $0-1/month (1M free requests)
- **API Calls**: $0-2/month (depends on usage)
- **Total**: Typically $0-5/month for personal use

## 🛠️ Development

### Project Structure

```
second-brain-telegram-aws/
├── pyproject.toml              # Workspace configuration
├── README.md
├── .env.local                  # Environment variables (gitignored)
├── packages/
│   ├── cdk/                   # AWS CDK infrastructure
│   │   └── src/cdk/
│   │       ├── app.py         # CDK entry point
│   │       └── second_brain/
│   │           └── second_brain_stack.py
│   ├── common/                # Shared utilities
│   │   └── src/common/
│   │       └── environments.py
│   ├── lambdas/               # Lambda functions
│   │   └── src/lambdas/
│   │       ├── processor.py   # Telegram webhook handler
│   │       └── digest.py      # Scheduled digest generator
│   └── scripts/               # CLI tools
│       └── src/scripts/
│           ├── setup_webhook.py
│           ├── cdkw.py
│           └── tail_logs.py
```

### Development Commands

```bash
# Install/update dependencies
uv sync

# Run tests (if configured)
uv run pytest

# Format code
uv run black .

# Type checking
uv run mypy .
```

### Build System

This project uses **uv workspace** with **hatchling** for building:

- `pyproject.toml` defines workspace members
- Each package has its own `pyproject.toml` with dependencies
- CDK builds Lambda layer using Docker and uv

## 📚 Resources

- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/latest/guide/)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Anthropic Claude API](https://docs.anthropic.com/claude/reference/)
- [OpenAI API Documentation](https://platform.openai.com/docs/api-reference)
- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/)
- [Building a Second Brain](https://www.buildingasecondbrain.com/)

## 📄 License

MIT License - feel free to use and modify for your personal second brain.

---

**Happy capturing! 🎯** May your second brain help you think better and achieve more.
