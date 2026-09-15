import pytest

from app.application.services.gr_service import GRService
from app.application.services.ledger_service import LedgerService
from app.application.services.payment_service import PaymentService
from app.application.services.po_service import POService
from app.application.services.pr_service import PRService
from app.domain.shared.errors import DomainValidationError


def posted_gr(uow):
    pr_service = PRService(uow)
    pr = pr_service.create(
        requested_by="alice",
        lines=[{"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}],
    )
    pr_service.submit(pr.id)
    pr_service.approve(pr.id)

    po_service = POService(uow)
    po = po_service.create(
        pr_id=pr.id,
        vendor_name="Acme Supplies Co.",
        lines=[{"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}],
    )
    po_service.submit(po.id)
    po_service.approve(po.id)

    gr_service = GRService(uow)
    gr = gr_service.create(po_id=po.id, lines=[{"line_number": 1, "quantity_received": 10}])
    return gr_service.post(gr.id)


def test_paying_creates_a_second_balanced_journal_entry(uow):
    gr = posted_gr(uow)
    payment_service = PaymentService(uow)
    payment = payment_service.create(gr_id=gr.id, amount=gr.total_amount)
    payment_service.approve(payment.id)

    paid = payment_service.pay(payment.id)

    assert paid.status.value == "paid"
    entries = LedgerService(uow).list_journal_entries()
    assert len(entries) == 2
    assert entries[1].source_event == "PaymentPaid"


def test_second_payment_for_same_gr_rejected(uow):
    gr = posted_gr(uow)
    payment_service = PaymentService(uow)
    payment_service.create(gr_id=gr.id, amount=gr.total_amount)

    with pytest.raises(DomainValidationError):
        payment_service.create(gr_id=gr.id, amount=gr.total_amount)


def test_payment_amount_must_match_gr_total(uow):
    gr = posted_gr(uow)
    payment_service = PaymentService(uow)

    with pytest.raises(DomainValidationError):
        payment_service.create(gr_id=gr.id, amount=gr.total_amount - 1)


def test_trial_balance_is_balanced_after_full_flow(uow):
    gr = posted_gr(uow)
    payment_service = PaymentService(uow)
    payment = payment_service.create(gr_id=gr.id, amount=gr.total_amount)
    payment_service.approve(payment.id)
    payment_service.pay(payment.id)

    balances = LedgerService(uow).trial_balance()

    total_debit = sum(row["debit"] for row in balances.values())
    total_credit = sum(row["credit"] for row in balances.values())
    assert total_debit == total_credit
    assert balances["2100"]["debit"] == balances["2100"]["credit"] == gr.total_amount
