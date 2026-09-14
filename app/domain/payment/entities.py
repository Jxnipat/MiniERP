from datetime import datetime, timezone
from enum import Enum

from app.domain.goods_receipt.entities import GRStatus
from app.domain.payment.events import PaymentPaid
from app.domain.shared.domain_event import AggregateRoot
from app.domain.shared.errors import DomainValidationError
from app.domain.shared.state_machine import StateMachineMixin


class PaymentStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    PAID = "paid"


class Payment(StateMachineMixin, AggregateRoot):
    TRANSITIONS = {
        PaymentStatus.DRAFT: {"approve": PaymentStatus.APPROVED},
        PaymentStatus.APPROVED: {"pay": PaymentStatus.PAID},
    }

    def __init__(
        self,
        gr_id: int,
        amount: float,
        id: int | None = None,
        status: PaymentStatus = PaymentStatus.DRAFT,
        created_at: datetime | None = None,
    ) -> None:
        AggregateRoot.__init__(self)
        if amount <= 0:
            raise DomainValidationError("amount must be greater than 0")
        self.id = id
        self.gr_id = gr_id
        self.amount = amount
        self.status = status
        self.created_at = created_at or datetime.now(timezone.utc)

    @classmethod
    def create_for_gr(
        cls, gr_id: int, gr_status: GRStatus, gr_total_amount: float, amount: float
    ) -> "Payment":
        if gr_status != GRStatus.POSTED:
            raise DomainValidationError(
                f"cannot create a payment for GR #{gr_id}: GR is not posted"
            )
        if round(amount, 2) != round(gr_total_amount, 2):
            raise DomainValidationError(
                f"payment amount {amount} must equal the goods receipt total "
                f"{gr_total_amount}"
            )
        return cls(gr_id=gr_id, amount=amount)

    def approve(self) -> None:
        self._transition("approve")

    def pay(self) -> None:
        self._transition("pay")
        self.record_event(
            PaymentPaid(payment_id=self.id, gr_id=self.gr_id, amount=self.amount)
        )
