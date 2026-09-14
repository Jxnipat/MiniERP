"""
End-to-end demonstration: a single Purchase Requisition flows all the
way through Purchase Order, Goods Receipt, and Payment, and the GL
Engine posts two balanced journal entries along the way with no manual
bookkeeping step.
"""


def test_full_procure_to_pay_flow_produces_a_balanced_ledger(client):
    pr = client.post(
        "/purchase-requisitions",
        json={
            "requested_by": "alice",
            "lines": [{"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}],
        },
    ).json()
    assert pr["status"] == "draft"

    client.post(f"/purchase-requisitions/{pr['id']}/submit")
    pr = client.post(f"/purchase-requisitions/{pr['id']}/approve").json()
    assert pr["status"] == "approved"

    po = client.post(
        "/purchase-orders",
        json={
            "pr_id": pr["id"],
            "vendor_name": "Acme Supplies Co.",
            "lines": [{"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}],
        },
    ).json()
    client.post(f"/purchase-orders/{po['id']}/submit")
    po = client.post(f"/purchase-orders/{po['id']}/approve").json()
    assert po["status"] == "approved"

    # Nothing hits the ledger until goods are actually received.
    assert client.get("/ledger/journal-entries").json() == []

    gr = client.post(
        "/goods-receipts",
        json={"po_id": po["id"], "lines": [{"line_number": 1, "quantity_received": 10}]},
    ).json()
    gr = client.post(f"/goods-receipts/{gr['id']}/post").json()
    assert gr["status"] == "posted"
    assert gr["total_amount"] == 255.0

    po_after_receipt = client.get(f"/purchase-orders/{po['id']}").json()
    assert po_after_receipt["status"] == "received"

    entries = client.get("/ledger/journal-entries").json()
    assert len(entries) == 1
    gr_entry = entries[0]
    assert gr_entry["source_event"] == "GoodsReceiptPosted"
    debit = next(l for l in gr_entry["lines"] if l["debit"])
    credit = next(l for l in gr_entry["lines"] if l["credit"])
    assert (debit["account_code"], debit["debit"]) == ("1000", 255.0)
    assert (credit["account_code"], credit["credit"]) == ("2100", 255.0)

    payment = client.post("/payments", json={"gr_id": gr["id"], "amount": 255.0}).json()
    client.post(f"/payments/{payment['id']}/approve")
    payment = client.post(f"/payments/{payment['id']}/pay").json()
    assert payment["status"] == "paid"

    entries = client.get("/ledger/journal-entries").json()
    assert len(entries) == 2
    payment_entry = entries[1]
    assert payment_entry["source_event"] == "PaymentPaid"
    debit = next(l for l in payment_entry["lines"] if l["debit"])
    credit = next(l for l in payment_entry["lines"] if l["credit"])
    assert (debit["account_code"], debit["debit"]) == ("2100", 255.0)
    assert (credit["account_code"], credit["credit"]) == ("1100", 255.0)

    trial_balance = {
        row["account_code"]: row for row in client.get("/ledger/trial-balance").json()
    }
    assert trial_balance["1000"]["debit"] == 255.0
    assert trial_balance["2100"]["debit"] == trial_balance["2100"]["credit"] == 255.0
    assert trial_balance["1100"]["credit"] == 255.0
    total_debit = sum(row["debit"] for row in trial_balance.values())
    total_credit = sum(row["credit"] for row in trial_balance.values())
    assert total_debit == total_credit
