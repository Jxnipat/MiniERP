import pytest

from app.application.services.gr_service import GRService
from app.application.services.po_service import POService
from app.application.services.pr_service import PRService
from app.domain.shared.errors import DomainValidationError


def approved_po(uow):
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
    return po_service.approve(po.id)


def draft_po(uow):
    pr_service = PRService(uow)
    pr = pr_service.create(
        requested_by="alice",
        lines=[{"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}],
    )
    pr_service.submit(pr.id)
    pr_service.approve(pr.id)

    po_service = POService(uow)
    return po_service.create(
        pr_id=pr.id,
        vendor_name="Acme Supplies Co.",
        lines=[{"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}],
    )


def test_posting_a_full_receipt_updates_po_and_creates_journal_entry(uow):
    po = approved_po(uow)
    gr_service = GRService(uow)
    gr = gr_service.create(po_id=po.id, lines=[{"line_number": 1, "quantity_received": 10}])

    posted = gr_service.post(gr.id)

    assert posted.status.value == "posted"
    assert posted.total_amount == 255.0

    updated_po = POService(uow).get(po.id)
    assert updated_po.status.value == "received"

    with uow:
        entries = uow.journal_repo.list()
    assert len(entries) == 1
    assert entries[0].source_event == "GoodsReceiptPosted"
    debit_line = next(l for l in entries[0].lines if l.debit)
    assert (debit_line.account_code, debit_line.debit) == ("1000", 255.0)


def test_partial_receipt_keeps_po_partially_received(uow):
    po = approved_po(uow)
    gr_service = GRService(uow)
    gr = gr_service.create(po_id=po.id, lines=[{"line_number": 1, "quantity_received": 4}])

    gr_service.post(gr.id)

    updated_po = POService(uow).get(po.id)
    assert updated_po.status.value == "partially_received"
    assert updated_po.lines[0].quantity_received == 4


def test_over_receiving_raises(uow):
    po = approved_po(uow)
    gr_service = GRService(uow)
    gr = gr_service.create(po_id=po.id, lines=[{"line_number": 1, "quantity_received": 11}])

    with pytest.raises(DomainValidationError):
        gr_service.post(gr.id)


def test_create_against_non_approved_po_raises(uow):
    po = draft_po(uow)
    gr_service = GRService(uow)

    with pytest.raises(DomainValidationError):
        gr_service.create(po_id=po.id, lines=[{"line_number": 1, "quantity_received": 5}])
