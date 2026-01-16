#!/bin/bash
# Assume SecondBrainTriggerRole and export temporary credentials
# Usage: source assume_role.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
eval "$(python "$SCRIPT_DIR/packages/scripts/src/scripts/assume_role.py" "$@")"
