def approved_po(client):
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
    return po


def test_post_goods_receipt_returns_200_and_updates_po(client):
    po = approved_po(client)
    gr = client.post(
        "/goods-receipts",
        json={"po_id": po["id"], "lines": [{"line_number": 1, "quantity_received": 10}]},
    ).json()

    response = client.post(f"/goods-receipts/{gr['id']}/post")

    assert response.status_code == 200
    assert response.json()["status"] == "posted"
    assert response.json()["total_amount"] == 255.0

    po_after = client.get(f"/purchase-orders/{po['id']}").json()
    assert po_after["status"] == "received"


def test_over_receiving_returns_400(client):
    po = approved_po(client)
    gr = client.post(
        "/goods-receipts",
        json={"po_id": po["id"], "lines": [{"line_number": 1, "quantity_received": 11}]},
    ).json()

    response = client.post(f"/goods-receipts/{gr['id']}/post")

    assert response.status_code == 400
