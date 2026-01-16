#!/bin/bash
# Load environment variables from env.local into current shell
# Usage: source load_env.sh

set -a
source "$(pwd)/packages/common/src/env.local"
set +a
