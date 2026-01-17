#!/usr/bin/env python3

import aws_cdk as cdk
from second_brain.second_brain_stack import SecondBrainStack

app = cdk.App()

SecondBrainStack(
    app,
    "SecondBrainStack",
)

app.synth()
