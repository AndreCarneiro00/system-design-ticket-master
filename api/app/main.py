from fastapi import FastAPI

from shared.database.db import Base, engine
from api.app.routes.events import router as events_router
from api.app.routes.reservations import router as reservations_router
from api.app.routes.checkout import router as checkout_router
from api.app.routes.queue import router as queue_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Ticket Master API")

app.include_router(events_router)
app.include_router(reservations_router)
app.include_router(checkout_router)
app.include_router(queue_router)

@app.get("/health")
def health():
    return {"status": "ok"}