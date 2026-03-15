from datetime import datetime
from pydantic import BaseModel


class EventCreateRequest(BaseModel):
    name: str
    total_tickets: int


class EventResponse(BaseModel):
    id: int
    name: str
    total_tickets: int


class ReservationRequest(BaseModel):
    event_id: int
    user_id: str
    quantity: int = 1
    queue_token: str


class ReservationResponse(BaseModel):
    reservation_id: int
    status: str
    expires_at: datetime


class CheckoutRequest(BaseModel):
    reservation_id: int
    user_id: str


class CheckoutResponse(BaseModel):
    order_id: int
    status: str
    reservation_id: int
    idempotency_key: str


class OrderResponse(BaseModel):
    order_id: int
    reservation_id: int
    user_id: str
    idempotency_key: str
    status: str
    created_at: datetime


class QueueJoinRequest(BaseModel):
    event_id: int
    user_id: str


class QueueJoinResponse(BaseModel):
    queue_token: str
    status: str
    position: int


class QueueStatusResponse(BaseModel):
    queue_token: str
    event_id: int
    user_id: str
    status: str
    position: int | None = None
    expires_at: datetime | None = None