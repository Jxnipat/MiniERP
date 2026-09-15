import pytest

from app.domain.purchase_requisition.entities import (
    PRLine,
    PRStatus,
    PurchaseRequisition,
)
from app.domain.shared.errors import DomainValidationError
from app.domain.shared.state_machine import InvalidStateTransitionError


def make_pr() -> PurchaseRequisition:
    return PurchaseRequisition.create(
        requested_by="alice",
        lines=[PRLine(item_name="Laptop Stand", quantity=10, unit_price=25.50)],
    )


def test_new_pr_starts_as_draft():
    pr = make_pr()

    assert pr.status == PRStatus.DRAFT
    assert pr.total_amount == 255.0


def test_submit_moves_draft_to_submitted():
    pr = make_pr()

    pr.submit()

    assert pr.status == PRStatus.SUBMITTED


def test_approve_requires_submitted_first():
    pr = make_pr()

    with pytest.raises(InvalidStateTransitionError):
        pr.approve()


def test_full_approval_flow():
    pr = make_pr()
    pr.submit()

    pr.approve()

    assert pr.status == PRStatus.APPROVED


def test_reject_from_submitted():
    pr = make_pr()
    pr.submit()

    pr.reject()

    assert pr.status == PRStatus.REJECTED


def test_pr_requires_at_least_one_line():
    with pytest.raises(DomainValidationError):
        PurchaseRequisition.create(requested_by="alice", lines=[])


def test_pr_line_rejects_non_positive_quantity():
    with pytest.raises(DomainValidationError):
        PRLine(item_name="Laptop Stand", quantity=0, unit_price=25.50)
