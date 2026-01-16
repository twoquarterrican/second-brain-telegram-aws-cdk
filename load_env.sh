#!/bin/bash
# Load environment variables from env.local into current shell
# Usage: source scripts/load_env.sh

set -a
source "$(dirname "$0")/../packages/common/src/env.local"
set +a
