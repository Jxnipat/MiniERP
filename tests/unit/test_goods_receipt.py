# tests/unit/test_goods_receipt.py
import pytest

from app.domain.goods_receipt.entities import GoodsReceipt, GRLine, GRStatus
from app.domain.goods_receipt.events import GoodsReceiptPosted
from app.domain.shared.errors import DomainValidationError
from app.domain.shared.state_machine import InvalidStateTransitionError


def make_gr() -> GoodsReceipt:
    return GoodsReceipt.create(po_id=1, lines=[GRLine(line_number=1, quantity_received=4)])


def test_new_gr_starts_as_draft():
    gr = make_gr()

    assert gr.status == GRStatus.DRAFT
    assert gr.total_amount is None


def test_post_moves_to_posted_and_records_event():
    gr = make_gr()
    gr.id = 7

    gr.post(amount=102.0)

    assert gr.status == GRStatus.POSTED
    assert gr.total_amount == 102.0
    events = gr.pull_events()
    assert len(events) == 1
    assert isinstance(events[0], GoodsReceiptPosted)
    assert events[0].gr_id == 7
    assert events[0].amount == 102.0


def test_cannot_post_twice():
    gr = make_gr()
    gr.id = 7
    gr.post(amount=102.0)

    with pytest.raises(InvalidStateTransitionError):
        gr.post(amount=102.0)


def test_gr_requires_at_least_one_line():
    with pytest.raises(DomainValidationError):
        GoodsReceipt.create(po_id=1, lines=[])


def test_gr_line_requires_positive_quantity():
    with pytest.raises(DomainValidationError):
        GRLine(line_number=1, quantity_received=0)
