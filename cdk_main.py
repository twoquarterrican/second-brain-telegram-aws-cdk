#!/usr/bin/env python3
"""
Very Simple CDK Deployment for Second Brain.
Uses AWS CLI directly instead of complex CDK imports.
"""

import os
import sys
import subprocess
import json


def run_cdk_command(cmd, description=""):
    """Run AWS CDK command and show status."""
    print(f"🔧 {description}")
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {description} succeeded")
            return True
        else:
            print(f"❌ {description} failed: {result.stderr}")
            return False


def check_environment():
    """Check if required tools are available."""
    print("🔍 Checking environment...")
    
    # Check AWS CLI
    if not run_cdk_command(["aws", "--version"], "Check AWS CLI version"):
        return False
    
    # Check CDK 
    if not run_cdk_command(["cdk", "--version"], "Check CDK version"):
        return False
    
    print("✅ AWS tools are available")
    return True


def check_env_json():
    """Check if env.json exists and has required fields."""
    if not os.path.exists("env.json"):
        print("❌ env.json not found!")
        print("Create env.json with:")
        print("""{
  "TelegramBotToken": "",
  "TelegramSecretToken": "",
  "UserChatId": "",
  "AnthropicApiKey": "-",
  "OpenaiApiKey": "-"
}""")
        return False
    
    try:
        with open("env.json", 'r') as f:
            env = json.load(f)
    except:
        print("❌ Failed to read env.json")
        return False
    
    # Check required fields
    required = ["TelegramBotToken", "TelegramSecretToken", "UserChatId"]
    missing = [field for field in required if not env.get(field) or env.get(field) == "-"]
    
    if missing:
        print(f"❌ Missing required fields: {', '.join(missing)}")
        print(f"   Edit env.json and add: {', ' / '.join(missing)}")
        return False
    
    print("✅ env.json is valid")
    print(f"   API Keys configured: Anthropic={env.get('AnthropicApiKey', '-') not in ['-', None]}, OpenAI={env.get('OpenaiApiKey', '-') not in ['-', None]}")
    return True


def bootstrap_cdk():
    """Bootstrap CDK environment."""
    print("🚀 Bootstrapping CDK...")
    
    if not check_environment():
        return False
    
    if not check_env_json():
        return False
    
    # Bootstrap CDK
    if not run_cdk_command(["cdk", "bootstrap"], "Bootstrap CDK"):
        return False
    
    print("✅ CDK bootstrap completed!")
    return True


def synthesize_cdk():
    """Synthesize CloudFormation template."""
    if not check_env_json():
        return False
    
    print("🏗 Synthesizing CloudFormation template...")
    if not run_cdk_command(["cdk", "synth", "--no-asset-bundle", "--no-progress"], "Synthesize CDK"):
        return False
    
    print("✅ CloudFormation template synthesized!")
    return True


def deploy_stack():
    """Deploy the stack using AWS CDK."""
    if not check_env_json():
        return False
    
    print("🚀 Deploying Second Brain stack...")
    
    if not run_cdk_command(["cdk", "deploy", "--require-approval-never"], "Deploy stack"):
        return False
    
    print("✅ Deployment completed!")
    return True


def show_stack_info():
    """Show current stack information."""
    if not run_cdk_command(["aws", "cloudformation", "describe-stacks", "--stack-name", "SecondBrainStack"], "Show stack info"):
        return False
    
    print("📋 Stack information displayed")
    return True


def main():
    """Main deployment script."""
    if len(sys.argv) < 2:
        print("Usage: python3 cdk_main.py [command]")
        print("")
        print("Available commands:")
        print("  synth    - Synthesize CloudFormation template")
        print("  deploy  - Deploy stack")
        print("  info   - Show stack information")
        print("  bootstrap - Bootstrap CDK environment")
        return 0
    
    command = sys.argv[1] if len(sys.argv) > 1 else "help"
    
    if command == "synth":
        return synthesize_cdk()
    elif command == "deploy":
        return deploy_stack()
    elif command == "info":
        return show_stack_info()
    elif command == "bootstrap":
        return bootstrap_cdk()
    elif command == "help":
        print("Second Brain CDK Deployment Script")
        print("")
        print("Commands:")
        print("  synth    - Synthesize CloudFormation template")
        print("  deploy  - Deploy stack")
        print("  info   - Show stack information")
        print("  bootstrap - Bootstrap CDK environment")
        print("")
        print("Example:")
        print("  # First deployment:")
        print("  python3 cdk_main.py synth")
        print("  python3 cdk_main.py deploy")
        print("")
        print("  # Or bootstrap:")
        print("  python3 cdk_main.py bootstrap")
        return 0
    else:
        print(f"Unknown command: {command}")
        return 1


if __name__ == "__main__":
    main()