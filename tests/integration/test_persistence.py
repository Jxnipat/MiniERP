# tests/integration/test_persistence.py
import pytest

from app.domain.accounting.entities import JournalEntry, JournalLine
from app.domain.goods_receipt.entities import GoodsReceipt, GRLine, GRStatus
from app.domain.payment.entities import Payment
from app.domain.purchase_order.entities import POLine, POStatus, PurchaseOrder
from app.domain.purchase_requisition.entities import (
    PRLine,
    PRStatus,
    PurchaseRequisition,
)
from app.infrastructure.db.repositories import (
    SqlAlchemyGRRepository,
    SqlAlchemyJournalRepository,
    SqlAlchemyPaymentRepository,
    SqlAlchemyPORepository,
    SqlAlchemyPRRepository,
)


def test_pr_round_trip(session_factory):
    with session_factory() as session:
        repo = SqlAlchemyPRRepository(session)
        pr = PurchaseRequisition.create(
            requested_by="alice",
            lines=[PRLine(item_name="Laptop Stand", quantity=10, unit_price=25.50)],
        )

        repo.add(pr)
        session.commit()

        fetched = repo.get(pr.id)

    assert fetched.requested_by == "alice"
    assert fetched.status == PRStatus.DRAFT
    assert fetched.lines[0].item_name == "Laptop Stand"


def test_po_round_trip_and_update(session_factory):
    with session_factory() as session:
        repo = SqlAlchemyPORepository(session)
        po = PurchaseOrder.create_from_pr(
            pr_id=1,
            pr_status=PRStatus.APPROVED,
            vendor_name="Acme Supplies Co.",
            lines=[
                POLine(line_number=1, item_name="Laptop Stand", quantity=10, unit_price=25.50)
            ],
        )
        repo.add(po)
        session.commit()

        po.submit()
        po.approve()
        po.receive_goods({1: 4})
        repo.update(po)
        session.commit()

        fetched = repo.get(po.id)

    assert fetched.status == POStatus.PARTIALLY_RECEIVED
    assert fetched.lines[0].quantity_received == 4


def test_gr_round_trip(session_factory):
    with session_factory() as session:
        repo = SqlAlchemyGRRepository(session)
        gr = GoodsReceipt.create(po_id=1, lines=[GRLine(line_number=1, quantity_received=4)])
        repo.add(gr)
        session.commit()

        gr.post(amount=102.0)
        repo.update(gr)
        session.commit()

        fetched = repo.get(gr.id)

    assert fetched.status == GRStatus.POSTED
    assert fetched.total_amount == 102.0


def test_payment_and_journal_round_trip(session_factory):
    with session_factory() as session:
        payment_repo = SqlAlchemyPaymentRepository(session)
        journal_repo = SqlAlchemyJournalRepository(session)

        payment = Payment.create_for_gr(
            gr_id=1, gr_status=GRStatus.POSTED, gr_total_amount=100.0, amount=100.0
        )
        payment_repo.add(payment)
        session.commit()

        assert payment_repo.get_by_gr_id(1).id == payment.id

        entry = JournalEntry(
            source_event="Test",
            source_id=1,
            lines=[
                JournalLine(account_code="1000", debit=100.0),
                JournalLine(account_code="2100", credit=100.0),
            ],
        )
        journal_repo.add(entry)
        session.commit()

        entries = journal_repo.list()

    assert len(entries) == 1
    assert entries[0].lines[0].account_code == "1000"
