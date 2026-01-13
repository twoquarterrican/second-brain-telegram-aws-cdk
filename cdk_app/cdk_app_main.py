#!/usr/bin/env python3
"""
AWS CDK entry point for Second Brain application.
"""

from main import SecondBrainStack
from aws_cdk import App


def main():
    """CDK entry point."""
    app = App(outdir="cdk.out")
    SecondBrainStack(app, "SecondBrainStack")

    app.synth()


if __name__ == "__main__":
    main()
