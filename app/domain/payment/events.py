from dataclasses import dataclass

from app.domain.shared.domain_event import DomainEvent


@dataclass(frozen=True)
class PaymentPaid(DomainEvent):
    payment_id: int
    gr_id: int
    amount: float
