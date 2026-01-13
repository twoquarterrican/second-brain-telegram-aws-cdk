#!/usr/bin/env python3
import os
import aws_cdk as cdk
from second_brain.second_brain_stack import SecondBrainStack

app = cdk.App()
SecondBrainStack(
    app,
    "SecondBrainStack",
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"),
        region=os.getenv("CDK_DEFAULT_REGION", "us-east-1"),
    ),
)

app.synth()
