#!/bin/bash
# Load environment variables from env.local into current shell
# Usage: source load_env.sh

set -e
eval "$(uv run load-env)"
