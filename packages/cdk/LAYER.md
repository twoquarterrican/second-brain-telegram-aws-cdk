# Building Lambda Layers for Second Brain

This guide explains how to build and deploy Lambda layers for the Second Brain project.

## Overview

Lambda layers allow you to share dependencies across multiple Lambda functions. This project uses `uv` to assemble a layer containing dependencies from `packages/lambdas/pyproject.toml`.

## Building the Layer

### Prerequisites

- Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Ensure your Python version matches Lambda runtime (Python 3.12)

### Build Process

1. **Build the layer**:
   ```bash
   cd packages/cdk
   python build_layer.py
   ```

   This script:
   - Extracts dependencies from `lambdas/pyproject.toml`
   - Uses `uv pip install` to install them into `packages/cdk/layer/python/`
   - Creates the proper Lambda layer structure

2. **Deploy with CDK**:
   ```bash
   cd packages/cdk
   cdk deploy
   ```

   The CDK stack will:
   - Create a Lambda layer from the built layer directory
   - Attach the layer to both processor and digest Lambda functions
   - Output the layer ARN

## Layer Structure

```
packages/cdk/layer/
└── python/
    ├── boto3/
    ├── requests/
    ├── anthropic/
    └── openai/
```

## Dependencies Included

The layer includes these external dependencies from `lambdas/pyproject.toml`:
- `boto3>=1.26.0`
- `requests>=2.28.0`
- `anthropic>=0.3.0`
- `openai>=0.27.0`

## Benefits

- **Smaller deployment packages**: Lambda function code only contains business logic
- **Faster deployments**: Dependencies are cached in the layer
- **Shared dependencies**: Multiple functions use the same layer
- **Easier updates**: Update layer once, all functions benefit

## Troubleshooting

### Layer directory issues
The build script automatically clears and rebuilds the layer directory each time. If you encounter issues:
```bash
# Clean build
python build_layer.py

# Or rebuild from CDK directory
cd packages/cdk
python build_layer.py
```

### Import errors
If Lambda functions can't import dependencies:
1. Verify the layer was built correctly
2. Check Lambda runtime compatibility (Python 3.12)
3. Ensure dependencies are in `python/` subdirectory

### Updating dependencies
1. Modify `packages/lambdas/pyproject.toml`
2. Rebuild the layer: `python packages/cdk/build_layer.py`
3. Redeploy: `cdk deploy`

## CDK Integration

The CDK stack automatically:
- Detects if the layer directory exists
- Creates `LambdaLayerVersion` resource when available
- Attaches the layer to all Lambda functions
- Provides graceful fallback if layer is missing

See `packages/cdk/src/cdk/second_brain/second_brain_stack.py` for implementation details.