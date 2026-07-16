"""
API endpoints for Purchase Orders.

This file only handles HTTP concerns (routes, status codes, request
bodies). The actual "how do we save/create a PO" logic lives in
app/database.py, and the data shapes live in app/models.py. Keeping
these separate makes each file easier to read on its own.
"""

from fastapi import APIRouter, HTTPException

from app import database
from app.models import PurchaseOrder, PurchaseOrderCreate

router = APIRouter(prefix="/purchase-orders", tags=["Purchase Orders"])


@router.post("", response_model=PurchaseOrder, status_code=201)
def create_purchase_order(order_in: PurchaseOrderCreate) -> PurchaseOrder:
    """
    Create a new Purchase Order.

    - Validates the request body against PurchaseOrderCreate.
    - Always creates the order with status = "draft" (see database.py).
    - Returns the full saved order, including its generated id.
    """
    return database.create_purchase_order(order_in)


@router.get("", response_model=list[PurchaseOrder])
def list_purchase_orders() -> list[PurchaseOrder]:
    """Return every Purchase Order created so far (in-memory only)."""
    return database.list_purchase_orders()


@router.get("/{order_id}", response_model=PurchaseOrder)
def get_purchase_order(order_id: int) -> PurchaseOrder:
    """Fetch a single Purchase Order by its id, or 404 if it doesn't exist."""
    order = database.get_purchase_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return order
