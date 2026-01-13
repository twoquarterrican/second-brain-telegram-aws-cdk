#!/usr/bin/env python3
"""
Very Simple CDK App for Second Brain - Avoids problematic APIs entirely.
Uses AWS CLI directly and simple constructs.
"""

import os
import sys

try:
    from aws_cdk import App, Duration
    from aws_cdk import CfnOutput
    from aws_cdk.aws_dynamodb import Table, Attribute, BillingMode, ProjectionType
except ImportError as e:
    print(f"❌ Failed to import aws_cdk: {e}")
    print("Install CDK:")
    print("1. npm install -g aws-cdk@2.80.0")
    print("2. pip install aws-cdk-lib constructs")
    print("3. python3 -m pip install aws-cdk-lib constructs")
    print("4. aws configure profile default")
    sys.exit(1)


class SecondBrainStack(Stack):
    """Second Brain CDK Stack - Simple version."""

    def __init__(self, scope, construct_id, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # Load environment from env.json
        env = self._load_env()

        # DynamoDB Table (simple construct, avoiding problematic APIs)
        second_brain_table = Table(
            self,
            "SecondBrainTable",
            table_name="SecondBrain",
            partition_key=Attribute(name="PK", type="STRING"),
            sort_key=Attribute(name="SK", type="STRING"),
            billing_mode=BillingMode.PAY_PER_REQUEST,
        )

        # Common environment variables
        common_env = {
            "DDB_TABLE_NAME": "SecondBrain",
            "LOG_LEVEL": "INFO",
        }

        # Processor Lambda
        processor_lambda = _lambda.Function(
            self,
            "ProcessorLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="app.lambda_handler",
            code=_lambda.Code.from_asset("../processor"),
            memory_size=256,
            timeout=Duration.seconds(30),
            environment=common_env
            | {
                "ANTHROPIC_API_KEY": env.get("AnthropicApiKey", "-"),
                "OPENAI_API_KEY": env.get("OpenaiApiKey", "-"),
                "TELEGRAM_BOT_TOKEN": env.get("TelegramBotToken", ""),
                "TELEGRAM_SECRET_TOKEN": env.get("TelegramSecretToken", ""),
            },
        )

        # Add Lambda URL for webhooks
        processor_lambda_url = _lambda.FunctionUrl(
            self,
            "ProcessorLambdaUrl",
            function=processor_lambda,
            auth_type=_lambda.FunctionUrlAuthType.NONE,
        )

        # Digest Lambda
        digest_lambda = _lambda.Function(
            self,
            "DigestLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="app.lambda_handler",
            code=_lambda.Code.from_asset("../digest"),
            memory_size=256,
            timeout=Duration.seconds(30),
            environment=common_env
            | {
                "ANTHROPIC_API_KEY": env.get("AnthropicApiKey", "-"),
                "OPENAI_API_KEY": env.get("OpenaiApiKey", "-"),
                "TELEGRAM_BOT_TOKEN": env.get("TelegramBotToken", ""),
                "USER_CHAT_ID": env.get("UserChatId", ""),
            },
        )

        # EventBridge Rules for scheduled digests
        # Daily digest at 8AM UTC
        daily_rule = Rule(
            self,
            "DailyDigestRule",
            schedule=Schedule.cron(
                minute="0", hour="8", month="*", week_day="*", year="*"
            ),
            targets=[digest_lambda],
        )

        # Weekly digest on Sundays at 9AM UTC
        weekly_rule = Rule(
            self,
            "WeeklyDigestRule",
            schedule=Schedule.cron(
                minute="0", hour="9", month="*", week_day="SUN", year="*"
            ),
            targets=[digest_lambda],
        )

        # Outputs
        CfnOutput(
            self,
            "ProcessorLambdaUrl",
            value=processor_lambda_url.url,
            description="URL for Telegram webhook",
        )

        CfnOutput(
            self,
            "SecondBrainTableName",
            value=second_brain_table.table_name,
            description="DynamoDB table name",
        )

    def _load_env(self) -> dict:
        """Load environment variables from env.json."""
        env_path = "../env.json"

        if not os.path.exists(env_path):
            print(f"❌ {env_path} not found!")
            print("Create {env_path} with your configuration:")
            print("""{
  "TelegramBotToken": "",
  "TelegramSecretToken": "",
  "UserChatId": "",
  "AnthropicApiKey": "-",
  "OpenaiApiKey": "-"
}""")
            sys.exit(1)

        try:
            with open(env_path, "r") as f:
                env_data = json.load(f)
            return env_data
        except (json.JSONDecodeError, FileNotFoundError, IOError) as e:
            print(f"❌ Failed to read {env_path}: {e}")
            sys.exit(1)

        # Validate required fields
        required_fields = ["TelegramBotToken", "TelegramSecretToken", "UserChatId"]
        missing = [
            field
            for field in required_fields
            if not env_data.get(field) or env_data.get(field) == ""
        ]

        if missing:
            print(f"❌ Missing required fields: {', '.join(missing)}")
            print(f"   Edit {env_path} and add missing fields")
            sys.exit(1)

        print("✅ Environment file is valid")
        return env_data


def main():
    """CDK entry point."""
    from aws_cdk import App

    app = App(outdir="cdk.out")
    SecondBrainStack(app, "SecondBrainStack")
    app.synth()


if __name__ == "__main__":
    main()
