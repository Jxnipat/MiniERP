from app.domain.accounting.chart_of_accounts import CASH_BANK, GR_IR_CLEARING, INVENTORY
from app.domain.accounting.entities import JournalEntry, JournalLine
from app.domain.goods_receipt.events import GoodsReceiptPosted
from app.domain.payment.events import PaymentPaid


def build_journal_entry_for_goods_receipt_posted(
    event: GoodsReceiptPosted,
) -> JournalEntry:
    return JournalEntry(
        source_event="GoodsReceiptPosted",
        source_id=event.gr_id,
        lines=[
            JournalLine(account_code=INVENTORY.code, debit=event.amount),
            JournalLine(account_code=GR_IR_CLEARING.code, credit=event.amount),
        ],
    )


def build_journal_entry_for_payment_paid(event: PaymentPaid) -> JournalEntry:
    return JournalEntry(
        source_event="PaymentPaid",
        source_id=event.payment_id,
        lines=[
            JournalLine(account_code=GR_IR_CLEARING.code, debit=event.amount),
            JournalLine(account_code=CASH_BANK.code, credit=event.amount),
        ],
    )


POSTING_RULES = {
    GoodsReceiptPosted: build_journal_entry_for_goods_receipt_posted,
    PaymentPaid: build_journal_entry_for_payment_paid,
}
