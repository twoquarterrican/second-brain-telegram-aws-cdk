#!/usr/bin/env python3
"""
Simple CDK Deployment for Second Brain.
This script uses AWS CDK to synthesize and deploy the infrastructure.
It reads from env.json for configuration.
"""

import os
import sys
import subprocess
import json


def run_command(cmd, description):
    """Run a command and handle result."""
    print(f"🔧 {description}")
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        return False


def check_env():
    """Check if env.json exists and has required fields."""
    env_path = "env.json"
    
    if not os.path.exists(env_path):
        print(f"❌ {env_path} not found!")
        print("Create {env_path} with:")
        print("""{
  "AnthropicApiKey": "-",
  "OpenaiApiKey": "-",
  "TelegramBotToken": "",
  "TelegramSecretToken": "",
  "UserChatId": ""
}""")
        return False
    
    try:
        with open(env_path, 'r') as f:
            env = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"❌ Failed to read {env_path}: {e}")
        return False
    
    # Check required fields
    required = ["TelegramBotToken", "TelegramSecretToken", "UserChatId"]
    missing = [field for field in required if not env.get(field)]
    
    if missing:
        print(f"❌ Missing required fields: {', '.join(missing)}")
        return False
    
    print("✅ Environment file is valid")
    
    # Check API keys
    has_anthropic = env.get("AnthropicApiKey", "-") not in ["-", None]
    has_openai = env.get("OpenaiApiKey", "-") not in ["-", None]
    
    if not has_anthropic and not has_openai:
        print("⚠️ Warning: No AI API keys configured")
        print("   At least one of AnthropicApiKey or OpenaiApiKey should be configured")
    else:
        print(f"✅ AI providers configured: Anthropic={has_anthropic}, OpenAI={has_openai}")
    
    return True


def deploy_stack():
    """Deploy the Second Brain stack using CDK."""
    print("🚀 Deploying Second Brain stack with CDK...")
    
    # Check environment first
    if not check_env():
        return False
    
    # Synthesize CloudFormation
    if not run_command(["cd", "cdk_app"], "Synthesize CDK templates"):
        return False
    
    # Deploy (non-interactive)
    if not run_command(["cd", "cdk_app"], 'Deploy stack", 
                   "cdk deploy SecondBrainStack --no-interactive",
                   "--require-approval never",
                   "--parameters-file", "cdk_app/cdk.context.json"):
        return False
    
    print("✅ Deployment completed!")
    print("📋 Check outputs with: aws cloudformation describe-stacks --stack-name SecondBrainStack")
    return True


def show_stack_info():
    """Show current stack information."""
    run_command(["aws", "cloudformation", "describe-stacks", "--stack-name", "SecondBrainStack"], 
               "Show stack information")


def bootstrap_cdk():
    """Bootstrap CDK environment."""
    print("🔧 Bootstrapping CDK environment...")
    
    if not run_command(["npm", "install", "-g", "aws-cdk@2.80.0"], "Install AWS CDK"):
        return False
    
    if not run_command(["cdk", "cdk_app"], "bootstrap"], "Bootstrap CDK"):
        return False
    
    print("✅ CDK bootstrap completed!")
    return True


def main():
    """Main deployment script."""
    if len(sys.argv) == 1:
        command = sys.argv[0]
    else:
        command = "deploy"
    
    print(f"🚀 Second Brain CDK Deployment")
    print("=" * 40)
    
    if command == "synth":
        return run_command(["cd", "cdk_app"], "Synthesize CDK templates")
    elif command == "deploy":
        return deploy_stack()
    elif command == "info":
        return show_stack_info()
    elif command == "bootstrap":
        return bootstrap_cdk()
    elif command == "deploy":
        return deploy_stack()
    elif command == "help":
        print("""
Available commands:
  synth       - Synthesize CloudFormation templates
  deploy      - Deploy stack
  info       - Show stack information
  bootstrap   - Bootstrap CDK environment
  help       - Show this help message
        """)
        return True
    else:
        print(f"❌ Unknown command: {command}")
        print("Use 'deploy', 'synth', 'info', or 'bootstrap'")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)