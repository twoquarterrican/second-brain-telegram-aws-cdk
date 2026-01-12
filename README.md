# 🧠 Second Brain with Telegram & AWS

A complete personal second brain system that captures thoughts via Telegram and processes them with AI, storing insights in DynamoDB with automated digest summaries.

Inspired by [Tiago Forte's Building a Second Brain](https://www.buildingasecondbrain.com/) and enhanced with 2026 AI capabilities. Watch [Why 2026 Is the Year to Build a Second Brain](https://youtu.be/0TpON5T-Sw4) by Nate B Jones.

## 🏗️ Architecture

```
┌─────────────┐    Webhook     ┌─────────────┐    AI API     ┌─────────────┐
│  Telegram   │ ──────────────► │  AWS Lambda │ ───────────► │ Claude/OpenAI │
│    Bot      │                │  Processor  │              │   (APIs)    │
└─────────────┘                └─────────────┘              └─────────────┘
                                        │
                                        ▼
                               ┌─────────────┐
                               │  DynamoDB    │
                               │  SecondBrain │
                               └─────────────┘
                                        ▲
                               Scheduled │  EventBridge
                                        ▼
                               ┌─────────────┐
                               │  AWS Lambda │ ──► Telegram
                               │   Digest     │      Chat
                               └─────────────┘
```

## 🚀 Features

- **Capture**: Send text messages to your personal Telegram bot
- **AI Classification**: Automatically categorizes thoughts into People/Projects/Ideas/Admin
- **Smart Extraction**: Extracts name, status, next actions, and notes with confidence scoring
- **Automated Digests**: Daily (8AM UTC) and weekly (Sunday 9AM UTC) summaries
- **Secure**: Webhook verification and secret token protection
- **Serverless**: Pay-per-use AWS infrastructure (typically $0-5/month)

## 📋 Prerequisites

- AWS account with appropriate permissions
- GitHub account with GitHub CLI (`gh`) installed and authenticated
- Python 3.12
- **uv** (modern Python package manager) installed
- AWS SAM CLI installed
- Telegram account

### Installing uv

```bash
# Install uv (Linux/macOS/Windows WSL)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or using pip
pip install uv

# Verify installation
uv --version
```

## 🛠️ Setup Instructions

### 1. Clone and Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/twoquarterrican/second-brain-telegram-aws.git
cd second-brain-telegram-aws

# Create and activate virtual environment with uv
uv sync

# Activate the virtual environment
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate     # Windows

# Install development dependencies (optional)
uv sync --group dev
```

### 2. Create Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` and follow instructions
3. Save your bot token (looks like `123456789:ABC...`)
4. Send `/setcommands` and configure commands:
   ```
   help - Get help information
   ```
5. Get your chat ID: Start a conversation with `@userinfobot`

### 2. Configure Environment Variables

Create a file `env.json` in the project root:

```json
{
  "AnthropicApiKey": "your_anthropic_api_key",
  "OpenaiApiKey": "your_openai_api_key", 
  "TelegramBotToken": "your_telegram_bot_token",
  "TelegramSecretToken": "your_random_secret_token",
  "UserChatId": "your_telegram_chat_id"
}
```

**API Keys**:
- **Anthropic Claude**: Get from [console.anthropic.com](https://console.anthropic.com/)
- **OpenAI**: Get from [platform.openai.com](https://platform.openai.com/)
- **Telegram Secret Token**: Generate a random secret string for webhook verification

### How to Generate Telegram Secret Token

The `TelegramSecretToken` is a security measure to verify that webhook requests actually come from Telegram. Generate it using one of these methods:

**Method 1: Using Python**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Method 2: Using OpenSSL**
```bash
openssl rand -base64 32
```

**Method 3: Using uuidgen**
```bash
uuidgen | tr -d '-'
```

**Method 4: Online generator**
- Visit [random.org](https://www.random.org/passwords/) and generate a 32-character random string

**Example secret token**: `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`

**Security Note**: Store these securely using AWS Secrets Manager in production. The secret token should be a unique random string that only your bot and Lambda function know.

### 4. Deploy with SAM

```bash
# Build the application (SAM will automatically use pyproject.toml dependencies)
sam build

# Deploy (follow prompts for parameters)
sam deploy --guided

# Save the configuration for future deployments
sam deploy
```

**Note**: AWS SAM automatically reads dependencies from `pyproject.toml`. No separate requirements.txt file needed!

### 4. Set Up Telegram Webhook

The easiest way to set up your webhook is using the interactive script:

```bash
# Launch interactive setup (recommended)
setup-webhook

# Alternative script names (all do the same thing)
webhook-setup
telegram-webhook
```

## CLI Commands

The webhook script now supports both CLI arguments and interactive prompts:

### Interactive Mode (Recommended)
```bash
# Launch interactive setup (default behavior)
setup-webhook

# Explicitly launch interactive mode
setup-webhook interactive
```

### Traditional CLI Mode
```bash
# Set webhook with parameters
setup-webhook set --token YOUR_TOKEN --auto-detect

# Get current webhook info
setup-webhook info --token YOUR_TOKEN

# Test bot connection
setup-webhook test --token YOUR_TOKEN

# Delete webhook
setup-webhook delete --token YOUR_TOKEN --force

# Show help
setup-webhook --help
setup-webhook set --help
```

### CLI Options
- `--token, -t`: Telegram bot token
- `--webhook-url, -w`: Webhook URL
- `--secret-token, -s`: Secret token for webhook verification
- `--function-name, -f`: AWS Lambda function name (default: SecondBrainProcessor)
- `--region, -r`: AWS region (default: us-east-1)
- `--auto-detect, -a`: Auto-detect webhook URL from AWS
- `--force, -f`: Skip confirmation (for delete command)

The interactive script will guide you through:
- **Auto-reading from env.json**: Detects if you have `TelegramBotToken` and `TelegramSecretToken` in your `env.json` file
- Entering your bot token manually (if not in env.json)
- Choosing to set, view, delete, or test the webhook
- Auto-detecting your Lambda function URL from AWS
- Generating a secure secret token for webhook verification
- Confirming the configuration before applying changes

#### env.json Support

The script automatically reads from your `env.json` file:

```json
{
  "TelegramBotToken": "123456789:ABC...",
  "TelegramSecretToken": "your_secret_token"
}
```

If these values are present, the script will ask if you want to use them, saving you from typing them manually!

#### Manual Setup (Advanced)

If you prefer manual setup:

```bash
# Get the function URL
aws lambda get-function-url-config --function-name SecondBrainProcessor

# Set webhook manually
curl -X POST "https://api.telegram.org/botYOUR_BOT_TOKEN/setWebhook" \
     -H "Content-Type: application/json" \
     -d '{"url": "YOUR_LAMBDA_URL", "secret_token": "YOUR_SECRET_TOKEN"}'
```

### 5. Test Your Bot

1. Send a test message to your bot: "Remember to call John about the project proposal tomorrow"
2. You should receive a confirmation message with the classification
3. Check DynamoDB table to see the stored item

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

### Categories

The AI classifies messages into four categories:

- **People**: Contacts, relationships, personal notes
- **Projects**: Work initiatives, goals, deliverables  
- **Ideas**: Creative thoughts, concepts, brainstorming
- **Admin**: Scheduling, logistics, maintenance tasks

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `ANTHROPIC_API_KEY` | Claude API key | ✅ |
| `OPENAI_API_KEY` | OpenAI API key (fallback) | ✅ |
| `TELEGRAM_BOT_TOKEN` | Bot token from BotFather | ✅ |
| `TELEGRAM_SECRET_TOKEN` | Webhook verification secret | ✅ |
| `USER_CHAT_ID` | Your Telegram chat ID for digests | ✅ |
| `DDB_TABLE_NAME` | DynamoDB table name (auto-set) | ❌ |
| `LOG_LEVEL` | Logging level (INFO/DEBUG) | ❌ |

### SAM Template Customization

Edit `template.yaml` to modify:
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
Solution: Verify API keys are valid, check network connectivity, try fallback API
```

**No Digest Messages**
```
Solution: Verify chat ID, check CloudWatch logs, ensure EventBridge rules are active
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

### Monitoring

Monitor via AWS CloudWatch:
- Lambda execution logs
- Error rates and timeouts
- DynamoDB consumption
- API call metrics

## 🛠️ Development

### Project Structure

```
second-brain-telegram-aws/
├── pyproject.toml           # Project metadata and dependencies
├── .venv/                   # Virtual environment (created by uv)
├── template.yaml            # AWS SAM template
├── processor/
│   └── app.py              # Telegram webhook processor
├── digest/
│   └── app.py              # Scheduled digest generator
├── scripts/
│   └── setup_webhook.py    # Webhook setup utility
└── README.md
```

### Development Commands

```bash
# Install/update dependencies
uv sync

# Run scripts in project context
setup-webhook           # Interactive webhook setup (default)
webhook-setup           # Same as above
telegram-webhook        # Same as above

# Install development tools
uv sync --group dev

# Format code with black
uv run black .

# Lint with ruff
uv run ruff check .

# Type check with mypy
uv run mypy .

# Run tests (when available)
uv run pytest
```

### Dependency Management

This project uses **uv** for modern Python dependency management:

- `pyproject.toml` contains all dependencies and project metadata
- `uv sync` creates a virtual environment and installs all dependencies
- Development tools are in `[project.optional-dependencies.dev]`
- No separate `requirements.txt` needed - SAM reads from `pyproject.toml`

## 🔄 Git Repository Setup

```bash
# Initialize git repository
git init
git add .
git commit -m "Initial second brain SAM project"

# Create GitHub repository
gh repo create second-brain-telegram-aws --public --push --source=.

# Or for private repository
gh repo create second-brain-telegram-aws --private --push --source=.
```

## 🚀 Extensions & Ideas

### Voice Transcription
Add support for voice notes using AWS Transcribe:

```python
# Add to processor/app.py
def transcribe_voice(file_id: str) -> str:
    # Download voice file from Telegram
    # Send to AWS Transcribe
    # Return transcribed text
```

### AWS Bedrock Integration
Replace external AI APIs with AWS Bedrock for better security and cost.

### Enhanced Categories
Add custom categories or let users define their own classification system.

### Web Dashboard
Create a simple web interface to browse and manage your second brain.

### Calendar Integration
Automatically create calendar events from items with dates/times.

## 📚 Resources

- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Anthropic Claude API](https://docs.anthropic.com/claude/reference/)
- [OpenAI API Documentation](https://platform.openai.com/docs/api-reference)
- [Building a Second Brain](https://www.buildingasecondbrain.com/)

## 📄 License

MIT License - feel free to use and modify for your personal second brain.

---

**Happy capturing! 🎯** May your second brain help you think better and achieve more.