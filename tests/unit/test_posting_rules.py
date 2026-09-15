from app.domain.accounting.posting_rules import POSTING_RULES
from app.domain.goods_receipt.events import GoodsReceiptPosted
from app.domain.payment.events import PaymentPaid


def test_goods_receipt_posted_produces_balanced_inventory_entry():
    event = GoodsReceiptPosted(gr_id=1, amount=255.0)

    entry = POSTING_RULES[GoodsReceiptPosted](event)

    assert entry.source_event == "GoodsReceiptPosted"
    assert entry.source_id == 1
    debit_line = next(l for l in entry.lines if l.debit)
    credit_line = next(l for l in entry.lines if l.credit)
    assert (debit_line.account_code, debit_line.debit) == ("1000", 255.0)
    assert (credit_line.account_code, credit_line.credit) == ("2100", 255.0)


def test_payment_paid_produces_balanced_clearing_entry():
    event = PaymentPaid(payment_id=1, gr_id=2, amount=255.0)

    entry = POSTING_RULES[PaymentPaid](event)

    assert entry.source_event == "PaymentPaid"
    assert entry.source_id == 1
    debit_line = next(l for l in entry.lines if l.debit)
    credit_line = next(l for l in entry.lines if l.credit)
    assert (debit_line.account_code, debit_line.debit) == ("2100", 255.0)
    assert (credit_line.account_code, credit_line.credit) == ("1100", 255.0)
