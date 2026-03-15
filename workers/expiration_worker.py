import os
import time
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from shared.models.models import Reservation
from shared.redis.redis_client import increment_stock

DATABASE_URL = os.getenv("DATABASE_URL")
EXPIRATION_WORKER_INTERVAL_SECONDS = int(
    os.getenv("EXPIRATION_WORKER_INTERVAL_SECONDS", 5)
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def restore_stock_if_needed(reservation: Reservation):
    if reservation.stock_restored:
        return

    stock_key = f"event:{reservation.event_id}:available_tickets"
    increment_stock(keys=[stock_key], args=[reservation.quantity])
    reservation.stock_restored = True


def expire_reservations():
    db = SessionLocal()

    try:
        now = datetime.utcnow()

        expired_reservations = (
            db.query(Reservation)
            .filter(
                Reservation.status == "HOLD",
                Reservation.expires_at < now
            )
            .all()
        )

        if not expired_reservations:
            return

        print(f"{len(expired_reservations)} reservas expiradas encontradas.")

        for reservation in expired_reservations:
            restore_stock_if_needed(reservation)
            reservation.status = "EXPIRED"

            print(
                f"Reserva {reservation.id} expirada. "
                f"Estoque devolvido: event_id={reservation.event_id}, "
                f"quantity={reservation.quantity}"
            )

        db.commit()

    except Exception as exc:
        db.rollback()
        print(f"Erro ao reconciliar reservas expiradas: {exc}")
    finally:
        db.close()


def main():
    print("Expiration workers iniciado.")

    while True:
        expire_reservations()
        time.sleep(EXPIRATION_WORKER_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()