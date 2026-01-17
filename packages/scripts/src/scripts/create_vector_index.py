#!/usr/bin/env python3
"""Create S3 Vector Index for embedding similarity search.

S3 Vectors is not yet available in CloudFormation, so we create it via API.

Usage:
    python scripts/create_vector_index.py

Environment variables:
    AWS_PROFILE: AWS profile to use
    AWS_REGION: AWS region (default: us-east-1)
    VECTOR_BUCKET_NAME: S3 bucket name for vector storage
"""

import os
import boto3


def create_vector_index():
    """Create the S3 Vector Index."""
    region = os.environ.get("AWS_REGION", "us-east-1")
    bucket_name = os.environ.get("VECTOR_BUCKET_NAME")

    if not bucket_name:
        bucket_name = f"second-brain-vectors-{boto3.Session().region_name}-{region}"

    s3control = boto3.client("s3control", region_name=region)

    print(f"Creating S3 Vector Index in {region}...")
    print(f"  Index Name: SecondBrainItemsIndex")
    print(f"  Bucket: {bucket_name}")

    try:
        response = s3control.create_vector_index(
            IndexName="SecondBrainItemsIndex",
            IndexUri=f"s3://{bucket_name}/vector-index/",
            VectorDimension=1024,
            Metric="COSINE",
        )

        print("✅ Vector Index created successfully!")
        print(f"   Index ARN: {response.get('IndexArn', 'N/A')}")

    except Exception as e:
        print(f"❌ Failed to create Vector Index: {e}")
        raise


if __name__ == "__main__":
    create_vector_index()
