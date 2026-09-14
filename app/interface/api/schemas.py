# app/interface/api/schemas.py
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LineItemIn(BaseModel):
    item_name: str = Field(..., min_length=1)
    quantity: int = Field(..., gt=0)
    unit_price: float = Field(..., gt=0)


class PRCreate(BaseModel):
    requested_by: str = Field(..., min_length=1)
    lines: list[LineItemIn] = Field(..., min_length=1)


class PRLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    item_name: str
    quantity: int
    unit_price: float


class PROut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    requested_by: str
    status: str
    total_amount: float
    lines: list[PRLineOut]
    created_at: datetime


class POCreate(BaseModel):
    pr_id: int
    vendor_name: str = Field(..., min_length=1)
    lines: list[LineItemIn] = Field(..., min_length=1)


class POLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    line_number: int
    item_name: str
    quantity: int
    unit_price: float
    quantity_received: int


class POOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pr_id: int
    vendor_name: str
    status: str
    total_amount: float
    lines: list[POLineOut]
    created_at: datetime


class GRLineIn(BaseModel):
    line_number: int
    quantity_received: int = Field(..., gt=0)


class GRCreate(BaseModel):
    po_id: int
    lines: list[GRLineIn] = Field(..., min_length=1)


class GRLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    line_number: int
    quantity_received: int


class GROut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    po_id: int
    status: str
    total_amount: float | None
    lines: list[GRLineOut]
    created_at: datetime


class PaymentCreate(BaseModel):
    gr_id: int
    amount: float = Field(..., gt=0)


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    gr_id: int
    amount: float
    status: str
    created_at: datetime


class JournalLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    account_code: str
    debit: float
    credit: float


class JournalEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_event: str
    source_id: int
    posted_at: datetime
    lines: list[JournalLineOut]


class TrialBalanceRowOut(BaseModel):
    account_code: str
    account_name: str
    debit: float
    credit: float
