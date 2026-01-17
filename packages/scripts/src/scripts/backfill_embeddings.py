#!/usr/bin/env python3
"""
Backfill utility for embedding missing Task items in DynamoDB.

This script:
1. Assumes SecondBrainTriggerRole to get DynamoDB write permissions
2. Scans SecondBrainTable for Task items missing embeddings
3. Batch processes items (≤20 per OpenAI call)
4. Generates embeddings using OpenAI text-embedding-3-small
5. Updates items with embedding and embeddingUpdatedAt
6. Uses checkpointing (JSON file) for resume capability

Usage:
    python scripts/backfill_embeddings.py
"""

import os
import sys
import time
import json
from datetime import datetime
from pathlib import Path

from openai import OpenAI
from common.environments import get_table

# Constants
CHECKPOINT_FILE = "backfill_checkpoint.json"
BATCH_SIZE = 20
EMBEDDING_MODEL = "text-embedding-3-small"
THROTTLE_SECONDS = 0.5


def get_checkpoint() -> set:
    """Load processed items from checkpoint file."""
    checkpoint_path = Path(__file__).parent / CHECKPOINT_FILE
    if checkpoint_path.exists():
        with open(checkpoint_path) as f:
            return set(json.load(f))
    return set()


def save_checkpoint(items: set):
    """Save processed items to checkpoint file."""
    checkpoint_path = Path(__file__).parent / CHECKPOINT_FILE
    with open(checkpoint_path, "w") as f:
        json.dump(list(items), f)


def embed_texts(client: OpenAI, texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a batch of texts using OpenAI."""
    resp = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
    )
    return [d.embedding for d in resp.data]


def update_item_embedding(table, pk: str, sk: str, embedding: list[float]):
    """Update a DynamoDB item with embedding and timestamp."""
    table.update_item(
        Key={"PK": pk, "SK": sk},
        UpdateExpression="SET embedding = :e, embeddingUpdatedAt = :t",
        ExpressionAttributeValues={
            ":e": embedding,
            ":t": datetime.utcnow().isoformat(),
        },
    )


def run_backfill():
    """Main backfill execution."""
    print("🚀 Starting embedding backfill...")
    print(f"   Model: {EMBEDDING_MODEL}")
    print(f"   Batch size: {BATCH_SIZE}")
    print()

    # Initialize OpenAI client
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")

    client = OpenAI(api_key=openai_api_key)

    # Get table with assumed role credentials
    print("🔐 Assuming SecondBrainTriggerRole...")
    table = get_table(second_brain_trigger_role=True)
    table_name = table.table_name
    print(f"   Connected to table: {table_name}")
    print()

    # Load checkpoint
    processed = get_checkpoint()
    print(f"📋 Loaded checkpoint: {len(processed)} items already processed")
    print()

    # Scan for Task items missing embeddings
    print("🔍 Scanning for Task items missing embeddings...")
    paginator = table.meta.client.get_paginator("scan")

    total_scanned = 0
    total_updated = 0
    total_skipped = 0

    for page in paginator.paginate(
        TableName=table_name,
        FilterExpression="entityType = :t AND attribute_not_exists(embedding)",
        ExpressionAttributeValues={":t": "Task"},
    ):
        items = page.get("Items", [])
        total_scanned += len(items)

        # Filter out already processed items
        items_to_process = [
            item for item in items if item["PK"] + item["SK"] not in processed
        ]
        total_skipped += len(items) - len(items_to_process)

        if not items_to_process:
            print(f"   Page: {len(items)} tasks found, 0 new (all already processed)")
            continue

        print(f"   Page: {len(items)} tasks found, {len(items_to_process)} new")

        # Process in batches
        for i in range(0, len(items_to_process), BATCH_SIZE):
            batch = items_to_process[i : i + BATCH_SIZE]
            texts = [item.get("name", "") or "" for item in batch]

            # Generate embeddings
            print(f"   📦 Embedding batch of {len(texts)} items...")
            embeddings = embed_texts(client, texts)

            # Update each item
            for item, embedding in zip(batch, embeddings):
                pk = item["PK"]
                sk = item["SK"]
                update_item_embedding(table, pk, sk, embedding)
                processed.add(pk + sk)
                total_updated += 1

            # Save checkpoint
            save_checkpoint(processed)

            # Throttle to avoid rate limits
            time.sleep(THROTTLE_SECONDS)

    print()
    print("✅ Backfill complete!")
    print(f"   Total scanned: {total_scanned}")
    print(f"   Already processed (skipped): {total_skipped}")
    print(f"   Newly embedded: {total_updated}")
    print(f"   Checkpoint saved: {len(processed)} items")


if __name__ == "__main__":
    run_backfill()
