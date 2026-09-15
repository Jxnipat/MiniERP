def approved_pr_id(client) -> int:
    pr = client.post(
        "/purchase-requisitions",
        json={
            "requested_by": "alice",
            "lines": [{"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}],
        },
    ).json()
    client.post(f"/purchase-requisitions/{pr['id']}/submit")
    client.post(f"/purchase-requisitions/{pr['id']}/approve")
    return pr["id"]


def test_create_po_requires_pr_id(client):
    pr_id = approved_pr_id(client)

    response = client.post(
        "/purchase-orders",
        json={
            "pr_id": pr_id,
            "vendor_name": "Acme Supplies Co.",
            "lines": [{"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}],
        },
    )

    assert response.status_code == 201
    assert response.json()["pr_id"] == pr_id


def test_create_po_from_non_approved_pr_returns_400(client):
    pr = client.post(
        "/purchase-requisitions",
        json={
            "requested_by": "alice",
            "lines": [{"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}],
        },
    ).json()

    response = client.post(
        "/purchase-orders",
        json={
            "pr_id": pr["id"],
            "vendor_name": "Acme Supplies Co.",
            "lines": [{"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}],
        },
    )

    assert response.status_code == 400


def test_submit_approve_cancel_flow(client):
    pr_id = approved_pr_id(client)
    po = client.post(
        "/purchase-orders",
        json={
            "pr_id": pr_id,
            "vendor_name": "Acme Supplies Co.",
            "lines": [{"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}],
        },
    ).json()

    client.post(f"/purchase-orders/{po['id']}/submit")
    client.post(f"/purchase-orders/{po['id']}/approve")
    response = client.post(f"/purchase-orders/{po['id']}/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
