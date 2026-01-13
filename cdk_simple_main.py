#!/usr/bin/env python3
"""
Very Simple CDK App for Second Brain.
No complex CDK imports - uses AWS CLI directly.
"""

import os
import sys
import subprocess
import json


def run_command(cmd, description):
    """Run command and show status."""
    print(f"🔧 {description}")
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {description} completed")
            return True
        else:
            print(f"❌ {description} failed: {result.stderr}")
            return False


def check_env():
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
    ai_keys_configured = []
    if env.get("AnthropicApiKey") not in ["-", None]:
        ai_keys_configured.append("Anthropic")
    if env.get("OpenaiApiKey") not in ["-", None]:
        ai_keys_configured.append("OpenAI")
    
    if ai_keys_configured:
        print(f"✅ AI providers: {', ', '.join(ai_keys_configured)}")
    else:
        print("⚠️ Warning: No AI API keys configured")
    return True
    
    return True


def bootstrap_cdk():
    """Bootstrap CDK environment."""
    print("🚀 Bootstrapping CDK...")
    
    if not check_env():
        return False
    
    # Install CDK if not available
    if not run_command(["npm", "-v"], "Check npm"):
        print("❌ npm not found, installing...")
        subprocess.run(["npm", "install", "-g", "aws-cdk"], shell=True)
    
    print("✅ CDK installation completed!")
    return True


def synthesize_cdk():
    """Synthesize CloudFormation template."""
    if not check_env():
        return False
    
    print("🏗️ Synthesizing...")
    
    # Synthesize using AWS CLI (avoids CDK Python package issues)
    if not run_command(["aws", "cloudformation", "synthesize", "--no-asset-bundle"], "Synthesize CloudFormation"):
        return False
    
    print("✅ Synthesis completed!")
    return True


def deploy_stack():
    """Deploy the stack using AWS CLI."""
    if not check_env():
        return False
    
    print("🚀 Deploying Second Brain stack...")
    
    if not run_command(["aws", "cloudformation", "deploy", "--stack-name", "SecondBrainStack", "--no-rollback-failure", "--no-eventbridge-failure", "--capabilities", "CAPABILITY_IAM"], "Deploy stack"):
        return False
    
    print("✅ Deployment completed!")
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
        print("  help   - Show this help message")
        return 0
    
    command = sys.argv[1] if len(sys.argv) > 1 else "help"
    
    if command == "synth":
        return synthesize_cdk()
    elif command == "deploy":
        return deploy_stack()
    elif command == "info":
        run_command(["aws", "cloudformation", "describe-stacks", "--stack-name", "SecondBrainStack"], "Show stack information")
        return True
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
        return True
    else:
        print(f"Unknown command: {command}")
        return 1


if __name__ == "__main__":
    main()