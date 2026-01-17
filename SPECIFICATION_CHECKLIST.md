# Specification Checklist

This document tracks implementation status against the architecture specification in [ARCHITECTURE.md](./ARCHITECTURE.md) and design principles in [INSPIRATION.md](./INSPIRATION.md).

**Legend:**
- ✅ Fully implemented
- 🟡 Partially implemented
- ❌ Not implemented
- 🔮 Future enhancement (out of scope for MVP)

---

## 1. Eight Building Blocks (from INSPIRATION.md)

### 1.1 The Dropbox (Capture Point)

| Feature | Status | Location | Notes |
|---------|--------|----------|-------|
| Telegram bot as capture interface | ✅ | `processor.py:handler` | Webhook receives messages |
| Zero-decision capture | ✅ | - | User just sends text |
| <5 second capture time | ✅ | - | Native Telegram UX |
| Voice message capture | 🔮 | - | Future: AWS Transcribe integration |

### 1.2 The Sorter (Classifier)

| Feature | Status | Location | Notes |
|---------|--------|----------|-------|
| AI classification into 4 categories | ✅ | `processor.py:process_message` | People/Projects/Ideas/Admin |
| Anthropic Claude (primary) | ✅ | `processor.py:classify_with_anthropic` | claude-sonnet-4-20250514 |
| OpenAI GPT (fallback) | ✅ | `processor.py:classify_with_openai` | gpt-3.5-turbo |
| AWS Bedrock (tertiary fallback) | ✅ | `processor.py:classify_with_bedrock` | claude-3-haiku |
| Structured JSON output | ✅ | `processor.py:CLASSIFICATION_PROMPT` | category, name, status, next_action, notes, confidence |

### 1.3 The Form (Schema)

| Feature | Status | Location | Notes |
|---------|--------|----------|-------|
| DynamoDB table schema | ✅ | `second_brain_stack.py` | PK/SK composite key |
| StatusIndex GSI | ✅ | `second_brain_stack.py` | Query by status + created_at |
| Category fields: name, status, next_action, notes | ✅ | `processor.py:CLASSIFICATION_PROMPT` | Extracted by AI |
| Confidence score (0-100) | ✅ | `processor.py:process_message` | Normalized and stored |
| original_text preserved | ✅ | `embedding_matcher.py:create_item` | Audit trail |
| Embedding vector stored | ✅ | `embedding_matcher.py:create_item` | As Decimal list |
| created_at timestamp | ✅ | `embedding_matcher.py:create_item` | ISO format |
| updated_at timestamp | ✅ | `embedding_matcher.py:update_item` | On updates only |

### 1.4 The Filing Cabinet (Memory Store)

| Feature | Status | Location | Notes |
|---------|--------|----------|-------|
| DynamoDB as source of truth | ✅ | `second_brain_stack.py` | Pay-per-request billing |
| S3 bucket for vectors | ✅ | `second_brain_stack.py` | `second-brain-vectors-*` |
| S3 Vector Index | 🟡 | `create_vector_index.py` | **Manual creation required** - not in CDK |
| Query by category | ✅ | `digest.py:get_open_items` | Uses StatusIndex |
| Query by status | ✅ | `digest.py:get_open_items` | Uses StatusIndex |

### 1.5 The Receipt (Audit Trail)

| Feature | Status | Location | Notes |
|---------|--------|----------|-------|
| original_text stored | ✅ | `embedding_matcher.py` | On every item |
| confidence stored | ✅ | `embedding_matcher.py:create_item` | AI confidence score |
| category stored | ✅ | `embedding_matcher.py:create_item` | Classification result |
| Dedicated INBOX_LOG category | 🟡 | [ADR-001](./docs/adr/001-event-sourcing-inbox-log.md) | **In progress** - Event sourcing design accepted |
| Log status (filed/needs_review/corrected) | 🟡 | [ADR-001](./docs/adr/001-event-sourcing-inbox-log.md) | Part of event sourcing design |
| CloudWatch logging | ✅ | All Lambdas | Standard Python logging |

### 1.6 The Bouncer (Confidence Filter)

| Feature | Status | Location | Notes |
|---------|--------|----------|-------|
| Confidence threshold check | ✅ | `actions/process.py:handle` | Threshold = 60 |
| Low confidence warning to user | ✅ | `actions/process.py:handle` | "Low confidence - not saved" |
| Request clarification message | 🟡 | `actions/process.py:handle` | Says "please rephrase" but no structured follow-up |
| "needs_review" status | ❌ | - | Low confidence items not stored at all |
| Queue for manual review | ❌ | - | Not implemented |

### 1.7 The Tap on the Shoulder (Proactive Surfacing)

