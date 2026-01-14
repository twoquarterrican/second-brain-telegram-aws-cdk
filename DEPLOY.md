# Deploy Script for Second Brain

This script combines Lambda layer building with CDK deployment.

## Usage

### Direct Execution
```bash
python deploy.py <cdk_command> [cdk_options...]
```

### UV Script Execution
```bash
uv run deploy <cdk_command> [cdk_options...]
```

## Examples

```bash
# Deploy the stack (builds layer first, then deploys)
uv run deploy deploy

# Synthesize CloudFormation template
uv run deploy synth

# Check for changes before deploying
uv run deploy diff

# Destroy the stack
uv run deploy destroy

# Deploy with specific profile
uv run deploy deploy --profile myprofile

# Deploy specific stack
uv run deploy deploy SecondBrainStack

# Watch for changes and auto-deploy
uv run deploy deploy --watch
```

## Workflow

1. **Build Layer**: Automatically clears existing layer and rebuilds with latest dependencies
2. **Run CDK**: Executes the specified CDK command with all provided options

## Benefits

- ✅ **Always fresh dependencies** - Layer is rebuilt every time
- ✅ **Single command** - No separate layer build step needed
- ✅ **All CDK options** - Pass any CDK arguments directly
- ✅ **Error handling** - Clear feedback on layer build failures

## Troubleshooting

### Layer Build Failures
If layer building fails, the script will abort before running CDK:
```bash
# Check lambdas dependencies
cat packages/lambdas/pyproject.toml

# Manually rebuild layer
python packages/cdk/build_layer.py
```

### CDK Not Found
Ensure CDK is installed and accessible in your PATH:
```bash
npm install -g aws-cdk
cdk --version
```

### Permission Issues
Make sure the deploy script is executable:
```bash
chmod +x deploy.py
```

The script provides a convenient one-command workflow for development and deployment.