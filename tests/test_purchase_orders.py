"""
Tests for the Purchase Order API endpoints.

app/database.py keeps state in a module-level dict, so each test
resets it first to avoid orders leaking between tests.
"""

import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_database():
    database.purchase_orders.clear()
    database._next_id = 1
    yield


def sample_order_payload():
    return {
        "vendor_name": "Acme Supplies Co.",
        "items": [
            {"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}
        ],
    }


def test_create_purchase_order_defaults_to_draft():
    response = client.post("/purchase-orders", json=sample_order_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "draft"
    assert body["id"] == 1
    assert body["total_amount"] == 255.0


def test_create_purchase_order_rejects_empty_items():
    payload = sample_order_payload()
    payload["items"] = []

    response = client.post("/purchase-orders", json=payload)

    assert response.status_code == 422


def test_list_purchase_orders_returns_created_orders():
    client.post("/purchase-orders", json=sample_order_payload())
    client.post("/purchase-orders", json=sample_order_payload())

    response = client.get("/purchase-orders")

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_get_purchase_order_by_id():
    created = client.post("/purchase-orders", json=sample_order_payload()).json()

    response = client.get(f"/purchase-orders/{created['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_purchase_order_missing_returns_404():
    response = client.get("/purchase-orders/999")

    assert response.status_code == 404