| Feature | Status | Location | Notes |
|---------|--------|----------|-------|
| Daily digest (8 AM UTC) | ✅ | `second_brain_stack.py:DailyDigestRule` | EventBridge cron |
| Weekly digest (Sunday 9 AM UTC) | ✅ | `second_brain_stack.py:WeeklyDigestRule` | EventBridge cron |
| AI-generated summary | ✅ | `digest.py:summarize_with_anthropic` | Claude Haiku |
| Fallback plain summary | ✅ | `digest.py:generate_digest_summary` | If AI fails |
| Top 3 actions for today | 🟡 | `digest.py:SUMMARY_PROMPT` | Requested in prompt, AI decides |
| Stuck items identification | 🟡 | `digest.py:SUMMARY_PROMPT` | Requested in prompt |
| Overdue items highlight | 🟡 | `digest.py:SUMMARY_PROMPT` | Requested but no due_date tracking |
| Manual digest trigger | ✅ | `actions/digest.py` | `/digest` command |

### 1.8 The Fix Button (Correction Mechanism)

| Feature | Status | Location | Notes |
|---------|--------|----------|-------|
| `/merge FROM INTO` command | ✅ | `actions/merge.py` | Merge items together |
| `/delete ID` command | ✅ | `actions/delete.py` | Delete single item |
| `/fix` correction command | ❌ | - | **Not implemented** |
| Reply-based correction | ❌ | - | Bot reply → correction not implemented |
| `/keep` mark as not duplicate | ❌ | - | Mentioned in output but not implemented |
| Confirmation reply after filing | ✅ | `actions/process.py` | Shows category and confidence |

---

## 2. Twelve Engineering Principles

| # | Principle | Status | Notes |
|---|-----------|--------|-------|
| 1 | One reliable behavior | ✅ | Just message the bot |
| 2 | Separate memory/compute/interface | ✅ | Telegram / Lambda / DynamoDB |
| 3 | Prompts as APIs (structured output) | ✅ | JSON schema in prompts |
| 4 | Trust mechanisms | 🟡 | Confidence scores yes, audit log partial |
| 5 | Safe defaults when uncertain | 🟡 | Low confidence rejected, but not queued for review |
| 6 | Small, frequent, actionable outputs | ✅ | Digests are concise |
| 7 | Next action as unit of execution | ✅ | `next_action` field extracted |
| 8 | Routing over organizing | ✅ | AI routes to 4 categories |
| 9 | Minimal categories and fields | ✅ | 4 categories, ~6 fields per item |
| 10 | Design for restart | ✅ | No backlog accumulation |
| 11 | Core loop first, modules later | ✅ | Core loop works, extras pending |
| 12 | Maintainability over cleverness | ✅ | Simple Lambda structure |

---

## 3. Infrastructure (CDK Stack)

| Resource | Status | Location | Notes |
|----------|--------|----------|-------|
| DynamoDB Table | ✅ | `second_brain_stack.py` | SecondBrain |
| DynamoDB StatusIndex GSI | ✅ | `second_brain_stack.py` | For status queries |
| S3 Vector Bucket | ✅ | `second_brain_stack.py` | `second-brain-vectors-*` |
| S3 Vector Index | 🟡 | `create_vector_index.py` | **Manual script, not CDK** |
| Processor Lambda | ✅ | `second_brain_stack.py` | 256MB, 30s timeout |
| Digest Lambda | ✅ | `second_brain_stack.py` | 512MB, 5min timeout |
| Task Linker Lambda | 🟡 | `second_brain_stack.py` | Declared but handler may not be wired |
| Lambda Layer (dependencies) | ✅ | `second_brain_stack.py` | Docker + uv build |
| Function URL | ✅ | `second_brain_stack.py` | Public HTTPS endpoint |
| Daily EventBridge Rule | ✅ | `second_brain_stack.py` | 8 AM UTC |
| Weekly EventBridge Rule | ✅ | `second_brain_stack.py` | Sunday 9 AM UTC |
| TriggerRole (IAM) | ✅ | `second_brain_stack.py` | For scripts |
| Bedrock IAM permissions | ✅ | `second_brain_stack.py` | InvokeModel for Titan |
| S3 Vectors IAM permissions | ✅ | `second_brain_stack.py` | SearchVectors, BatchPut/Delete |

---

## 4. Commands

| Command | Status | Location | Notes |
|---------|--------|----------|-------|
| (default) Process message | ✅ | `actions/process.py` | Classify and save |
| `/digest [daily\|weekly]` | ✅ | `actions/digest.py` | On-demand digest |
| `/open` | ✅ | `actions/open_items.py` | List open items |
| `/closed` | ✅ | `actions/closed_items.py` | List completed items |
| `/merge FROM INTO` | ✅ | `actions/merge.py` | Merge two items |
| `/delete ID` | ✅ | `actions/delete.py` | Delete item |
| `/debug count` | ✅ | `actions/debug_count.py` | Count items by category |
| `/debug backfill` | ✅ | `actions/debug_backfill.py` | Trigger embedding backfill |
| `/debug duplicates` | ✅ | `actions/debug_duplicates.py` | AI-powered duplicate detection |
| `/debug duplicates-auto` | ✅ | `actions/debug_duplicates_auto.py` | Auto-resolve duplicates |
| `/fix` | ❌ | - | Correct last classification |
| `/keep ID ID...` | ❌ | - | Mark items as not duplicates |
| `/status ID STATUS` | ❌ | - | Update item status |
| `/edit ID` | ❌ | - | Edit item fields |

