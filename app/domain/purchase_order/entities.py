from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from app.domain.purchase_requisition.entities import PRStatus
from app.domain.shared.errors import DomainValidationError
from app.domain.shared.state_machine import StateMachineMixin


class POStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    PARTIALLY_RECEIVED = "partially_received"
    RECEIVED = "received"
    CLOSED = "closed"
    CANCELLED = "cancelled"


@dataclass
class POLine:
    line_number: int
    item_name: str
    quantity: int
    unit_price: float
    quantity_received: int = 0

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise DomainValidationError("quantity must be greater than 0")
        if self.unit_price <= 0:
            raise DomainValidationError("unit_price must be greater than 0")

    @property
    def remaining_quantity(self) -> int:
        return self.quantity - self.quantity_received


class PurchaseOrder(StateMachineMixin):
    TRANSITIONS = {
        POStatus.DRAFT: {"submit": POStatus.SUBMITTED, "cancel": POStatus.CANCELLED},
        POStatus.SUBMITTED: {
            "approve": POStatus.APPROVED,
            "cancel": POStatus.CANCELLED,
        },
        POStatus.APPROVED: {"cancel": POStatus.CANCELLED},
        POStatus.RECEIVED: {"close": POStatus.CLOSED},
    }

    def __init__(
        self,
        pr_id: int,
        vendor_name: str,
        lines: list[POLine],
        id: int | None = None,
        status: POStatus = POStatus.DRAFT,
        created_at: datetime | None = None,
    ) -> None:
        if not lines:
            raise DomainValidationError("a purchase order needs at least one line")
        self.id = id
        self.pr_id = pr_id
        self.vendor_name = vendor_name
        self.lines = lines
        self.status = status
        self.created_at = created_at or datetime.now(timezone.utc)

    @classmethod
    def create_from_pr(
        cls,
        pr_id: int,
        pr_status: PRStatus,
        vendor_name: str,
        lines: list[POLine],
    ) -> "PurchaseOrder":
        if pr_status != PRStatus.APPROVED:
            raise DomainValidationError(
                f"cannot create a purchase order from PR #{pr_id}: PR is not approved"
            )
        return cls(pr_id=pr_id, vendor_name=vendor_name, lines=lines)

    @property
    def total_amount(self) -> float:
        return sum(line.quantity * line.unit_price for line in self.lines)

    def submit(self) -> None:
        self._transition("submit")

    def approve(self) -> None:
        self._transition("approve")

    def cancel(self) -> None:
        self._transition("cancel")

    def close(self) -> None:
        self._transition("close")

    def receive_goods(self, received_lines: dict[int, int]) -> None:
        """
        received_lines: {line_number: quantity received in this delivery}.
        Not a plain `_transition()` call because the resulting status
        depends on the quantities, not just a fixed action->state map.
        """
        if self.status not in (POStatus.APPROVED, POStatus.PARTIALLY_RECEIVED):
            raise DomainValidationError(
                f"cannot receive goods against a PO in status '{self.status}'"
            )

        lines_by_number = {line.line_number: line for line in self.lines}
        for line_number, qty in received_lines.items():
            line = lines_by_number.get(line_number)
            if line is None:
                raise DomainValidationError(f"PO has no line number {line_number}")
            if qty > line.remaining_quantity:
                raise DomainValidationError(
                    f"line {line_number}: cannot receive {qty}, only "
                    f"{line.remaining_quantity} remaining"
                )
            line.quantity_received += qty

        if all(line.remaining_quantity == 0 for line in self.lines):
            self.status = POStatus.RECEIVED
        else:
            self.status = POStatus.PARTIALLY_RECEIVED
