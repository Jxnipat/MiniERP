import pytest

from app.domain.goods_receipt.entities import GRStatus
from app.domain.payment.entities import Payment, PaymentStatus
from app.domain.payment.events import PaymentPaid
from app.domain.shared.errors import DomainValidationError
from app.domain.shared.state_machine import InvalidStateTransitionError


def test_create_for_gr_requires_posted_gr():
    with pytest.raises(DomainValidationError):
        Payment.create_for_gr(
            gr_id=1, gr_status=GRStatus.DRAFT, gr_total_amount=100.0, amount=100.0
        )


def test_create_for_gr_requires_matching_amount():
    with pytest.raises(DomainValidationError):
        Payment.create_for_gr(
            gr_id=1, gr_status=GRStatus.POSTED, gr_total_amount=100.0, amount=50.0
        )


def test_full_payment_flow_records_event():
    payment = Payment.create_for_gr(
        gr_id=1, gr_status=GRStatus.POSTED, gr_total_amount=100.0, amount=100.0
    )
    payment.id = 9

    payment.approve()
    payment.pay()

    assert payment.status == PaymentStatus.PAID
    events = payment.pull_events()
    assert len(events) == 1
    assert isinstance(events[0], PaymentPaid)
    assert events[0].payment_id == 9
    assert events[0].gr_id == 1
    assert events[0].amount == 100.0


def test_cannot_pay_before_approval():
    payment = Payment.create_for_gr(
        gr_id=1, gr_status=GRStatus.POSTED, gr_total_amount=100.0, amount=100.0
    )

    with pytest.raises(InvalidStateTransitionError):
        payment.pay()


def test_amount_must_be_positive():
    with pytest.raises(DomainValidationError):
        Payment(gr_id=1, amount=0.0)
