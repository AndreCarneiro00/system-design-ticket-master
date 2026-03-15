from fastapi import APIRouter, HTTPException

from api.app.services.queue_service import create_queue_entry, get_queue_status
from api.app.schemas import (
    QueueJoinRequest,
    QueueJoinResponse,
    QueueStatusResponse,
)

router = APIRouter(prefix="/queue", tags=["queue"])


@router.post("/join", response_model=QueueJoinResponse)
def join_queue(payload: QueueJoinRequest):
    result = create_queue_entry(payload.event_id, payload.user_id)
    return QueueJoinResponse(**result)


@router.get("/{event_id}/{queue_token}", response_model=QueueStatusResponse)
def queue_status(event_id: int, queue_token: str):
    result = get_queue_status(event_id, queue_token)

    if not result:
        raise HTTPException(status_code=404, detail="Queue token não encontrado.")

    return QueueStatusResponse(**result)