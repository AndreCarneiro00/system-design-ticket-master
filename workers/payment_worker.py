import os
import json
import random
import time
from datetime import datetime

import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from shared.models.models import Order, Reservation
from shared.redis.redis_client import increment_stock

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True
)


def restore_stock_if_needed(reservation: Reservation):
    if reservation.stock_restored:
        return

    stock_key = f"event:{reservation.event_id}:available_tickets"
    increment_stock(keys=[stock_key], args=[reservation.quantity])
    reservation.stock_restored = True


def process_payment_job(payload: str):
    data = json.loads(payload)

    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == data["order_id"]).first()
        reservation = db.query(Reservation).filter(Reservation.id == data["reservation_id"]).first()

        if not order or not reservation:
            print(f"Order ou reservation não encontrada. payload={data}")
            return

        if order.status != "PENDING_PAYMENT":
            print(f"Order {order.id} já processada. status={order.status}")
            return

        if reservation.status != "HOLD":
            print(
                f"Reservation {reservation.id} inválida para pagamento. "
                f"status={reservation.status}"
            )
            order.status = "FAILED"
            db.commit()
            return

        if reservation.expires_at < datetime.utcnow():
            print(f"Reservation {reservation.id} expirada antes do pagamento.")
            order.status = "FAILED"
            reservation.status = "EXPIRED"
            restore_stock_if_needed(reservation)
            db.commit()
            return

        time.sleep(2)

        approved = random.random() < 0.8

        if approved:
            order.status = "CONFIRMED"
            reservation.status = "CONFIRMED"
            print(f"Pagamento aprovado. order={order.id}")
        else:
            order.status = "FAILED"
            reservation.status = "CANCELLED"
            restore_stock_if_needed(reservation)
            print(f"Pagamento falhou. order={order.id}. Estoque devolvido.")

        db.commit()

    except Exception as exc:
        db.rollback()
        print(f"Erro ao processar job: {exc}")
    finally:
        db.close()


def main():
    print("Worker iniciado. Aguardando jobs...")
    while True:
        job = redis_client.blpop("payment_queue", timeout=5)

        if not job:
            continue

        queue_name, payload = job

        try:
            process_payment_job(payload)
        except Exception as exc:
            print(f"Erro ao processar job da fila {queue_name}: {exc}")


if __name__ == "__main__":
    main()