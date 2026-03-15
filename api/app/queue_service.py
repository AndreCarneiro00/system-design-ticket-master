import json
import os
import uuid
from datetime import datetime, timedelta, UTC

from app.redis_client import redis_client

ACTIVE_EVENTS_KEY = "queue:active_events"
QUEUE_PURCHASE_WINDOW_SECONDS = int(os.getenv("QUEUE_PURCHASE_WINDOW_SECONDS", 120))

def waiting_key(event_id: int) -> str:
    return f"queue:event:{event_id}:waiting"


def active_key(event_id: int) -> str:
    return f"queue:event:{event_id}:active"


def token_key(event_id: int, queue_token: str) -> str:
    return f"queue:event:{event_id}:token:{queue_token}"


def create_queue_entry(event_id: int, user_id: str):
    queue_token = str(uuid.uuid4())

    register_active_event(event_id)

    payload = {
        "queue_token": queue_token,
        "event_id": event_id,
        "user_id": user_id,
        "status": "WAITING",
        "created_at": datetime.now(UTC).isoformat(),
        "expires_at": None,
    }

    redis_client.set(
        token_key(event_id, queue_token),
        json.dumps(payload),
        ex=3600
    )

    redis_client.rpush(waiting_key(event_id), queue_token)

    position = redis_client.llen(waiting_key(event_id))

    return {
        "queue_token": queue_token,
        "status": "WAITING",
        "position": position,
    }


def get_queue_status(event_id: int, queue_token: str):
    raw = redis_client.get(token_key(event_id, queue_token))
    if not raw:
        return None

    data = json.loads(raw)
    status = data["status"]

    position = None
    expires_at = data.get("expires_at")

    if status == "WAITING":
        waiting_list = redis_client.lrange(waiting_key(event_id), 0, -1)
        try:
            position = waiting_list.index(queue_token) + 1
        except ValueError:
            position = None

    return {
        "queue_token": data["queue_token"],
        "event_id": data["event_id"],
        "user_id": data["user_id"],
        "status": status,
        "position": position,
        "expires_at": expires_at,
    }


def mark_token_ready(event_id: int, queue_token: str, user_id: str):
    expires_at = datetime.now(UTC) + timedelta(seconds=QUEUE_PURCHASE_WINDOW_SECONDS)

    payload = {
        "queue_token": queue_token,
        "event_id": event_id,
        "user_id": user_id,
        "status": "READY",
        "created_at": datetime.now(UTC).isoformat(),
        "expires_at": expires_at.isoformat(),
    }

    redis_client.set(
        token_key(event_id, queue_token),
        json.dumps(payload),
        ex=QUEUE_PURCHASE_WINDOW_SECONDS
    )

    redis_client.sadd(active_key(event_id), queue_token)

    return expires_at


def mark_token_expired(event_id: int, queue_token: str, user_id: str):
    payload = {
        "queue_token": queue_token,
        "event_id": event_id,
        "user_id": user_id,
        "status": "EXPIRED",
        "created_at": datetime.now(UTC).isoformat(),
        "expires_at": None,
    }

    redis_client.set(
        token_key(event_id, queue_token),
        json.dumps(payload),
        ex=300
    )

    redis_client.srem(active_key(event_id), queue_token)
    unregister_active_event_if_empty(event_id)


def consume_ready_access(event_id: int, queue_token: str, user_id: str) -> bool:
    raw = redis_client.get(token_key(event_id, queue_token))
    if not raw:
        return False

    data = json.loads(raw)

    if data["status"] != "READY":
        return False

    if data["user_id"] != user_id:
        return False

    expires_at = data.get("expires_at")
    if not expires_at:
        return False

    expires_dt = datetime.fromisoformat(expires_at)
    if expires_dt < datetime.now(UTC):
        mark_token_expired(event_id, queue_token, user_id)
        return False

    payload = {
        "queue_token": queue_token,
        "event_id": event_id,
        "user_id": user_id,
        "status": "CONSUMED",
        "created_at": data.get("created_at"),
        "expires_at": expires_at,
    }

    redis_client.set(
        token_key(event_id, queue_token),
        json.dumps(payload),
        ex=600
    )
    redis_client.srem(active_key(event_id), queue_token)
    unregister_active_event_if_empty(event_id)
    return True


def register_active_event(event_id: int):
    redis_client.sadd(ACTIVE_EVENTS_KEY, event_id)


def unregister_active_event_if_empty(event_id: int):
    waiting_count = redis_client.llen(waiting_key(event_id))
    active_count = redis_client.scard(active_key(event_id))

    if waiting_count == 0 and active_count == 0:
        redis_client.srem(ACTIVE_EVENTS_KEY, event_id)


def get_active_events():
    return [int(event_id) for event_id in redis_client.smembers(ACTIVE_EVENTS_KEY)]