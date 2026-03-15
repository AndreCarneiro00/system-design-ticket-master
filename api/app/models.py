from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from app.db import Base


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    total_tickets = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Reservation(Base):
    __tablename__ = "reservations"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    quantity = Column(Integer, nullable=False, default=1)
    status = Column(String, nullable=False, default="HOLD")
    expires_at = Column(DateTime, nullable=False)
    stock_restored = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    reservation_id = Column(Integer, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    idempotency_key = Column(String, nullable=False, unique=True, index=True)
    status = Column(String, nullable=False, default="PENDING_PAYMENT")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)