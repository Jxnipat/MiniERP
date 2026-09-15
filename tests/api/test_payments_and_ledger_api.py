def posted_gr(client):
    pr = client.post(
        "/purchase-requisitions",
        json={
            "requested_by": "alice",
            "lines": [{"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}],
        },
    ).json()
    client.post(f"/purchase-requisitions/{pr['id']}/submit")
    client.post(f"/purchase-requisitions/{pr['id']}/approve")

    po = client.post(
        "/purchase-orders",
        json={
            "pr_id": pr["id"],
            "vendor_name": "Acme Supplies Co.",
            "lines": [{"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}],
        },
    ).json()
    client.post(f"/purchase-orders/{po['id']}/submit")
    client.post(f"/purchase-orders/{po['id']}/approve")

    gr = client.post(
        "/goods-receipts",
        json={"po_id": po["id"], "lines": [{"line_number": 1, "quantity_received": 10}]},
    ).json()
    return client.post(f"/goods-receipts/{gr['id']}/post").json()


def test_full_payment_flow_and_ledger(client):
    gr = posted_gr(client)
    payment = client.post(
        "/payments", json={"gr_id": gr["id"], "amount": gr["total_amount"]}
    ).json()
    client.post(f"/payments/{payment['id']}/approve")

    response = client.post(f"/payments/{payment['id']}/pay")

    assert response.status_code == 200
    assert response.json()["status"] == "paid"

    entries = client.get("/ledger/journal-entries").json()
    assert len(entries) == 2

    trial_balance = client.get("/ledger/trial-balance").json()
    total_debit = sum(row["debit"] for row in trial_balance)
    total_credit = sum(row["credit"] for row in trial_balance)
    assert total_debit == total_credit == gr["total_amount"] * 2


def test_duplicate_payment_returns_400(client):
    gr = posted_gr(client)
    client.post("/payments", json={"gr_id": gr["id"], "amount": gr["total_amount"]})

    response = client.post(
        "/payments", json={"gr_id": gr["id"], "amount": gr["total_amount"]}
    )

    assert response.status_code == 400
