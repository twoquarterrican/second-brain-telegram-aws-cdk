#!/usr/bin/env python3
"""
Second Brain AWS CDK Application - Working Version with env.json.
"""

import os
import sys
import json

try:
    from aws_cdk import (
        Stack,
        Duration,
        aws_lambda as _lambda,
        CfnOutput,
        RemovalPolicy,
    )
    # Avoid using problematic dynamodb APIs that changed
except ImportError as e:
    print(f"❌ Failed to import aws_cdk: {e}")
    print("Make sure CDK packages are installed:")
    print("1. uv sync --group dev")
    print("2. Or install manually: pip install aws-cdk-lib constructs")
    sys.exit(1)


class SecondBrainStack(Stack):
    """Second Brain CDK Stack - reads from env.json."""

    def __init__(self, scope, construct_id, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # Load environment from env.json
        env = self._load_env()

        # Validate required fields
        required_fields = ["TelegramBotToken", "TelegramSecretToken", "UserChatId"]
        missing_fields = [field for field in required_fields if not env.get(field)]

        if missing_fields:
            print(
                f"❌ Missing required fields in env.json: {', '.join(missing_fields)}"
            )
            sys.exit(1)

        # DynamoDB Table using simple construct
        # This avoids the problematic TableV2 API
        from aws_cdk.aws_dynamodb import Table, Attribute, ProjectionType
        from aws_cdk.aws_events import Rule, Schedule, Target
        from aws_cdk.aws_dynamodb import GlobalSecondaryIndexProps

        second_brain_table = Table(
            self,
            "SecondBrainTable",
            table_name="SecondBrain",
            partition_key=Attribute(name="PK", type="STRING"),
            sort_key=Attribute(name="SK", type="STRING"),
            billing_mode=BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            global_secondary_indexes=[
                GlobalSecondaryIndexProps(
                    index_name="StatusIndex",
                    partition_key=Attribute(name="status", type="STRING"),
                    sort_key=Attribute(name="category", type="STRING"),
                    projection_type=ProjectionType.ALL,
                )
            ],
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
        from aws_cdk.aws_lambda import FunctionUrl, FunctionUrlAuthType

        processor_lambda_url = FunctionUrl(
            self,
            "ProcessorLambdaUrl",
            function=processor_lambda,
            auth_type=FunctionUrlAuthType.NONE,
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
        from aws_cdk.aws_events import Rule, Schedule, Target

        # Daily digest at 8AM UTC
        daily_rule = Rule(
            self,
            "DailyDigestRule",
            schedule=Schedule.cron(
                minute="0", hour="8", month="*", week_day="*", year="*"
            ),
            targets=[RuleTarget(handler=digest_lambda)],
        )

        # Weekly digest on Sundays at 9AM UTC
        weekly_rule = Rule(
            self,
            "WeeklyDigestRule",
            schedule=Schedule.cron(
                minute="0", hour="9", month="*", week_day="SUN", year="*"
            ),
            targets=[RuleTarget(handler=digest_lambda)],
        )

        # Weekly digest on Sundays at 9AM UTC
        weekly_rule = Rule(
            self,
            "WeeklyDigestRule",
            schedule=Schedule.cron(
                minute="0", hour="9", month="*", week_day="SUN", year="*"
            ),
            targets=[Target(handler=digest_lambda)],
        )

        # Show what's being loaded
        print(f"✅ Loaded configuration from env.json:")
        print(
            f"   Anthropic API Key: {'configured' if env.get('AnthropicApiKey', '-') not in [None, ''] else 'missing'}"
        )
        print(
            f"   OpenAI API Key: {'configured' if env.get('OpenaiApiKey', '-') not in [None, ''] else 'missing'}"
        )
        print(f"   Telegram Bot Token: {'✓' if env.get('TelegramBotToken') else '✗'}")
        print(f"   User Chat ID: {'✓' if env.get('UserChatId') else '✗'}")

        # Outputs
        CfnOutput(
            self,
            "ProcessorLambdaUrl",
            value=processor_lambda_url.function_url,
            description="URL for Telegram webhook",
        )

        CfnOutput(
            self,
            "SecondBrainTableName",
            value=second_brain_table.table_name,
            description="DynamoDB table name",
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
  "AnthropicApiKey": "-",
  "OpenaiApiKey": "-",
  "TelegramBotToken": "",
  "TelegramSecretToken": "",
  "UserChatId": ""
}""")
            sys.exit(1)

        try:
            with open(env_path, "r") as f:
                env_data = json.load(f)
            return env_data
        except (json.JSONDecodeError, FileNotFoundError, IOError) as e:
            print(f"❌ Failed to read {env_path}: {e}")
            sys.exit(1)


def main():
    """CDK entry point."""
    from aws_cdk import App

    app = App(outdir="cdk.out")
    SecondBrainStack(app, "SecondBrainStack")
    app.synth()


if __name__ == "__main__":
    main()
