"""
Entry point for the Mini ERP API.

Run it with:
    uvicorn app.main:app --reload

Then open http://127.0.0.1:8000/docs for the interactive API docs.
"""

from fastapi import FastAPI

from app.infrastructure.db.session import init_db
from app.interface.api.routers import (
    goods_receipts,
    ledger,
    payments,
    purchase_orders,
    purchase_requisitions,
)

app = FastAPI(
    title="Mini ERP API",
    description="A Procure-to-Pay backend with an automated double-entry GL engine.",
    version="0.2.0",
)

app.include_router(purchase_requisitions.router)
app.include_router(purchase_orders.router)
app.include_router(goods_receipts.router)
app.include_router(payments.router)
app.include_router(ledger.router)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/")
def root():
    """Simple health-check / welcome route."""
    return {"message": "Mini ERP API is running. Visit /docs to try it out."}
