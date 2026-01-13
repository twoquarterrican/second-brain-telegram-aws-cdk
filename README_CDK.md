# Second Brain with AWS CDK

This is the AWS CDK version of the Second Brain Telegram application. CDK provides better infrastructure management, type safety, and easier debugging compared to SAM.

## Why CDK over SAM?

- **Type Safety**: Python classes instead of YAML
- **Better Debugging**: IDE support, breakpoints
- **Infrastructure as Code**: Real programming language
- **Easier Testing**: Unit tests for infrastructure
- **Cleaner Syntax**: Python > YAML for complex infrastructure
- **Version Control**: Proper diff and merging

## Quick Start

### 1. Install Dependencies
```bash
# Install CDK dependencies
uv sync --group dev

# Install AWS CDK globally (if not already installed)
npm install -g aws-cdk
```

### 2. Bootstrap CDK (one-time setup)
```bash
cd cdk_app
cdk bootstrap
```

### 3. Set up Secrets
```bash
# Configure your secrets in env.json
cp env.json.example env.json
# Edit env.json with your actual values

# Store secrets to Parameter Store
uv run scripts/secrets.py store
```

### 4. Deploy
```bash
cd cdk_app

# Deploy the stack
cdk deploy

# Or with specific parameters
cdk deploy --parameters AnthropicApiKey=your_key
```

## Development Workflow

### Local Development
```bash
cd cdk_app

# Synthesize CloudFormation template (dry run)
cdk synth

# Local testing
cdk local invoke SecondBrainStack/ProcessorLambda -e ../events/test-event.json
```

### Making Changes
1. Modify infrastructure in `cdk_app/app.py`
2. Update Lambda functions as needed
3. Run `cdk diff` to see changes
4. Run `cdk deploy` to apply changes

## Project Structure

```
second-brain-telegram-aws/
├── cdk_app/                  # CDK application
│   ├── app.py              # CDK stack definition
│   └── main.py            # CDK entry point
├── processor/                # Processor Lambda code
│   └── app.py             # Lambda handler
├── digest/                  # Digest Lambda code  
│   └── app.py             # Lambda handler
├── scripts/                 # Utility scripts
│   ├── secrets.py          # Secret management
│   └── setup_webhook.py   # Webhook setup
├── cdk.out/               # Synthesized CloudFormation (generated)
└── env.json               # Your configuration
```

## CDK vs SAM Comparison

| Feature | SAM | CDK |
|---------|------|------|
| Language | YAML | Python |
| Type Safety | ❌ | ✅ |
| IDE Support | ❌ | ✅ |
| Testing | Hard | Easy |
| Debugging | ❌ | ✅ |
| Reusability | Limited | ✅ |
| Version Control | YAML diff | Code diff |

## Environment Variables

All configuration is managed through:
- **env.json**: Local development configuration
- **AWS Parameter Store**: Production secrets (via `scripts/secrets.py`)
- **CDK Parameters**: Deployment-time values

## Commands

```bash
# Core CDK commands
cdk synth          # Generate CloudFormation
cdk deploy         # Deploy stack
cdk destroy        # Destroy stack
cdk diff           # Show changes
cdk bootstrap       # One-time setup

# Utility scripts  
uv run scripts/secrets.py list     # List secrets
uv run scripts/secrets.py store    # Store secrets
uv run setup-webhook               # Setup Telegram webhook
```

## Migration from SAM

If migrating from the SAM version:

1. **Infrastructure**: Handled automatically by CDK
2. **Lambda Code**: No changes required  
3. **Secrets**: Same process with `scripts/secrets.py`
4. **Deployment**: `cdk deploy` instead of `sam deploy`

## Troubleshooting

### CDK Bootstrap Issues
```bash
# Ensure AWS CLI is configured
aws sts get-caller-identity

# Bootstrap with explicit account/region
cdk bootstrap aws://ACCOUNT_ID/REGION
```

### Parameter Resolution
CDK uses the same Parameter Store approach as SAM:
- Optional AI keys default to "-"
- Required keys must have real values
- Runtime validation checks for valid keys

### Local Testing
```bash
# Invoke Lambda locally with test event
cdk local invoke SecondBrainStack/ProcessorLambda -e ../events/test-event.json

# Start local API Gateway (if applicable)
cdk local start-api
```

## Benefits of CDK

1. **Programmatic Infrastructure**: Use loops, conditions, functions
2. **Type Safety**: Catch errors at compile time, not deploy time
3. **Better Testing**: Unit test infrastructure code
4. **Cleaner Dependencies**: Python package management vs CLI tools
5. **IDE Integration**: Autocomplete, refactoring tools
6. **Reusable Constructs**: Share infrastructure patterns
7. **Language Familiarity**: Use Python you already know

## Next Steps

1. `cd cdk_app` - Start working with CDK
2. `cdk synth` - Review generated CloudFormation
3. `cdk bootstrap` - One-time setup
4. `cdk deploy` - Deploy your stack
5. `uv run scripts/secrets.py store` - Configure secrets

Welcome to the cleaner, safer, and more maintainable way to do AWS infrastructure! 🚀