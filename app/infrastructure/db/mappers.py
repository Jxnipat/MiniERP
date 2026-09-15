# app/infrastructure/db/mappers.py
from app.domain.accounting.entities import JournalEntry, JournalLine
from app.domain.goods_receipt.entities import GoodsReceipt, GRLine, GRStatus
from app.domain.payment.entities import Payment, PaymentStatus
from app.domain.purchase_order.entities import POLine, POStatus, PurchaseOrder
from app.domain.purchase_requisition.entities import (
    PRLine,
    PRStatus,
    PurchaseRequisition,
)
from app.infrastructure.db.models import (
    GRLineModel,
    GRModel,
    JournalEntryModel,
    JournalLineModel,
    PaymentModel,
    POLineModel,
    POModel,
    PRLineModel,
    PRModel,
)


def pr_to_model(pr: PurchaseRequisition) -> PRModel:
    return PRModel(
        id=pr.id,
        requested_by=pr.requested_by,
        status=pr.status.value,
        created_at=pr.created_at,
        lines=[
            PRLineModel(item_name=l.item_name, quantity=l.quantity, unit_price=l.unit_price)
            for l in pr.lines
        ],
    )


def pr_to_domain(model: PRModel) -> PurchaseRequisition:
    return PurchaseRequisition(
        id=model.id,
        requested_by=model.requested_by,
        status=PRStatus(model.status),
        created_at=model.created_at,
        lines=[
            PRLine(item_name=l.item_name, quantity=l.quantity, unit_price=l.unit_price)
            for l in model.lines
        ],
    )


def po_to_model(po: PurchaseOrder) -> POModel:
    return POModel(
        id=po.id,
        pr_id=po.pr_id,
        vendor_name=po.vendor_name,
        status=po.status.value,
        created_at=po.created_at,
        lines=[
            POLineModel(
                line_number=l.line_number,
                item_name=l.item_name,
                quantity=l.quantity,
                unit_price=l.unit_price,
                quantity_received=l.quantity_received,
            )
            for l in po.lines
        ],
    )


def po_to_domain(model: POModel) -> PurchaseOrder:
    return PurchaseOrder(
        id=model.id,
        pr_id=model.pr_id,
        vendor_name=model.vendor_name,
        status=POStatus(model.status),
        created_at=model.created_at,
        lines=[
            POLine(
                line_number=l.line_number,
                item_name=l.item_name,
                quantity=l.quantity,
                unit_price=l.unit_price,
                quantity_received=l.quantity_received,
            )
            for l in model.lines
        ],
    )


def gr_to_model(gr: GoodsReceipt) -> GRModel:
    return GRModel(
        id=gr.id,
        po_id=gr.po_id,
        status=gr.status.value,
        total_amount=gr.total_amount,
        created_at=gr.created_at,
        lines=[
            GRLineModel(line_number=l.line_number, quantity_received=l.quantity_received)
            for l in gr.lines
        ],
    )


def gr_to_domain(model: GRModel) -> GoodsReceipt:
    return GoodsReceipt(
        id=model.id,
        po_id=model.po_id,
        status=GRStatus(model.status),
        total_amount=model.total_amount,
        created_at=model.created_at,
        lines=[
            GRLine(line_number=l.line_number, quantity_received=l.quantity_received)
            for l in model.lines
        ],
    )


def payment_to_model(payment: Payment) -> PaymentModel:
    return PaymentModel(
        id=payment.id,
        gr_id=payment.gr_id,
        amount=payment.amount,
        status=payment.status.value,
        created_at=payment.created_at,
    )


def payment_to_domain(model: PaymentModel) -> Payment:
    return Payment(
        id=model.id,
        gr_id=model.gr_id,
        amount=model.amount,
        status=PaymentStatus(model.status),
        created_at=model.created_at,
    )


def journal_entry_to_model(entry: JournalEntry) -> JournalEntryModel:
    return JournalEntryModel(
        id=entry.id,
        source_event=entry.source_event,
        source_id=entry.source_id,
        posted_at=entry.posted_at,
        lines=[
            JournalLineModel(account_code=l.account_code, debit=l.debit, credit=l.credit)
            for l in entry.lines
        ],
    )


def journal_entry_to_domain(model: JournalEntryModel) -> JournalEntry:
    return JournalEntry(
        id=model.id,
        source_event=model.source_event,
        source_id=model.source_id,
        posted_at=model.posted_at,
        lines=[
            JournalLine(account_code=l.account_code, debit=l.debit, credit=l.credit)
            for l in model.lines
        ],
    )
