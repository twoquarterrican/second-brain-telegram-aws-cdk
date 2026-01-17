#!/usr/bin/env python3
import os

import aws_cdk as cdk
from aws_cdk import aws_lambda as lambda_
from second_brain.second_brain_stack import SecondBrainStack

app = cdk.App()

SecondBrainStack(
    app,
    "SecondBrainStack",
)

app.synth()
