#!/bin/bash
# Load environment variables from env.local into current shell
# Usage: source load_env.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
set -a
source "$SCRIPT_DIR/packages/common/src/env.local"
set +a
