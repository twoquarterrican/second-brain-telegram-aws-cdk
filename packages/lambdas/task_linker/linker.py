from .embeddings import embed_text
from .similarity import cosine_similarity
from .task_store import list_open_tasks, update_task_status, create_task


def derive_status(action: str) -> str:
    mapping = {
        "start": "in_progress",
        "started": "in_progress",
        "done": "completed",
        "complete": "completed",
    }
    return mapping.get(action.lower(), "open")


def link_task(user_id: str, message_text: str, action: str) -> dict:
    """Identify or create a task via embedding similarity."""
    msg_emb = embed_text(message_text)
    open_tasks = list_open_tasks(user_id)

    best_score = 0.0
    best_task = None
    for t in open_tasks:
        if not t.get("embedding"):
            continue
        score = cosine_similarity(msg_emb, t["embedding"])
        if score > best_score:
            best_score = score
            best_task = t

    status = derive_status(action)
    if best_task and best_score > 0.85:
        update_task_status(user_id, best_task["taskId"], status)
        return {"matched_task": best_task["taskId"], "confidence": best_score}
    else:
        new_task_id = create_task(user_id, message_text, status, msg_emb)
        return {"created_task": new_task_id, "confidence": best_score}


def handler(event, context):
    """AWS Lambda handler for task linking."""
    import json

    user_id = event.get("user_id", "default_user")
    message_text = event.get("message_text", "")
    action = event.get("action", "open")

    if not message_text:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "message_text is required"}),
        }

    try:
        result = link_task(user_id, message_text, action)
        return {"statusCode": 200, "body": json.dumps(result)}
    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
