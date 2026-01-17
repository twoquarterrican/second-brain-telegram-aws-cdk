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
    BundlingOptions,
)
import os
from pathlib import Path
from constructs import Construct
from common.environments import layer_dir, lambdas_dir, lambdas_src_dir, common_dir


class SecondBrainStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        code = _lambda.Code.from_asset(lambdas_src_dir().as_posix())
        # Layer will be built by CDK Docker build

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
        lambda_env = {
            "DDB_TABLE_NAME": table.table_name,
            "SECOND_BRAIN_TABLE_NAME": table.table_name,
        }
        for key in [
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_SECRET_TOKEN",
            "BEDROCK_REGION",
            "USER_CHAT_ID",
        ]:
            value = os.getenv(key)
            if value:
                lambda_env[key] = value

        # Create Lambda layer with dependencies
        lambdas_directory = lambdas_dir()
        common_directory = common_dir()

        # noinspection PyTypeChecker
        dependencies_layer = _lambda.LayerVersion(
            scope=self,
            id="PythonDepsLayer",
            description="Lambda layer built from pyproject.toml using uv inside Docker",
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_12],
            code=_lambda.Code.from_asset(
                path=lambdas_directory.as_posix(),
                bundling=BundlingOptions(
                    image=_lambda.Runtime.PYTHON_3_12.bundling_image,
                    command=[
                        "bash",
                        "-c",
                        "pip install uv && uv pip install --requirements pyproject.toml --target /asset-output/python && cp -r /common-src/src/common /asset-output/python/",
                    ],
                    user="root",
                    volumes=[
                        {
                            "hostPath": common_directory.as_posix(),
                            "containerPath": "/common-src",
                        },
                    ],
                ),
            ),
        )

        # Allow Bedrock InvokeModel for Titan embeddings (primary) and other models (fallback)
        invoke_model = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "bedrock:InvokeModel",
                "bedrock:ListFoundationModels",
            ],
            resources=[
                "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v1",
            ],
        )
        # noinspection PyTypeChecker
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
            initial_policy=[
                invoke_model,
            ],
        )
        table.grant_read_write_data(processor_lambda)

        # Enable Function URL for Processor
        function_url = processor_lambda.add_function_url(
            auth_type=_lambda.FunctionUrlAuthType.NONE,
        )
        # Digest Lambda
        # noinspection PyTypeChecker
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
            initial_policy=[invoke_model],
        )
        table.grant_read_write_data(digest_lambda)

        # Task Linker Lambda
        # noinspection PyTypeChecker
        task_linker_lambda = _lambda.Function(
            self,
            "TaskLinkerLambda",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="lambdas.task_linker.linker.handler",
            code=code,
            environment=lambda_env,
            timeout=Duration.seconds(30),
            memory_size=256,
            layers=[dependencies_layer],
            initial_policy=[invoke_model],
        )
        table.grant_read_write_data(task_linker_lambda)

        # EventBridge Rule for Daily Digest (8 AM UTC)
        daily_rule = events.Rule(
            self,
            "DailyDigestRule",
            schedule=events.Schedule.cron(minute="0", hour="8"),
            description="Trigger daily digest at 8 AM UTC",
        )
        # noinspection PyTypeChecker
        daily_rule.add_target(targets.LambdaFunction(digest_lambda))

        # EventBridge Rule for Weekly Digest (Sundays at 9 AM UTC)
        weekly_rule = events.Rule(
            self,
            "WeeklyDigestRule",
            schedule=events.Schedule.cron(minute="0", hour="9", week_day="SUN"),
            description="Trigger weekly digest on Sundays at 9 AM UTC",
        )
        # noinspection PyTypeChecker
        weekly_rule.add_target(targets.LambdaFunction(digest_lambda))

        # Role for triggering lambdas (assumed by scripts/automation)
        trigger_role = self._create_trigger_role(
            processor_lambda,
            digest_lambda,
            task_linker_lambda,
            table,
        )

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
        CfnOutput(
            self,
            "TriggerRoleArn",
            value=trigger_role.role_arn,
            description="ARN of role for triggering lambdas (for scripts)",
        )

    def _create_trigger_role(
        self,
        processor_lambda: _lambda.Function,
        digest_lambda: _lambda.Function,
        task_linker_lambda: _lambda.Function,
        table: dynamodb.Table,
    ) -> iam.Role:
        """Create a role that can be assumed to invoke lambdas."""

        trust_account = os.getenv("TRIGGER_ROLE_TRUST_ACCOUNT", self.account)

        trigger_role = iam.Role(
            self,
            "TriggerRole",
            role_name="SecondBrainTriggerRole",
            assumed_by=iam.AccountPrincipal(trust_account),
            description="Role for triggering Second Brain Lambda functions",
        )

        trigger_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["lambda:InvokeFunction"],
                resources=[
                    processor_lambda.function_arn,
                    digest_lambda.function_arn,
                    task_linker_lambda.function_arn,
                ],
            )
        )

        # Allow Bedrock InvokeModel for Titan embeddings (backfill and Lambda use)
        trigger_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["bedrock:InvokeModel", "bedrock:ListFoundationModels"],
                resources=[
                    "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v1",
                ],
            )
        )

        # Allow DynamoDB operations for backfill and task linking
        trigger_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:Scan",
                    "dynamodb:Query",
                    "dynamodb:UpdateItem",
                    "dynamodb:GetItem",
                ],
                resources=[
                    table.table_arn,
                    f"{table.table_arn}/index/*",
                ],
            )
        )

        return trigger_role
