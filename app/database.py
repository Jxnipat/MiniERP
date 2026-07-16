"""
Fake "database" for local testing.

There's no real database yet - just a Python dictionary that lives in
memory. This means:
  - It's great for quickly running and testing the API.
  - All data disappears when you stop the server (uvicorn).

When we're ready for a real database, this file is the ONLY place
that should need to change - the router code below talks to these
three functions/variables, not to a raw dict directly, so swapping
this out later stays simple.
"""

from datetime import datetime
from typing import Dict

from app.models import POStatus, PurchaseOrder, PurchaseOrderCreate

# key = purchase order id, value = the PurchaseOrder itself
purchase_orders: Dict[int, PurchaseOrder] = {}

# Simple auto-incrementing id counter (a real DB would do this for us)
_next_id = 1


def create_purchase_order(data: PurchaseOrderCreate) -> PurchaseOrder:
    """
    Turn the incoming PurchaseOrderCreate (from the client) into a full
    PurchaseOrder and save it in memory.

    Business rule: every new order starts as DRAFT, no matter what.
    """
    global _next_id

    total_amount = sum(item.quantity * item.unit_price for item in data.items)

    order = PurchaseOrder(
        id=_next_id,
        vendor_name=data.vendor_name,
        items=data.items,
        status=POStatus.DRAFT,   # <-- the business rule lives right here
        total_amount=total_amount,
        created_at=datetime.utcnow(),
    )

    purchase_orders[order.id] = order
    _next_id += 1

    return order


def get_purchase_order(order_id: int) -> PurchaseOrder | None:
    return purchase_orders.get(order_id)


def list_purchase_orders() -> list[PurchaseOrder]:
    return list(purchase_orders.values())
