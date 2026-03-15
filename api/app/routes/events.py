from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from shared.database.db import get_db
from shared.models.models import Event
from shared.redis.redis_client import redis_client
from api.app.schemas import EventCreateRequest, EventResponse

router = APIRouter(prefix="/events", tags=["events"])


@router.post("", response_model=EventResponse)
def create_event(payload: EventCreateRequest, db: Session = Depends(get_db)):
    if payload.total_tickets <= 0:
        raise HTTPException(status_code=400, detail="total_tickets deve ser maior que zero.")

    event = Event(
        name=payload.name,
        total_tickets=payload.total_tickets,
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    redis_client.set(f"event:{event.id}:available_tickets", event.total_tickets)

    return EventResponse(
        id=event.id,
        name=event.name,
        total_tickets=event.total_tickets
    )


@router.get("/{event_id}/stock")
def get_stock(event_id: int, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")

    available = redis_client.get(f"event:{event_id}:available_tickets")
    available = int(available) if available is not None else 0

    return {
        "event_id": event.id,
        "event_name": event.name,
        "total_tickets": event.total_tickets,
        "available_tickets": available
    }