# AWS Bedrock Integration

This document explains the AWS Bedrock integration added to the Second Brain Lambda processor.

## Overview

The processor now supports AWS Bedrock as a third AI provider for message classification, alongside Anthropic Claude and OpenAI GPT.

## Architecture

```
Telegram Message
       ↓
   Classification Logic
       ↓
┌─────────────────┬─────────────────┐
│  Anthropic     │  OpenAI        │  Bedrock      │
│   (Direct)     │   (Direct)     │   (via AWS)  │
│     Claude       │     GPT        │     Claude     │
└─────────────────┴─────────────────┘
       ↓ (Fallback Chain)
```

## Configuration

### Environment Variables

Add these to your environment or `env.json`:

```bash
# Existing variables
ANTHROPIC_API_KEY=your_anthropic_key
OPENAI_API_KEY=your_openai_key
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_SECRET_TOKEN=your_webhook_secret
USER_CHAT_ID=your_chat_id

# New Bedrock variable
BEDROCK_REGION=us-east-1  # Optional, defaults to us-east-1
```

### AWS IAM Permissions

Your Lambda execution role needs these permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:ListFoundationModels"
            ],
            "Resource": "*"
        }
    ]
}
```

## Bedrock Models Supported

Currently configured for:
- **Claude 3 Haiku** (`anthropic.claude-3-haiku-20240307-v1:0`)
- Temperature: 0.1
- Max tokens: 500

## Implementation Details

### Classification Flow

1. **Primary**: Anthropic Claude (direct API)
2. **Secondary**: OpenAI GPT (fallback)
3. **Tertiary**: AWS Bedrock Claude (AWS native)

### Bedrock Integration

```python
def classify_with_bedrock(message: str) -> Optional[Dict[str, Any]]:
    """Classify message using AWS Bedrock."""
    import boto3
    
    # Create Bedrock client
    bedrock = boto3.client('bedrock-runtime')
    
    # Use Anthropic Claude via Bedrock
    response = bedrock.converse(
        modelId='anthropic.claude-3-haiku-20240307-v1:0',
        messages=[
            {
                "role": "user",
                "content": CLASSIFICATION_PROMPT.format(message=message)
            }
        ],
        maxTokens=500,
        temperature=0.1,
    )
    
    # Extract and parse response
    content = response['output']['message']['content']
    if content.startswith("```json"):
        content = content[7:-3].strip()
    
    return json.loads(content)
```

## Benefits

### Cost Efficiency
- **No additional API costs** for Bedrock if you have AWS enterprise agreement
- **Same model capabilities** - Claude 3 Haiku on all platforms
- **Consistent responses** - Same classification logic across providers

### Reliability
- **Three-tier fallback** - If one provider fails, tries the next
- **AWS native integration** - Uses AWS SDK for Bedrock calls
- **No external dependencies** for Bedrock (boto3 already included)

### Security
- **No API keys in code** - Uses AWS IAM permissions
- **VPC-friendly** - Stays within AWS network
- **Audit trail** - All calls logged in CloudTrail

## Usage

### Automatic Fallback
The system automatically tries providers in this order:
1. Anthropic Claude (if `ANTHROPIC_API_KEY` set)
2. OpenAI GPT (if `OPENAI_API_KEY` set and Anthropic fails)
3. Bedrock Claude (if `BEDROCK_REGION` set and others fail)

### Manual Provider Selection
You can control which provider is used by setting environment variables:

```bash
# Use only Bedrock
unset ANTHROPIC_API_KEY
unset OPENAI_API_KEY
export BEDROCK_REGION=us-east-1

# Use only Anthropic
export ANTHROPIC_API_KEY=your_key
unset OPENAI_API_KEY
unset BEDROCK_REGION
```

## Monitoring

Each classification attempt is logged:

```python
logger.info(f"Anthropic classification: {result}")
logger.info(f"OpenAI classification: {result}")  
logger.info(f"Bedrock classification: {result}")
```

## Troubleshooting

### Bedrock Not Working
1. **Check IAM permissions**: Ensure Lambda role has `bedrock:InvokeModel`
2. **Verify region**: Confirm `BEDROCK_REGION` is set correctly
3. **Test manually**: Use AWS CLI to test Bedrock access

```bash
aws bedrock invoke-model \
  --model-id anthropropic.claude-3-haiku-20240307-v1:0 \
  --body '{"input": {"text": "Hello world"}}'
```

### Classification Failures
- **Low confidence**: Check if message is clear and specific
- **JSON parsing errors**: Verify prompt format and response structure
- **Timeouts**: Increase Lambda timeout if needed (currently 30 seconds)

## Future Enhancements

- **Model selection**: Choose different Bedrock models
- **Streaming responses**: For faster responses
- **Custom prompts**: Per-category classification prompts
- **Metrics**: Track classification accuracy by provider