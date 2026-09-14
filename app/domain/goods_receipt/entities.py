# app/domain/goods_receipt/entities.py
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from app.domain.goods_receipt.events import GoodsReceiptPosted
from app.domain.shared.domain_event import AggregateRoot
from app.domain.shared.errors import DomainValidationError
from app.domain.shared.state_machine import StateMachineMixin


class GRStatus(str, Enum):
    DRAFT = "draft"
    POSTED = "posted"


@dataclass
class GRLine:
    line_number: int
    quantity_received: int

    def __post_init__(self) -> None:
        if self.quantity_received <= 0:
            raise DomainValidationError("quantity_received must be greater than 0")


class GoodsReceipt(StateMachineMixin, AggregateRoot):
    TRANSITIONS = {
        GRStatus.DRAFT: {"post": GRStatus.POSTED},
    }

    def __init__(
        self,
        po_id: int,
        lines: list[GRLine],
        id: int | None = None,
        status: GRStatus = GRStatus.DRAFT,
        total_amount: float | None = None,
        created_at: datetime | None = None,
    ) -> None:
        AggregateRoot.__init__(self)
        if not lines:
            raise DomainValidationError("a goods receipt needs at least one line")
        self.id = id
        self.po_id = po_id
        self.lines = lines
        self.status = status
        self.total_amount = total_amount
        self.created_at = created_at or datetime.now(timezone.utc)

    @classmethod
    def create(cls, po_id: int, lines: list[GRLine]) -> "GoodsReceipt":
        return cls(po_id=po_id, lines=lines)

    def post(self, amount: float) -> None:
        self._transition("post")
        self.total_amount = amount
        self.record_event(GoodsReceiptPosted(gr_id=self.id, amount=amount))
