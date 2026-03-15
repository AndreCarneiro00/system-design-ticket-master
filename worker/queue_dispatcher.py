import json
import os
import time
from datetime import datetime, UTC

from app.queue_service import (
    active_key,
    get_active_events,
    mark_token_expired,
    mark_token_ready,
    token_key,
    unregister_active_event_if_empty,
    waiting_key,
)
from app.redis_client import redis_client

QUEUE_MAX_ACTIVE_USERS = int(os.getenv("QUEUE_MAX_ACTIVE_USERS", 5))
QUEUE_DISPATCHER_INTERVAL_SECONDS = int(os.getenv("QUEUE_DISPATCHER_INTERVAL_SECONDS", 2))


def cleanup_expired_ready_tokens(event_id: int):
    active_tokens = redis_client.smembers(active_key(event_id))

    for queue_token in active_tokens:
        raw = redis_client.get(token_key(event_id, queue_token))
        if not raw:
            redis_client.srem(active_key(event_id), queue_token)
            continue

        data = json.loads(raw)
        expires_at = data.get("expires_at")
        if not expires_at:
            continue

        expires_dt = datetime.fromisoformat(expires_at)
        if expires_dt < datetime.now(UTC):
            mark_token_expired(event_id, queue_token, data["user_id"])


def dispatch_event(event_id: int):
    cleanup_expired_ready_tokens(event_id)

    active_count = redis_client.scard(active_key(event_id))
    slots = max(QUEUE_MAX_ACTIVE_USERS - active_count, 0)

    for _ in range(slots):
        queue_token = redis_client.lpop(waiting_key(event_id))
        if not queue_token:
            break

        raw = redis_client.get(token_key(event_id, queue_token))
        if not raw:
            continue

        data = json.loads(raw)
        mark_token_ready(event_id, queue_token, data["user_id"])
        print(
            f"Usuário liberado na fila: "
            f"event={event_id}, user={data['user_id']}, token={queue_token}"
        )

    unregister_active_event_if_empty(event_id)


def main():
    print("Queue dispatcher iniciado.")

    while True:
        event_ids = get_active_events()

        for event_id in event_ids:
            dispatch_event(event_id)

        time.sleep(QUEUE_DISPATCHER_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()