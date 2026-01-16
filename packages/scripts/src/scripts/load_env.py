#!/usr/bin/env python3
"""
Load environment variables from env.local into current shell.
Usage: python load_env.py && source /dev/stdin <<< "$(python load_env.py)"

Or run directly to print export statements:
    eval "$(python load_env.py)"
"""

import os
from pathlib import Path


def main():
    env_path = Path(__file__).parents[3] / "common" / "src" / "env.local"

    if not env_path.exists():
        print(f"Error: {env_path} not found", file=sys.stderr)
        sys.exit(1)

    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            print(f'export {key}="{value}"')


if __name__ == "__main__":
    import sys

    main()
