import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Event, Reservation
from app.redis_client import redis_client, decrement_if_available
from app.schemas import ReservationRequest, ReservationResponse
from app.queue_service import consume_ready_access

router = APIRouter(prefix="/reservations", tags=["reservations"])

RESERVATION_TTL_SECONDS = int(os.getenv("RESERVATION_TTL_SECONDS", 300))


@router.post("", response_model=ReservationResponse)
def create_reservation(payload: ReservationRequest, db: Session = Depends(get_db)):
    if payload.quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity deve ser maior que zero.")

    access_granted = consume_ready_access(
        event_id=payload.event_id,
        queue_token=payload.queue_token,
        user_id=payload.user_id
    )

    if not access_granted:
        raise HTTPException(
            status_code=403,
            detail="Usuário não está liberado pela fila virtual."
        )

    event = db.query(Event).filter(Event.id == payload.event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")

    stock_key = f"event:{payload.event_id}:available_tickets"

    result = decrement_if_available(
        keys=[stock_key],
        args=[payload.quantity]
    )

    if int(result) == -2:
        raise HTTPException(status_code=500, detail="Estoque não inicializado no Redis.")

    if int(result) == -1:
        raise HTTPException(status_code=409, detail="Ingressos indisponíveis.")

    expires_at = datetime.utcnow() + timedelta(seconds=RESERVATION_TTL_SECONDS)

    reservation = Reservation(
        event_id=payload.event_id,
        user_id=payload.user_id,
        quantity=payload.quantity,
        status="HOLD",
        expires_at=expires_at
    )

    db.add(reservation)
    db.commit()
    db.refresh(reservation)

    hold_key = f"hold:{reservation.id}"
    redis_client.set(
        hold_key,
        payload.quantity,
        ex=RESERVATION_TTL_SECONDS
    )

    return ReservationResponse(
        reservation_id=reservation.id,
        status=reservation.status,
        expires_at=reservation.expires_at
    )