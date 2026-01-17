#!/usr/bin/env python3
"""
CDK wrapper for Second Brain project
Usage: uv run cdkw [cdk_args...]
"""

import subprocess
import sys
from pathlib import Path

from common.environments import cdk_src_dir, layer_dir


def run_cdk(cdk_args):
    """Run CDK with provided arguments"""
    print(f"🚀 Running CDK with args: {' '.join(cdk_args)}")

    # Run CDK command
    cmd = ["cdk"] + cdk_args
    result = subprocess.run(cmd, cwd=cdk_dir())

    return result.returncode == 0


def deploy_main():
    """Main entry point"""
    # Parse arguments: everything after script name goes to CDK
    if len(sys.argv) < 2:
        print("Usage: uv run deploy <cdk_command> [cdk_options...]")
        print("Examples:")
        print("  uv run deploy deploy")
        print("  uv run deploy synth")
        print("  uv run deploy diff")
        print("  uv run deploy destroy")
        return 1

    cdk_args = sys.argv[1:]

    # Step 1: Build layer
    if not build_layer():
        print("❌ Failed to build layer, aborting CDK deployment")
        return 1

    # Step 2: Run CDK
    if not run_cdk(cdk_args):
        print(f"❌ CDK command failed: {' '.join(cdk_args)}")
        return 1

    print(f"✅ CDK command completed successfully: {' '.join(cdk_args)}")
    return 0


def wrapper():
    """Wrapper method that calls cdk, passing through all arguments"""
    print(f"🚀 Running CDK with args: {' '.join(sys.argv[1:])}")

    # Run CDK command with all arguments
    cmd = ["cdk"] + sys.argv[1:]
    result = subprocess.run(cmd, cwd=cdk_src_dir())

    return result.returncode == 0


if __name__ == "__main__":
    # Check if called as wrapper (no specific command)
    if len(sys.argv) == 1 or (len(sys.argv) > 1 and sys.argv[1] == "wrapper"):
        exit(0 if wrapper() else 1)
    else:
        exit(deploy_main())
