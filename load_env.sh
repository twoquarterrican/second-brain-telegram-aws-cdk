#!/bin/bash
# Load environment variables from env.local into current shell
# Usage: source load_env.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
eval "$(python "$SCRIPT_DIR/packages/scripts/src/scripts/load_env.py")"
