# Mini ERP: Procure-to-Pay Document State Machine + GL Engine (Design)

## Goal

Rebuild Mini ERP's backend around Clean Architecture / DDD to demonstrate:

- A **document state machine** for the full Procure-to-Pay chain:
  `Purchase Requisition (PR) → Purchase Order (PO) → Goods Receipt (GR) → Payment`
- An automated **General Ledger (GL) Engine** that reacts to domain events
  emitted by document state transitions and posts correct double-entry
  (debit = credit) journal entries — with no manual bookkeeping step.

This is a portfolio/learning project. Scope is deliberately limited: no
real authentication/RBAC, no concurrency hardening, no multi-currency.
The priority is demonstrating the patterns correctly, not
production-hardening them.

## Non-goals

- Real user authentication / RBAC enforcement (documents just carry a
  free-text `approved_by` string, no permission checks)
- Concurrent-user safety / optimistic locking
- Multi-currency, tax, installment/partial payments, or splitting one
  payment across multiple GRs — each GR is settled by exactly one
  full-amount Payment
- A UI for managing the Chart of Accounts (it's a fixed seed list)
- An async event bus / outbox pattern (see "Event dispatch" below)

## Architecture

Four layers, dependencies point inward. `domain` has zero framework
imports (no FastAPI, no SQLAlchemy) so business rules are testable in
isolation.

```
app/
├── domain/                          # pure Python, no framework deps
│   ├── shared/
│   │   ├── state_machine.py         # transition-table mixin + guard validation
│   │   └── domain_event.py          # DomainEvent base, AggregateRoot (holds _events)
│   ├── purchase_requisition/
│   │   ├── entities.py              # PurchaseRequisition, PRLine, PRStatus
│   │   └── events.py                # PRSubmitted, PRApproved, PRRejected
│   ├── purchase_order/
│   │   ├── entities.py              # PurchaseOrder, POLine, POStatus
│   │   └── events.py                # POApproved, GoodsFullyReceived, POClosed
│   ├── goods_receipt/
│   │   ├── entities.py              # GoodsReceipt, GRLine, GRStatus
│   │   └── events.py                # GoodsReceiptPosted
│   ├── payment/
│   │   ├── entities.py              # Payment, PaymentStatus
│   │   └── events.py                # PaymentPaid
│   └── accounting/
│       ├── entities.py              # Account, JournalEntry, JournalLine
│       └── chart_of_accounts.py     # fixed seed accounts
│
├── application/                     # use cases; knows domain, not concrete DB
│   ├── unit_of_work.py              # UnitOfWork abstract interface (Protocol)
│   ├── services/
│   │   ├── pr_service.py
│   │   ├── po_service.py
│   │   ├── gr_service.py
│   │   └── payment_service.py
│   └── gl_engine/
│       ├── posting_rules.py         # event type -> JournalEntry builder
│       └── gl_engine.py             # GLEngine.handle(event, uow)
│
├── infrastructure/
│   └── db/
│       ├── models.py                # SQLAlchemy ORM tables
│       ├── mappers.py               # entity <-> ORM row, both directions
│       ├── repositories.py          # concrete repos implementing the ports
│       ├── unit_of_work.py          # SqlAlchemyUnitOfWork
│       └── session.py               # engine + sessionmaker (SQLite)
│
└── interface/
    └── api/
        ├── schemas/                 # Pydantic request/response DTOs
        └── routers/
            ├── purchase_requisitions.py
            ├── purchase_orders.py
            ├── goods_receipts.py
            ├── payments.py
            └── ledger.py            # GET journal-entries, GET trial-balance
```

## Domain model & state machines

Each aggregate validates its own transitions and raises
`InvalidStateTransitionError` on an illegal move. Business-rule
violations (over-receiving, over-paying) raise
`DomainValidationError`. Both are caught at the API layer.

### Purchase Requisition (PR)
`DRAFT --submit()--> SUBMITTED --approve()--> APPROVED`
`SUBMITTED --reject()--> REJECTED`
No GL impact — internal request only.

### Purchase Order (PO)
Created **only** from a PR whose status is `APPROVED` (`pr_id` is a
required field on creation; creating against a non-approved PR raises
`DomainValidationError`).

`DRAFT --submit()--> SUBMITTED --approve()--> APPROVED`
`APPROVED --(partial receipt)--> PARTIALLY_RECEIVED --(full receipt)--> RECEIVED --close()--> CLOSED`
`DRAFT|SUBMITTED|APPROVED --cancel()--> CANCELLED`

`approve()` has no GL impact (budgetary commitment only). The
`PARTIALLY_RECEIVED` / `RECEIVED` transitions are driven indirectly by
`GoodsReceipt.post()` (see below), which updates the PO's per-line
received quantity. A guard rejects any receipt that would push a
line's received quantity past its ordered quantity.

### Goods Receipt (GR)
Created against a PO in status `APPROVED` or `PARTIALLY_RECEIVED`.

`DRAFT --post()--> POSTED`

`post()` is **GL trigger #1**:
1. Validates each line's received quantity ≤ the PO line's remaining quantity.
2. Updates the referenced PO's received quantities and status.
3. Emits `GoodsReceiptPosted(gr_id, amount)`.

### Payment
Created against a GR in status `POSTED`. Exactly one `Payment` settles
a GR in full: `amount` must equal the GR's total amount, and a GR can
have at most one non-cancelled Payment against it (creating a second
one raises `DomainValidationError`). Splitting a GR's payment across
installments is out of scope (see Non-goals).

`DRAFT --approve()--> APPROVED --pay()--> PAID`

`pay()` is **GL trigger #2**: emits `PaymentPaid(payment_id, gr_id, amount)`.

## GL Engine

### Chart of Accounts (fixed seed, no management UI)

| Code | Account          |
|------|------------------|
| 1000 | Inventory        |
| 1100 | Cash/Bank        |
| 2100 | GR/IR Clearing   |

### Posting rules

| Domain event          | Debit               | Credit              |
|------------------------|---------------------|----------------------|
| `GoodsReceiptPosted`   | 1000 Inventory      | 2100 GR/IR Clearing |
| `PaymentPaid`          | 2100 GR/IR Clearing | 1100 Cash/Bank       |

This models the standard two-step P2P accounting simplification for a
chain with no separate Invoice/AP step: goods receipt accrues a
liability in the clearing account; payment settles it.

### JournalEntry invariant

Enforced in the `JournalEntry` constructor, not by convention:
- Σdebit == Σcredit exactly
- Each `JournalLine` carries a value on exactly one side (never both, never neither)
- At least 2 lines
- Violation raises `UnbalancedJournalEntryError` at construction time —
  it is impossible to persist an unbalanced entry.

### Event dispatch

Synchronous, same-transaction. A service method (e.g.
`GoodsReceiptService.post`) runs inside one `UnitOfWork`:

```python
def post(self, gr_id: int) -> GoodsReceipt:
    with self.uow:
        gr = self.uow.gr_repo.get(gr_id)
        gr.post()  # domain method: validates, mutates state, records event
        for event in gr.pull_events():
            self.gl_engine.handle(event, self.uow)
        self.uow.commit()  # GR status + PO update + JournalEntry commit atomically
        return gr
```

If GL posting fails (e.g. a bug produces an unbalanced entry), the
whole transaction rolls back — the GR is never left `POSTED` without
its journal entry. An outbox/async event bus is explicitly out of
scope (see Non-goals) — it solves a distributed-systems problem this
single-process app doesn't have.

## Persistence

- SQLAlchemy ORM models are separate from domain entities: `PRModel`/`PRLineModel`,
  `POModel`/`POLineModel`, `GRModel`/`GRLineModel`, `PaymentModel`,
  `AccountModel` (seeded on startup), `JournalEntryModel`/`JournalLineModel`.
- `mappers.py` converts entity ↔ ORM row in both directions. Domain
  code never imports `infrastructure`.
- One repository per aggregate, implementing a `Protocol` declared in
  `application/`. Routers/services depend on the abstract port, not on
  SQLAlchemy directly.
- `SqlAlchemyUnitOfWork` wraps a `Session`, exposes repositories as
  properties, and is used as a context manager (`commit()`/`rollback()`).
- Runtime DB: SQLite file (`mini_erp.db`). Tests: `sqlite:///:memory:`,
  fresh per test — same pattern as the existing
  `tests/test_purchase_orders.py`, just backed by a real engine instead
  of a dict.

## API

```
POST   /purchase-requisitions              # create PR (DRAFT)
POST   /purchase-requisitions/{id}/submit
POST   /purchase-requisitions/{id}/approve
POST   /purchase-requisitions/{id}/reject
GET    /purchase-requisitions
GET    /purchase-requisitions/{id}

POST   /purchase-orders                    # requires pr_id (PR must be APPROVED)
POST   /purchase-orders/{id}/submit
POST   /purchase-orders/{id}/approve
POST   /purchase-orders/{id}/cancel
GET    /purchase-orders
GET    /purchase-orders/{id}

POST   /goods-receipts                     # requires po_id
POST   /goods-receipts/{id}/post           # <- GL trigger #1
GET    /goods-receipts
GET    /goods-receipts/{id}

POST   /payments                           # requires gr_id
POST   /payments/{id}/approve
POST   /payments/{id}/pay                  # <- GL trigger #2
GET    /payments
GET    /payments/{id}

GET    /ledger/journal-entries             # all posted journal entries
GET    /ledger/trial-balance               # sum(debit)/sum(credit) per account
```

This replaces the current `POST /purchase-orders` (which takes no
`pr_id` and has no upstream PR concept) — it's a breaking change to the
existing endpoint, made deliberately per the confirmed PR→PO linkage
requirement.

**Error mapping:** `InvalidStateTransitionError` → 409 Conflict;
`DomainValidationError` (over-receive, over-pay, PO created from a
non-approved PR) → 400 Bad Request; entity not found → 404 — consistent
with the existing `purchase_orders.py` router's style.

## Testing strategy

- **Domain unit tests** (no DB, no FastAPI): each aggregate's legal and
  illegal transitions; `JournalEntry` invariant (constructing an
  unbalanced entry must raise); each posting rule produces the correct
  `JournalEntry` for a given event.
- **Integration tests** (httpx `TestClient` + in-memory SQLite per
  test, extending the existing pattern in `tests/test_purchase_orders.py`):
  drive the full happy path PR → PO → GR → Payment through the API and
  assert `/ledger/trial-balance` balances and matches the expected
  amounts; cover error cases (skipping a required approval,
  over-receiving, over-paying, creating a PO from a non-approved PR).

## Migration notes

- The in-memory `app/database.py` module and the current flat
  `PurchaseOrder` model/router are superseded by the layered structure
  above. The existing PO tests
  ([tests/test_purchase_orders.py](../../../tests/test_purchase_orders.py))
  will need to be rewritten against the new API shape (PO creation now
  requires `pr_id`).
- `requirements.txt` gains `sqlalchemy` (both SQLite support and
  SQLAlchemy itself are free/open-source, no paid dependency).
