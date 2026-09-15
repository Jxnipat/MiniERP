# app/domain/goods_receipt/events.py
from dataclasses import dataclass

from app.domain.shared.domain_event import DomainEvent


@dataclass(frozen=True)
class GoodsReceiptPosted(DomainEvent):
    gr_id: int
    amount: float
