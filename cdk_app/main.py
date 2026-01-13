#!/usr/bin/env python3
"""
Second Brain AWS CDK Application - Simplified Version.
"""


from aws_cdk import (
    CfnOutput,
    CfnParameter,
    Duration,
    Stack,
App,
)
from aws_cdk import (
    aws_dynamodb as dynamodb,
)
from aws_cdk import (
    aws_events as events,
)
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_lambda as _lambda,
)


class SecondBrainStack(Stack):
    """Second Brain CDK Stack."""

    def __init__(self, scope, construct_id, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # Parameters
        anthropic_api_key = CfnParameter(
            self,
            "AnthropicApiKey",
            type="String",
            description="Anthropic API key for Claude AI processing",
            no_echo=True,
            default="-",  # Default to non-existent
        )

        openai_api_key = CfnParameter(
            self,
            "OpenaiApiKey",
            type="String",
            description="OpenAI API key (fallback if Anthropic fails)",
            no_echo=True,
            default="-",  # Default to non-existent
        )

        telegram_bot_token = CfnParameter(
            self,
            "TelegramBotToken",
            type="String",
            description="Telegram bot token from BotFather",
            no_echo=True,
        )

        telegram_secret_token = CfnParameter(
            self,
            "TelegramSecretToken",
            type="String",
            description="Secret token for webhook verification",
            no_echo=True,
        )

        user_chat_id = CfnParameter(
            self,
            "UserChatId",
            type="String",
            description="Your personal Telegram chat ID for digest messages",
            no_echo=True,
        )

        # DynamoDB Table
        second_brain_table = dynamodb.Table(
            self,
            "SecondBrainTable",
            table_name="SecondBrain",
            partition_key=dynamodb.Attribute(
                name="PK", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(name="SK", type=dynamodb.AttributeType.STRING),
            billing=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=dynamodb.RemovalPolicy.DESTROY,
            global_secondary_indexes=[
                dynamodb.GlobalSecondaryIndexProps(
                    index_name="StatusIndex",
                    partition_key=dynamodb.Attribute(
                        name="status", type=dynamodb.AttributeType.STRING
                    ),
                    sort_key=dynamodb.Attribute(
                        name="category", type=dynamodb.AttributeType.STRING
                    ),
                    projection_type=dynamodb.ProjectionType.ALL,
                )
            ],
        )

        # Common environment variables
        common_env = {
            "DDB_TABLE_NAME": second_brain_table.table_name,
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
                "ANTHROPIC_API_KEY": anthropic_api_key.value_as_string,
                "OPENAI_API_KEY": openai_api_key.value_as_string,
                "TELEGRAM_BOT_TOKEN": telegram_bot_token.value_as_string,
                "TELEGRAM_SECRET_TOKEN": telegram_secret_token.value_as_string,
            },
            initial_policy=iam.PolicyDocument(
                statements=[
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "dynamodb:PutItem",
                            "dynamodb:GetItem",
                            "dynamodb:UpdateItem",
                            "dynamodb:DeleteItem",
                            "dynamodb:Query",
                            "dynamodb:Scan",
                        ],
                        resources=[second_brain_table.table_arn],
                    )
                ]
            ),
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
                "ANTHROPIC_API_KEY": anthropic_api_key.value_as_string,
                "OPENAI_API_KEY": openai_api_key.value_as_string,
                "TELEGRAM_BOT_TOKEN": telegram_bot_token.value_as_string,
                "USER_CHAT_ID": user_chat_id.value_as_string,
            },
            initial_policy=iam.PolicyDocument(
                statements=[
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=["dynamodb:GetItem", "dynamodb:Query", "dynamodb:Scan"],
                        resources=[second_brain_table.table_arn],
                    )
                ]
            ),
        )

        # EventBridge Rules for scheduled digests
        # Daily digest at 8AM UTC
        daily_rule = events.Rule(
            self,
            "DailyDigestRule",
            schedule=events.Schedule.cron(
                minute="0", hour="8", month="*", week_day="*", year="*"
            ),
            targets=[events.Target(handler=digest_lambda)],
        )

        # Weekly digest on Sundays at 9AM UTC
        weekly_rule = events.Rule(
            self,
            "WeeklyDigestRule",
            schedule=events.Schedule.cron(
                minute="0", hour="9", month="*", week_day="SUN", year="*"
            ),
            targets=[events.Target(handler=digest_lambda)],
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


def main():
    """CDK entry point."""
    app = App(outdir="cdk.out")
    SecondBrainStack(app, "SecondBrainStack")
    app.synth()


if __name__ == "__main__":
    main()