---

## 5. Scripts (CLI Tools)

| Script | Status | Entry Point | Notes |
|--------|--------|-------------|-------|
| `setup-webhook` | ✅ | `scripts/setup_webhook.py` | Configure Telegram webhook |
| `tail-logs` | ✅ | `scripts/tail_logs.py` | Stream CloudWatch logs |
| `cdkw` | ✅ | `scripts/cdkw.py` | CDK wrapper |
| `deploy` | ✅ | `scripts/deploy.py` | Build layer + CDK deploy |
| `trigger-digest` | ✅ | `scripts/trigger_digest.py` | Manual digest invoke |
| `backfill-embeddings` | ✅ | `scripts/backfill_embeddings.py` | Backfill missing embeddings |
| `create-vector-index` | ✅ | `scripts/create_vector_index.py` | Create S3 Vector Index |
| `assume-role` | ✅ | `scripts/assume_role.py` | Run commands with TriggerRole |

---

## 6. Embedding & Deduplication

| Feature | Status | Location | Notes |
|---------|--------|----------|-------|
| Bedrock Titan embeddings (primary) | ✅ | `embedding_matcher.py:_embed_bedrock` | `titan-embed-text-v2:0` |
| OpenAI embeddings (fallback) | ✅ | `embedding_matcher.py:_embed_openai` | `text-embedding-3-small` |
| Cosine similarity calculation | ✅ | `embedding_matcher.py:cosine_similarity` | Manual implementation |
| S3 Vectors similarity search | ✅ | `embedding_matcher.py:find_similar_item` | query_vectors API |
| Similarity threshold (0.85) | ✅ | `embedding_matcher.py:find_similar_item` | Configurable |
| Update existing on high similarity | ✅ | `embedding_matcher.py:save_with_embedding_matching` | Updates instead of creating |
| Index new vectors | ✅ | `embedding_matcher.py:index_vector` | batch_put_vector API |
| Delete vectors on item delete | ❌ | - | `/delete` doesn't remove vector |

---

## 7. Security

| Feature | Status | Location | Notes |
|---------|--------|----------|-------|
| Webhook secret token validation | ✅ | `processor.py:handler` | `X-Telegram-Bot-Api-Secret-Token` |
| Function URL (no API Gateway) | ✅ | `second_brain_stack.py` | Public endpoint |
| TriggerRole for least-privilege | ✅ | `second_brain_stack.py` | Scripts assume role |
| Secrets in environment variables | ✅ | `.env.local` | Not committed |
| DynamoDB encryption at rest | 🟡 | AWS default | AWS-managed keys only |
| S3 encryption at rest | 🟡 | AWS default | AWS-managed keys only |
| API key rotation mechanism | ❌ | - | Manual only |

---

## 8. Quality & Testing

| Feature | Status | Location | Notes |
|---------|--------|----------|-------|
| Unit tests for Lambdas | ❌ | - | **No test coverage** |
| Integration tests | ❌ | - | Not implemented |
| Pre-commit hooks | ✅ | `.pre-commit-config.yaml` | Ruff, trailing whitespace |
| Type hints | 🟡 | Various | Partial coverage |
| Docstrings | 🟡 | Various | Partial coverage |

---

## 9. Future Enhancements (Out of Scope)

| Feature | Status | Notes |
|---------|--------|-------|
| Voice message capture | 🔮 | AWS Transcribe integration |
| Email forwarding | 🔮 | SES + Lambda |
| Meeting prep module | 🔮 | Calendar integration |
| Birthday reminders | 🔮 | Recurring events |
| Mobile app | 🔮 | Telegram is the interface |
| Web dashboard | 🔮 | DynamoDB viewer |
| Multi-user support | 🔮 | Currently single-user |

---

## Summary

### Implementation Progress

| Category | ✅ Done | 🟡 Partial | ❌ Missing |
|----------|---------|------------|------------|
| Building Blocks | 5 | 3 | 0 |
| Engineering Principles | 10 | 2 | 0 |
| Infrastructure | 12 | 2 | 0 |
| Commands | 10 | 0 | 4 |
| Scripts | 8 | 0 | 0 |
| Embedding/Dedup | 7 | 0 | 1 |
| Security | 4 | 2 | 1 |
| Quality/Testing | 1 | 2 | 2 |

### Priority Items to Implement

1. **S3 Vector Index in CDK** - Currently manual script, should be IaC
2. **`/fix` command** - Correct last classification (key trust mechanism)
3. **Vector cleanup on delete** - `/delete` should remove from S3 Vectors
4. **Unit tests** - No test coverage currently
5. **`needs_review` queue** - Low confidence items should be queued, not discarded

### In Progress

| Feature | ADR | Status |
|---------|-----|--------|
| Event Sourcing with INBOX_LOG | [ADR-001](./docs/adr/001-event-sourcing-inbox-log.md) | Design accepted, implementation pending |

---

*Last updated: 2026-01-17*
