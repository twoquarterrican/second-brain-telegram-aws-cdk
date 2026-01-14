from aws_cdk import (
    Duration,
    Stack,
    aws_lambda as _lambda,
    aws_dynamodb as dynamodb,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    CfnOutput,
    RemovalPolicy,
)
from pathlib import Path
from constructs import Construct
from cdk.build_layer import build_lambda_layer
from common.environments import layer_dir, lambdas_src_dir, load_env_config


class SecondBrainStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        code = _lambda.Code.from_asset(lambdas_src_dir().as_posix())
        build_lambda_layer()

        # DynamoDB Table
        table = dynamodb.Table(
            self,
            "SecondBrainTable",
            table_name="SecondBrain",
            partition_key=dynamodb.Attribute(
                name="PK", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(name="SK", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # GSI for status queries
        table.add_global_secondary_index(
            index_name="StatusIndex",
            partition_key=dynamodb.Attribute(
                name="status", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="created_at", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # Environment variables for Lambdas
        local_env = load_env_config()
        lambda_env = {
            "DDB_TABLE_NAME": table.table_name,
            "ANTHROPIC_API_KEY": local_env.get("AnthropicApiKey", ""),
            "OPENAI_API_KEY": local_env.get("OpenAIApiKey", ""),
            "TELEGRAM_BOT_TOKEN": local_env.get("TelegramBotToken", ""),
            "TELEGRAM_SECRET_TOKEN": local_env.get("TelegramSecretToken", ""),
            "BEDROCK_REGION": local_env.get("BedrockRegion", ""),
            "USER_CHAT_ID": local_env.get("UserChatId", ""),
        }

        # Create Lambda layer with dependencies
        layer_path = layer_dir()

        dependencies_layer = _lambda.LayerVersion(
            self,
            "DependenciesLayer",
            code=_lambda.Code.from_asset(str(layer_path)),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_12],
            description="Dependencies for Second Brain Lambda functions",
            layer_version_name="second-brain-deps",
        )

        # Processor Lambda
        processor_lambda = _lambda.Function(
            self,
            "ProcessorLambda",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="lambdas.processor.handler",
            code=code,
            environment=lambda_env,
            timeout=Duration.seconds(30),
            memory_size=256,
            layers=[dependencies_layer],
        )

        # Enable Function URL for Processor
        function_url = processor_lambda.add_function_url(
            auth_type=_lambda.FunctionUrlAuthType.NONE
        )

        # Digest Lambda
        digest_lambda = _lambda.Function(
            self,
            "DigestLambda",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="lambdas.digest.handler",
            code=code,
            environment=lambda_env,
            timeout=Duration.minutes(5),
            memory_size=512,
            layers=[dependencies_layer],
        )

        # Grant DynamoDB permissions
        table.grant_read_write_data(processor_lambda)
        table.grant_read_write_data(digest_lambda)

        # EventBridge Rule for Daily Digest (8 AM UTC)
        daily_rule = events.Rule(
            self,
            "DailyDigestRule",
            schedule=events.Schedule.cron(minute="0", hour="8"),
            description="Trigger daily digest at 8 AM UTC",
        )
        daily_rule.add_target(targets.LambdaFunction(digest_lambda))

        # EventBridge Rule for Weekly Digest (Sundays at 9 AM UTC)
        weekly_rule = events.Rule(
            self,
            "WeeklyDigestRule",
            schedule=events.Schedule.cron(minute="0", hour="9", week_day="SUN"),
            description="Trigger weekly digest on Sundays at 9 AM UTC",
        )
        weekly_rule.add_target(targets.LambdaFunction(digest_lambda))

        # Outputs
        CfnOutput(
            self,
            "ProcessorFunctionUrl",
            value=function_url.url,
            description="URL for Telegram webhook",
        )
        CfnOutput(
            self, "TableName", value=table.table_name, description="DynamoDB table name"
        )
        CfnOutput(
            self,
            "DependenciesLayerArn",
            value=dependencies_layer.layer_version_arn,
            description="ARN of the dependencies layer",
        )
