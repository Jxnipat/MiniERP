"""
Pydantic models for the Purchase Order (PO) part of the
Procure-to-Pay (P2P) workflow: PR -> PO -> GR -> AP -> Payment.

We only build the PurchaseOrder piece for now. Everything here is
just data shape + validation - no database, no business rules beyond
"a new PO always starts as Draft".
"""

from datetime import datetime
from enum import Enum
from typing import List

from pydantic import BaseModel, Field


class POStatus(str, Enum):
    """
    All the states a Purchase Order can be in.

    Right now we only ever *create* orders in the "draft" state.
    The other states are listed here so the model is ready for the
    next step (a proper state machine / RBAC-protected transitions),
    but nothing in this file lets a client jump straight to them.
    """
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PurchaseOrderItem(BaseModel):
    """One line item on a purchase order, e.g. '10 x Laptop Stand'."""

    item_name: str = Field(..., min_length=1, examples=["Laptop Stand"])
    quantity: int = Field(..., gt=0, examples=[10])
    unit_price: float = Field(..., gt=0, examples=[25.50])


class PurchaseOrderCreate(BaseModel):
    """
    Shape of the JSON body a client sends to POST /purchase-orders.

    Note: there is no "status" field here on purpose. The client is
    NOT allowed to choose the starting status - the API decides that.
    """

    vendor_name: str = Field(..., min_length=1, examples=["Acme Supplies Co."])
    items: List[PurchaseOrderItem] = Field(..., min_length=1)


class PurchaseOrder(PurchaseOrderCreate):
    """
    The full Purchase Order as stored/returned by the API.

    Adds everything the server is responsible for generating:
    id, status, total_amount, created_at.
    """

    id: int
    status: POStatus
    total_amount: float
    created_at: datetime
