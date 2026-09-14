import pytest

from app.application.services.po_service import POService
from app.application.services.pr_service import PRService
from app.domain.shared.errors import DomainValidationError


def approved_pr_id(uow) -> int:
    pr_service = PRService(uow)
    pr = pr_service.create(
        requested_by="alice",
        lines=[{"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}],
    )
    pr_service.submit(pr.id)
    pr_service.approve(pr.id)
    return pr.id


def test_create_po_from_approved_pr(uow):
    pr_id = approved_pr_id(uow)
    service = POService(uow)

    po = service.create(
        pr_id=pr_id,
        vendor_name="Acme Supplies Co.",
        lines=[{"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}],
    )

    assert po.pr_id == pr_id
    assert po.lines[0].line_number == 1


def test_create_po_from_non_approved_pr_raises(uow):
    pr_service = PRService(uow)
    pr = pr_service.create(
        requested_by="alice",
        lines=[{"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}],
    )
    service = POService(uow)

    with pytest.raises(DomainValidationError):
        service.create(
            pr_id=pr.id,
            vendor_name="Acme Supplies Co.",
            lines=[{"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}],
        )


def test_approve_and_cancel_flow(uow):
    pr_id = approved_pr_id(uow)
    service = POService(uow)
    po = service.create(
        pr_id=pr_id,
        vendor_name="Acme Supplies Co.",
        lines=[{"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}],
    )

    service.submit(po.id)
    approved = service.approve(po.id)
    assert approved.status.value == "approved"

    cancelled = service.cancel(po.id)
    assert cancelled.status.value == "cancelled"
