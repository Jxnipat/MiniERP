import pytest

from app.application.services.pr_service import PRService
from app.domain.purchase_requisition.entities import PRStatus
from app.domain.shared.errors import NotFoundError
from app.domain.shared.state_machine import InvalidStateTransitionError


def test_create_and_get(uow):
    service = PRService(uow)

    pr = service.create(
        requested_by="alice",
        lines=[{"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}],
    )

    assert pr.id is not None
    fetched = service.get(pr.id)
    assert fetched.requested_by == "alice"


def test_full_approval_flow(uow):
    service = PRService(uow)
    pr = service.create(
        requested_by="alice",
        lines=[{"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}],
    )

    service.submit(pr.id)
    approved = service.approve(pr.id)

    assert approved.status == PRStatus.APPROVED


def test_approve_before_submit_raises(uow):
    service = PRService(uow)
    pr = service.create(
        requested_by="alice",
        lines=[{"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}],
    )

    with pytest.raises(InvalidStateTransitionError):
        service.approve(pr.id)


def test_get_missing_raises_not_found(uow):
    service = PRService(uow)

    with pytest.raises(NotFoundError):
        service.get(999)
