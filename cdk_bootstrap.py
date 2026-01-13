#!/usr/bin/env python3
"""
Second Brain CDK Bootstrap Script.
Run with: python cdk_bootstrap.py
"""

import subprocess
import sys
import os
from pathlib import Path


def run_command(cmd, description):
    """Run command and handle errors."""
    print(f"🔧 {description}")
    try:
        result = subprocess.run(
            cmd, shell=True, check=True, capture_output=True, text=True
        )
        print(f"✅ {description} completed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        print(f"Output: {e.output}")
        return False


def main():
    """Bootstrap the Second Brain CDK project."""
    print("🚀 Bootstrapping Second Brain CDK Project")
    print("=" * 50)

    # Check if uv is available
    try:
        subprocess.run(["uv", "--version"], check=True, capture_output=True)
        print("✅ uv found")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ uv not found. Please install uv:")
        print("curl -LsSf https://astral.sh/uv/install.sh | sh")
        sys.exit(1)

    # Check if CDK is available
    try:
        subprocess.run(["cdk", "--version"], check=True, capture_output=True)
        print("✅ AWS CDK found")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ AWS CDK not found. Installing CDK...")
        if not run_command("npm install -g aws-cdk", "Install AWS CDK"):
            sys.exit(1)

    # Install CDK Python dependencies
    if not run_command(
        "uv add --dev aws-cdk-lib constructs aws-cdk", "Install CDK dependencies"
    ):
        sys.exit(1)

    # Initialize CDK app structure
    print("🏗️ Creating CDK project structure...")

    # Create directories
    dirs_to_create = [
        "cdk_app",
        "cdk_app/second_brain",
        "cdk_app/second_brain/constructs",
        "cdk_app/second_brain/lambdas",
        "cdk_app/second_brain/lambdas/processor",
        "cdk_app/second_brain/lambdas/digest",
    ]

    for dir_path in dirs_to_create:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        print(f"📁 Created directory: {dir_path}")

    print("✅ CDK project structure created")
    print("\n🎯 Next steps:")
    print("1. cd cdk_app")
    print("2. cdk bootstrap")
    print("3. cdk deploy")
    print("\n📋 See README_CDK.md for detailed instructions")


if __name__ == "__main__":
    main()
