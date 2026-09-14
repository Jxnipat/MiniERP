import pytest

from app.domain.purchase_order.entities import POLine, POStatus, PurchaseOrder
from app.domain.purchase_requisition.entities import PRStatus
from app.domain.shared.errors import DomainValidationError
from app.domain.shared.state_machine import InvalidStateTransitionError


def make_po(status: POStatus = POStatus.APPROVED) -> PurchaseOrder:
    po = PurchaseOrder.create_from_pr(
        pr_id=1,
        pr_status=PRStatus.APPROVED,
        vendor_name="Acme Supplies Co.",
        lines=[POLine(line_number=1, item_name="Laptop Stand", quantity=10, unit_price=25.50)],
    )
    po.status = status
    return po


def test_create_from_pr_requires_approved_pr():
    with pytest.raises(DomainValidationError):
        PurchaseOrder.create_from_pr(
            pr_id=1,
            pr_status=PRStatus.DRAFT,
            vendor_name="Acme Supplies Co.",
            lines=[POLine(line_number=1, item_name="Laptop Stand", quantity=10, unit_price=25.50)],
        )


def test_new_po_starts_as_draft():
    po = PurchaseOrder.create_from_pr(
        pr_id=1,
        pr_status=PRStatus.APPROVED,
        vendor_name="Acme Supplies Co.",
        lines=[POLine(line_number=1, item_name="Laptop Stand", quantity=10, unit_price=25.50)],
    )

    assert po.status == POStatus.DRAFT
    assert po.total_amount == 255.0


def test_cancel_allowed_from_approved():
    po = make_po(status=POStatus.APPROVED)

    po.cancel()

    assert po.status == POStatus.CANCELLED


def test_cancel_not_allowed_after_received():
    po = make_po(status=POStatus.RECEIVED)

    with pytest.raises(InvalidStateTransitionError):
        po.cancel()


def test_receive_goods_partial_moves_to_partially_received():
    po = make_po(status=POStatus.APPROVED)

    po.receive_goods({1: 4})

    assert po.status == POStatus.PARTIALLY_RECEIVED
    assert po.lines[0].quantity_received == 4
    assert po.lines[0].remaining_quantity == 6


def test_receive_goods_full_moves_to_received():
    po = make_po(status=POStatus.APPROVED)

    po.receive_goods({1: 10})

    assert po.status == POStatus.RECEIVED


def test_receive_goods_over_quantity_raises():
    po = make_po(status=POStatus.APPROVED)

    with pytest.raises(DomainValidationError):
        po.receive_goods({1: 11})


def test_receive_goods_rejected_if_not_approved_or_partially_received():
    po = make_po(status=POStatus.DRAFT)

    with pytest.raises(DomainValidationError):
        po.receive_goods({1: 1})


def test_receive_goods_unknown_line_number_raises():
    po = make_po(status=POStatus.APPROVED)

    with pytest.raises(DomainValidationError):
        po.receive_goods({99: 1})


def test_close_requires_received_status():
    po = make_po(status=POStatus.RECEIVED)

    po.close()

    assert po.status == POStatus.CLOSED
