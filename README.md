# Mini ERP - Backend (Procure-to-Pay with an automated GL Engine)

A FastAPI backend implementing the full Procure-to-Pay chain —
Purchase Requisition (PR) → Purchase Order (PO) → Goods Receipt (GR) →
Payment — built as a Clean Architecture / DDD application. Goods
Receipt and Payment transitions automatically trigger a GL Engine that
posts balanced double-entry journal entries; there is no manual
bookkeeping step anywhere in the flow.

See [docs/superpowers/specs/2026-09-15-p2p-clean-architecture-gl-engine-design.md](docs/superpowers/specs/2026-09-15-p2p-clean-architecture-gl-engine-design.md)
for the full design.

## Folder structure

```
MiniERP/
├── app/
│   ├── domain/            # pure Python business rules, no framework imports
│   │   ├── shared/            # state machine mixin, domain event base
│   │   ├── purchase_requisition/
│   │   ├── purchase_order/
│   │   ├── goods_receipt/
│   │   ├── payment/
│   │   └── accounting/        # JournalEntry invariant, GL posting rules
│   ├── application/        # use cases (services) + the GL engine
│   │   └── services/
│   ├── infrastructure/     # SQLAlchemy ORM models, mappers, repositories
│   │   └── db/
│   └── interface/          # FastAPI routers and Pydantic schemas
│       └── api/
├── requirements.txt
└── README.md
```

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

Then open **http://127.0.0.1:8000/docs** for interactive Swagger docs.
The database is a local SQLite file (`mini_erp.db`), created and
seeded with the chart of accounts automatically on startup.

## Try the full flow with curl

```bash
# 1. Create and approve a Purchase Requisition
PR_ID=$(curl -s -X POST http://127.0.0.1:8000/purchase-requisitions \
  -H "Content-Type: application/json" \
  -d '{"requested_by": "alice", "lines": [{"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}]}' \
  | python -c "import sys, json; print(json.load(sys.stdin)['id'])")
curl -X POST http://127.0.0.1:8000/purchase-requisitions/$PR_ID/submit
curl -X POST http://127.0.0.1:8000/purchase-requisitions/$PR_ID/approve

# 2. Create and approve a Purchase Order against it
PO_ID=$(curl -s -X POST http://127.0.0.1:8000/purchase-orders \
  -H "Content-Type: application/json" \
  -d "{\"pr_id\": $PR_ID, \"vendor_name\": \"Acme Supplies Co.\", \"lines\": [{\"item_name\": \"Laptop Stand\", \"quantity\": 10, \"unit_price\": 25.50}]}" \
  | python -c "import sys, json; print(json.load(sys.stdin)['id'])")
curl -X POST http://127.0.0.1:8000/purchase-orders/$PO_ID/submit
curl -X POST http://127.0.0.1:8000/purchase-orders/$PO_ID/approve

# 3. Receive the goods - this posts the first journal entry automatically
GR_ID=$(curl -s -X POST http://127.0.0.1:8000/goods-receipts \
  -H "Content-Type: application/json" \
  -d "{\"po_id\": $PO_ID, \"lines\": [{\"line_number\": 1, \"quantity_received\": 10}]}" \
  | python -c "import sys, json; print(json.load(sys.stdin)['id'])")
curl -X POST http://127.0.0.1:8000/goods-receipts/$GR_ID/post

# 4. Pay it - this posts the second journal entry automatically
PAYMENT_ID=$(curl -s -X POST http://127.0.0.1:8000/payments \
  -H "Content-Type: application/json" \
  -d "{\"gr_id\": $GR_ID, \"amount\": 255.0}" \
  | python -c "import sys, json; print(json.load(sys.stdin)['id'])")
curl -X POST http://127.0.0.1:8000/payments/$PAYMENT_ID/approve
curl -X POST http://127.0.0.1:8000/payments/$PAYMENT_ID/pay

# 5. Inspect the automatically-posted, balanced ledger
curl http://127.0.0.1:8000/ledger/journal-entries
curl http://127.0.0.1:8000/ledger/trial-balance
```

## Run tests

```bash
pytest
```

- `tests/unit/` — pure domain logic, no database (state machines, the
  `JournalEntry` debit=credit invariant, GL posting rules).
- `tests/integration/` — persistence and application-service tests
  against an in-memory SQLite database.
- `tests/api/` and `tests/test_full_p2p_flow.py` — the HTTP API,
  including the full PR→PO→GR→Payment golden path.

## Out of scope (by design)

No real authentication/RBAC, no concurrency control, no
multi-currency, no partial/installment payments, no async event bus —
see the design doc's "Non-goals" section for the reasoning.
