# Mini ERP - Backend (Step 1: Purchase Orders)

A simple FastAPI backend, starting with the Purchase Order (PO) step
of the Procure-to-Pay workflow. No real database yet - everything is
stored in memory, so data resets whenever you restart the server.

## Folder structure

```
MiniERP/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app entry point
│   ├── models.py                # Pydantic models (data + validation)
│   ├── database.py               # In-memory "database" + business logic
│   └── routers/
│       ├── __init__.py
│       └── purchase_orders.py    # /purchase-orders API endpoints
├── requirements.txt
└── README.md
```

- **models.py** – defines what a Purchase Order looks like and validates input.
- **database.py** – stores orders in a Python dict and contains the rule "new orders always start as Draft".
- **routers/purchase_orders.py** – the actual API routes (HTTP layer only).
- **main.py** – creates the FastAPI app and wires the router in.

## Setup

```bash
python -m venv venv
source venv/bin/activate      # on Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload
```

Then open **http://127.0.0.1:8000/docs** for interactive Swagger docs
where you can try the API in your browser.

## Try it with curl

```bash
curl -X POST http://127.0.0.1:8000/purchase-orders \
  -H "Content-Type: application/json" \
  -d '{
        "vendor_name": "Acme Supplies Co.",
        "items": [
          {"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}
        ]
      }'
```

The response will always come back with `"status": "draft"`, even
though we never sent a status in the request - that's the business
rule enforced server-side in `database.py`.

List all orders:

```bash
curl http://127.0.0.1:8000/purchase-orders
```

## Next steps (not built yet)

- Swap the in-memory dict for a real database (e.g. SQLite via SQLAlchemy).
- Add the rest of the P2P lifecycle: PR, GR, AP, Payment.
- Add a real state machine (Draft -> Pending -> Approved) with RBAC.
- Add the automated GL (double-entry accounting) engine via domain events.
