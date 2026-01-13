from aws_cdk import (
    Duration,
    Stack,
    aws_lambda as _lambda,
    aws_dynamodb as dynamodb,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    CfnOutput,
    RemovalPolicy
)
from constructs import Construct
from typing import cast


class SecondBrainStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

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
            point_in_time_recovery=True,
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

# Lambda execution role - use default Lambda role
        lambda_role = None
            ],
        )

        # Grant DynamoDB permissions
        table.grant_read_write_data(lambda_role)

        # Environment variables for Lambdas
        lambda_env = {
            "DDB_TABLE_NAME": table.table_name,
        }

        # Processor Lambda
        processor_lambda = _lambda.Function(
            self,
            "ProcessorLambda",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="processor.handler",
            code=_lambda.Code.from_asset("lambda"),
            environment=lambda_env,
            timeout=Duration.seconds(30),
            memory_size=256,
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
            handler="digest.handler",
            code=_lambda.Code.from_asset("lambda"),
            environment=lambda_env,
            timeout=Duration.minutes(5),
            memory_size=512,
        )

        # EventBridge Rule for Daily Digest (8 AM UTC)
        daily_rule = events.Rule(
            self,
            "DailyDigestRule",
            schedule=events.Schedule.cron(minute="0", hour="8"),
            description="Trigger daily digest at 8 AM UTC",
        )
        daily_rule.add_target(cast(_lambda.IFunction, digest_lambda))

        # EventBridge Rule for Weekly Digest (Sundays at 9 AM UTC)
        weekly_rule = events.Rule(
            self,
            "WeeklyDigestRule",
            schedule=events.Schedule.cron(minute="0", hour="9", week_day="SUN"),
            description="Trigger weekly digest on Sundays at 9 AM UTC",
        )
        weekly_rule.add_target(cast(_lambda.IFunction, digest_lambda))

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
