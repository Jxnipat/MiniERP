def sample_pr_payload():
    return {
        "requested_by": "alice",
        "lines": [{"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}],
    }


def test_create_and_full_approval_flow(client):
    response = client.post("/purchase-requisitions", json=sample_pr_payload())
    assert response.status_code == 201
    pr = response.json()
    assert pr["status"] == "draft"

    client.post(f"/purchase-requisitions/{pr['id']}/submit")
    response = client.post(f"/purchase-requisitions/{pr['id']}/approve")

    assert response.status_code == 200
    assert response.json()["status"] == "approved"


def test_approve_without_submit_returns_409(client):
    pr = client.post("/purchase-requisitions", json=sample_pr_payload()).json()

    response = client.post(f"/purchase-requisitions/{pr['id']}/approve")

    assert response.status_code == 409


def test_get_missing_pr_returns_404(client):
    response = client.get("/purchase-requisitions/999")

    assert response.status_code == 404


def test_create_rejects_empty_lines(client):
    response = client.post(
        "/purchase-requisitions", json={"requested_by": "alice", "lines": []}
    )

    assert response.status_code == 422
