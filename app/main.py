"""
Entry point for the Mini ERP API.

Run it with:
    uvicorn app.main:app --reload

Then open http://127.0.0.1:8000/docs for the interactive API docs.
"""

from fastapi import FastAPI

from app.routers import purchase_orders

app = FastAPI(
    title="Mini ERP API",
    description="A simple backend for a Mini ERP system.",
    version="0.1.0",
)

# Every module in app/routers gets "plugged in" here. As we add more
# modules (e.g. goods_receipts, invoices, payments) we just add one
# more line like this.
app.include_router(purchase_orders.router)


@app.get("/")
def root():
    """Simple health-check / welcome route."""
    return {"message": "Mini ERP API is running. Visit /docs to try it out."}
