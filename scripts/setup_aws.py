#!/usr/bin/env python3
"""
Setup AWS environment for Second Brain project
Configures AWS CLI with mtp-cdk profile and us-east-2 region
"""

import os
import subprocess
import sys


def set_aws_config():
    """Set AWS configuration for Second Brain project"""

    # Set AWS profile
    profile_cmd = "aws configure set profile mtp-cdk"
    try:
        subprocess.run(profile_cmd, check=True, capture_output=True)
        print("✅ Set AWS profile to 'mtp-cdk'")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error setting AWS profile: {e}")
        return False

    # Set AWS region
    region_cmd = "aws configure set region us-east-2"
    try:
        subprocess.run(region_cmd, check=True, capture_output=True)
        print("✅ Set AWS region to 'us-east-2'")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error setting AWS region: {e}")
        return False

    # Create/update .env file for the project
    env_file = ".env"
    env_content = f"""# AWS Configuration for Second Brain
AWS_PROFILE=mtp-cdk
AWS_REGION=us-east-2

# Run AWS CLI commands with this profile:
# aws --profile mtp-cdk [command]

# Example:
# aws --profile mtp-cdk cdk deploy
# aws --profile mtp-cdk logs tail /aws/lambda/ProcessorLambda --follow
# aws --profile mtp-cdk dynamodb describe-table --table-name SecondBrain
"""

    try:
        with open(env_file, "w") as f:
            f.write(env_content)
        print(f"✅ Created {env_file} with AWS configuration")
    except IOError as e:
        print(f"❌ Error creating {env_file}: {e}")
        return False

    return True


def update_gitignore():
    """Add .env to .gitignore if not present"""
    gitignore_path = ".gitignore"

    try:
        with open(gitignore_path, "r") as f:
            content = f.read()
    except IOError:
        content = ""

    if ".env" not in content and "DOTENV" not in content:
        try:
            with open(gitignore_path, "a") as f:
                f.write("\n# AWS Configuration\n.env\n.DOTENV\n")
            print("✅ Added .env to .gitignore")
        except IOError as e:
            print(f"❌ Error updating .gitignore: {e}")


def main():
    """Main setup function"""
    print("🔧 Setting up AWS environment for Second Brain project")
    print("─" * 50)

    if not set_aws_config():
        print("❌ Failed to set AWS configuration")
        sys.exit(1)

    update_gitignore()

    print("─" * 50)
    print("✅ AWS environment configured successfully!")
    print()
    print("📋 Next steps:")
    print("  1. Activate AWS profile:")
    print("     export AWS_PROFILE=mtp-cdk")
    print("  2. Deploy with CDK:")
    print("     uv run cdk deploy")
    print("  3. Setup webhook:")
    print("     uv run setup-webhook --auto-detect")
    print("  4. Tail logs:")
    print("     uv run tail-logs --lambda-name ProcessorLambda --follow")
    print()
    print("💡 To make this permanent, add to your shell profile:")
    print("     echo 'export AWS_PROFILE=mtp-cdk' >> ~/.bashrc")
    print("     echo 'export AWS_REGION=us-east-2' >> ~/.bashrc")


if __name__ == "__main__":
    main()
