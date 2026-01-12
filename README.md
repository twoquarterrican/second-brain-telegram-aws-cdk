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
- AWS SAM CLI installed
- Telegram account

## 🛠️ Setup Instructions

### 1. Create Telegram Bot

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

**Security Note**: Store these securely using AWS Secrets Manager in production.

### 3. Deploy with SAM

```bash
# Navigate to project directory
cd second-brain-telegram-aws

# Build the application
sam build

# Deploy (follow prompts for parameters)
sam deploy --guided

# Save the configuration for future deployments
sam deploy
```

### 4. Set Up Telegram Webhook

After deployment, get your Processor Lambda URL:

```bash
# Get the function URL (replace with your function name)
aws lambda get-function-url-config --function-name SecondBrainProcessor

# Or use the helper script
python scripts/setup_webhook.py --token YOUR_BOT_TOKEN --secret-token YOUR_SECRET_TOKEN
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