from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from app.domain.shared.errors import DomainValidationError
from app.domain.shared.state_machine import StateMachineMixin


class PRStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class PRLine:
    item_name: str
    quantity: int
    unit_price: float

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise DomainValidationError("quantity must be greater than 0")
        if self.unit_price <= 0:
            raise DomainValidationError("unit_price must be greater than 0")


class PurchaseRequisition(StateMachineMixin):
    TRANSITIONS = {
        PRStatus.DRAFT: {"submit": PRStatus.SUBMITTED},
        PRStatus.SUBMITTED: {
            "approve": PRStatus.APPROVED,
            "reject": PRStatus.REJECTED,
        },
    }

    def __init__(
        self,
        requested_by: str,
        lines: list[PRLine],
        id: int | None = None,
        status: PRStatus = PRStatus.DRAFT,
        created_at: datetime | None = None,
    ) -> None:
        if not lines:
            raise DomainValidationError("a purchase requisition needs at least one line")
        self.id = id
        self.requested_by = requested_by
        self.lines = lines
        self.status = status
        self.created_at = created_at or datetime.now(timezone.utc)

    @classmethod
    def create(cls, requested_by: str, lines: list[PRLine]) -> "PurchaseRequisition":
        return cls(requested_by=requested_by, lines=lines)

    @property
    def total_amount(self) -> float:
        return sum(line.quantity * line.unit_price for line in self.lines)

    def submit(self) -> None:
        self._transition("submit")

    def approve(self) -> None:
        self._transition("approve")

    def reject(self) -> None:
        self._transition("reject")
