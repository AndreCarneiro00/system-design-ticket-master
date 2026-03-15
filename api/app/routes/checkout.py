import json

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shared.database.db import get_db
from shared.models.models import Order, Reservation
from shared.redis.redis_client import redis_client
from api.app.schemas import CheckoutRequest, CheckoutResponse, OrderResponse

router = APIRouter(prefix="/checkout", tags=["checkout"])


@router.post("", response_model=CheckoutResponse)
def checkout(
    payload: CheckoutRequest,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    if not idempotency_key:
        raise HTTPException(
            status_code=400,
            detail="Header Idempotency-Key é obrigatório."
        )

    existing_order = (
        db.query(Order)
        .filter(Order.idempotency_key == idempotency_key)
        .first()
    )

    if existing_order:
        return CheckoutResponse(
            order_id=existing_order.id,
            status=existing_order.status,
            reservation_id=existing_order.reservation_id,
            idempotency_key=existing_order.idempotency_key
        )

    reservation = (
        db.query(Reservation)
        .filter(Reservation.id == payload.reservation_id)
        .first()
    )

    if not reservation:
        raise HTTPException(status_code=404, detail="Reserva não encontrada.")

    if reservation.user_id != payload.user_id:
        raise HTTPException(status_code=403, detail="Reserva não pertence ao usuário.")

    if reservation.status != "HOLD":
        raise HTTPException(status_code=409, detail="Reserva não está disponível para checkout.")

    if reservation.expires_at < __import__("datetime").datetime.utcnow():
        raise HTTPException(status_code=409, detail="Reserva expirada.")

    order = Order(
        reservation_id=reservation.id,
        user_id=payload.user_id,
        idempotency_key=idempotency_key,
        status="PENDING_PAYMENT"
    )

    try:
        db.add(order)
        db.commit()
        db.refresh(order)
    except IntegrityError:
        db.rollback()

        existing_order = (
            db.query(Order)
            .filter(Order.idempotency_key == idempotency_key)
            .first()
        )

        if not existing_order:
            raise HTTPException(status_code=500, detail="Erro ao resolver idempotência.")

        return CheckoutResponse(
            order_id=existing_order.id,
            status=existing_order.status,
            reservation_id=existing_order.reservation_id,
            idempotency_key=existing_order.idempotency_key
        )

    job = {
        "order_id": order.id,
        "reservation_id": reservation.id,
        "event_id": reservation.event_id,
        "user_id": reservation.user_id,
        "quantity": reservation.quantity
    }

    redis_client.rpush("payment_queue", json.dumps(job))

    return CheckoutResponse(
        order_id=order.id,
        status=order.status,
        reservation_id=order.reservation_id,
        idempotency_key=order.idempotency_key
    )


@router.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order não encontrada.")

    return OrderResponse(
        order_id=order.id,
        reservation_id=order.reservation_id,
        user_id=order.user_id,
        idempotency_key=order.idempotency_key,
        status=order.status,
        created_at=order.created_at
    )