# P2P Document State Machine + GL Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild Mini ERP's backend as a Clean Architecture / DDD application implementing the full Procure-to-Pay chain (PR → PO → GR → Payment), where Goods Receipt and Payment transitions automatically trigger a GL Engine that posts balanced double-entry journal entries.

**Architecture:** Four layers (`domain` → `application` → `infrastructure`/`interface`, dependencies point inward). `domain` is pure Python with zero framework imports. `application` orchestrates use cases and dispatches domain events to the GL Engine inside one SQLAlchemy transaction per operation. `infrastructure` maps domain entities to SQLAlchemy ORM rows. `interface` exposes FastAPI routers.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x, SQLite, pytest, httpx (`TestClient`).

**Spec:** [docs/superpowers/specs/2026-09-15-p2p-clean-architecture-gl-engine-design.md](../specs/2026-09-15-p2p-clean-architecture-gl-engine-design.md)

## Global Constraints

- `app/domain/**` must never import FastAPI or SQLAlchemy — it is pure Python, testable with no I/O.
- Persistence is SQLite everywhere: `sqlite:///./mini_erp.db` at runtime, `sqlite:///:memory:` in tests.
- A GR's `post()` and a Payment's `pay()` must never commit without their GL journal entry committing in the *same* transaction — no partial state is ever persisted.
- `JournalEntry` cannot be constructed unless Σdebit == Σcredit exactly, each line has a value on exactly one side, and there are ≥2 lines — enforced in the constructor itself, not by a separate validation pass.
- Each Goods Receipt is settled by exactly one full-amount Payment. No partial/installment payments, no multi-currency, no RBAC/auth, no concurrency control (all confirmed out of scope in the design doc's Non-goals).
- Error mapping is fixed: `NotFoundError` → HTTP 404, `InvalidStateTransitionError` → HTTP 409, `DomainValidationError` → HTTP 400.

---

## Task 1: Shared domain kernel

**Files:**
- Create: `app/domain/__init__.py` (empty)
- Create: `app/domain/shared/__init__.py` (empty)
- Create: `app/domain/shared/errors.py`
- Create: `app/domain/shared/domain_event.py`
- Create: `app/domain/shared/state_machine.py`
- Test: `tests/unit/test_state_machine.py`
- Test: `tests/unit/test_domain_event.py`

**Interfaces:**
- Produces: `DomainValidationError`, `NotFoundError` (both plain `Exception` subclasses); `DomainEvent` (frozen dataclass, has `occurred_at: datetime`, kw-only); `AggregateRoot` (`.record_event(event)`, `.pull_events() -> list[DomainEvent]`); `InvalidStateTransitionError`; `StateMachineMixin` (class attribute `TRANSITIONS: dict`, method `._transition(action: str) -> None` that reads/writes `self.status`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_state_machine.py
import pytest

from app.domain.shared.state_machine import InvalidStateTransitionError, StateMachineMixin


class TrafficLight(StateMachineMixin):
    TRANSITIONS = {
        "red": {"go": "green"},
        "green": {"caution": "yellow"},
        "yellow": {"stop": "red"},
    }

    def __init__(self) -> None:
        self.status = "red"


def test_legal_transition_changes_status():
    light = TrafficLight()

    light._transition("go")

    assert light.status == "green"


def test_illegal_transition_raises_and_leaves_status_unchanged():
    light = TrafficLight()

    with pytest.raises(InvalidStateTransitionError):
        light._transition("stop")

    assert light.status == "red"
```

```python
# tests/unit/test_domain_event.py
from dataclasses import dataclass

from app.domain.shared.domain_event import AggregateRoot, DomainEvent


@dataclass(frozen=True)
class SomethingHappened(DomainEvent):
    payload: str


class Widget(AggregateRoot):
    def do_something(self) -> None:
        self.record_event(SomethingHappened(payload="done"))


def test_pull_events_returns_and_clears_recorded_events():
    widget = Widget()
    widget.do_something()

    events = widget.pull_events()

    assert len(events) == 1
    assert events[0].payload == "done"
    assert widget.pull_events() == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_state_machine.py tests/unit/test_domain_event.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.domain'`

- [ ] **Step 3: Create the empty package files**

Create `app/domain/__init__.py` and `app/domain/shared/__init__.py` as empty files.

- [ ] **Step 4: Implement `errors.py`**

```python
# app/domain/shared/errors.py
class DomainValidationError(Exception):
    """Raised when an operation violates a business rule (not a state-machine rule)."""


class NotFoundError(Exception):
    """Raised when a requested aggregate does not exist."""
```

- [ ] **Step 5: Implement `domain_event.py`**

```python
# app/domain/shared/domain_event.py
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class DomainEvent:
    occurred_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc), kw_only=True
    )


class AggregateRoot:
    def __init__(self) -> None:
        self._events: list[DomainEvent] = []

    def record_event(self, event: DomainEvent) -> None:
        self._events.append(event)

    def pull_events(self) -> list[DomainEvent]:
        events = self._events
        self._events = []
        return events
```

- [ ] **Step 6: Implement `state_machine.py`**

```python
# app/domain/shared/state_machine.py
class InvalidStateTransitionError(Exception):
    def __init__(self, current_state, action: str) -> None:
        super().__init__(f"cannot perform '{action}' from state '{current_state}'")
        self.current_state = current_state
        self.action = action


class StateMachineMixin:
    """
    Mix into any entity with a `status` attribute. Subclasses declare a
    class-level `TRANSITIONS` dict shaped {current_status: {action: next_status}}
    and call self._transition(action) inside each action method.
    """

    TRANSITIONS: dict = {}

    def _transition(self, action: str) -> None:
        allowed = self.TRANSITIONS.get(self.status, {})
        if action not in allowed:
            raise InvalidStateTransitionError(self.status, action)
        self.status = allowed[action]
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/unit/test_state_machine.py tests/unit/test_domain_event.py -v`
Expected: PASS (4 tests)

- [ ] **Step 8: Commit**

```bash
git add app/domain/__init__.py app/domain/shared/ tests/unit/test_state_machine.py tests/unit/test_domain_event.py
git commit -m "Add shared domain kernel: errors, domain events, state machine mixin"
```

---

## Task 2: Accounting domain — Account, JournalLine, JournalEntry, chart of accounts

**Files:**
- Create: `app/domain/accounting/__init__.py` (empty)
- Create: `app/domain/accounting/entities.py`
- Create: `app/domain/accounting/chart_of_accounts.py`
- Test: `tests/unit/test_accounting_entities.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `UnbalancedJournalEntryError`; `Account(code: str, name: str)`; `JournalLine(account_code: str, debit: float = 0.0, credit: float = 0.0)`; `JournalEntry(source_event: str, source_id: int, lines: list[JournalLine], id: int | None = None, posted_at: datetime = ...)`; `INVENTORY`, `CASH_BANK`, `GR_IR_CLEARING` (each an `Account`), `SEED_ACCOUNTS: list[Account]`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_accounting_entities.py
import pytest

from app.domain.accounting.entities import (
    JournalEntry,
    JournalLine,
    UnbalancedJournalEntryError,
)


def test_balanced_entry_is_accepted():
    entry = JournalEntry(
        source_event="Test",
        source_id=1,
        lines=[
            JournalLine(account_code="1000", debit=100.0),
            JournalLine(account_code="2100", credit=100.0),
        ],
    )

    assert len(entry.lines) == 2


def test_unbalanced_entry_raises():
    with pytest.raises(UnbalancedJournalEntryError):
        JournalEntry(
            source_event="Test",
            source_id=1,
            lines=[
                JournalLine(account_code="1000", debit=100.0),
                JournalLine(account_code="2100", credit=50.0),
            ],
        )


def test_entry_needs_at_least_two_lines():
    with pytest.raises(UnbalancedJournalEntryError):
        JournalEntry(
            source_event="Test",
            source_id=1,
            lines=[JournalLine(account_code="1000", debit=100.0)],
        )


def test_line_cannot_have_both_debit_and_credit():
    with pytest.raises(UnbalancedJournalEntryError):
        JournalLine(account_code="1000", debit=100.0, credit=100.0)


def test_line_needs_a_value_on_one_side():
    with pytest.raises(UnbalancedJournalEntryError):
        JournalLine(account_code="1000")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_accounting_entities.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.domain.accounting'`

- [ ] **Step 3: Implement `entities.py`**

```python
# app/domain/accounting/entities.py
from dataclasses import dataclass, field
from datetime import datetime, timezone


class UnbalancedJournalEntryError(Exception):
    pass


@dataclass(frozen=True)
class Account:
    code: str
    name: str


@dataclass(frozen=True)
class JournalLine:
    account_code: str
    debit: float = 0.0
    credit: float = 0.0

    def __post_init__(self) -> None:
        if self.debit < 0 or self.credit < 0:
            raise UnbalancedJournalEntryError("debit/credit cannot be negative")
        if (self.debit > 0) == (self.credit > 0):
            raise UnbalancedJournalEntryError(
                "a journal line must have a value on exactly one side"
            )


@dataclass
class JournalEntry:
    source_event: str
    source_id: int
    lines: list[JournalLine]
    id: int | None = None
    posted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if len(self.lines) < 2:
            raise UnbalancedJournalEntryError("a journal entry needs at least 2 lines")
        total_debit = round(sum(line.debit for line in self.lines), 2)
        total_credit = round(sum(line.credit for line in self.lines), 2)
        if total_debit != total_credit:
            raise UnbalancedJournalEntryError(
                f"unbalanced entry: debit={total_debit} credit={total_credit}"
            )
```

- [ ] **Step 4: Implement `chart_of_accounts.py`**

```python
# app/domain/accounting/chart_of_accounts.py
from app.domain.accounting.entities import Account

INVENTORY = Account(code="1000", name="Inventory")
CASH_BANK = Account(code="1100", name="Cash/Bank")
GR_IR_CLEARING = Account(code="2100", name="GR/IR Clearing")

SEED_ACCOUNTS: list[Account] = [INVENTORY, CASH_BANK, GR_IR_CLEARING]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_accounting_entities.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add app/domain/accounting/ tests/unit/test_accounting_entities.py
git commit -m "Add accounting domain: JournalEntry invariant and chart of accounts"
```

---

## Task 3: Purchase Requisition entity

**Files:**
- Create: `app/domain/purchase_requisition/__init__.py` (empty)
- Create: `app/domain/purchase_requisition/entities.py`
- Test: `tests/unit/test_purchase_requisition.py`

**Interfaces:**
- Consumes: `DomainValidationError`, `StateMachineMixin` (Task 1).
- Produces: `PRStatus` (str Enum: `DRAFT`, `SUBMITTED`, `APPROVED`, `REJECTED`); `PRLine(item_name: str, quantity: int, unit_price: float)`; `PurchaseRequisition` with `.create(requested_by, lines) -> PurchaseRequisition` classmethod, `.id`, `.requested_by`, `.lines`, `.status`, `.created_at`, `.total_amount` (property), `.submit()`, `.approve()`, `.reject()`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_purchase_requisition.py
import pytest

from app.domain.purchase_requisition.entities import (
    PRLine,
    PRStatus,
    PurchaseRequisition,
)
from app.domain.shared.errors import DomainValidationError
from app.domain.shared.state_machine import InvalidStateTransitionError


def make_pr() -> PurchaseRequisition:
    return PurchaseRequisition.create(
        requested_by="alice",
        lines=[PRLine(item_name="Laptop Stand", quantity=10, unit_price=25.50)],
    )


def test_new_pr_starts_as_draft():
    pr = make_pr()

    assert pr.status == PRStatus.DRAFT
    assert pr.total_amount == 255.0


def test_submit_moves_draft_to_submitted():
    pr = make_pr()

    pr.submit()

    assert pr.status == PRStatus.SUBMITTED


def test_approve_requires_submitted_first():
    pr = make_pr()

    with pytest.raises(InvalidStateTransitionError):
        pr.approve()


def test_full_approval_flow():
    pr = make_pr()
    pr.submit()

    pr.approve()

    assert pr.status == PRStatus.APPROVED


def test_reject_from_submitted():
    pr = make_pr()
    pr.submit()

    pr.reject()

    assert pr.status == PRStatus.REJECTED


def test_pr_requires_at_least_one_line():
    with pytest.raises(DomainValidationError):
        PurchaseRequisition.create(requested_by="alice", lines=[])


def test_pr_line_rejects_non_positive_quantity():
    with pytest.raises(DomainValidationError):
        PRLine(item_name="Laptop Stand", quantity=0, unit_price=25.50)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_purchase_requisition.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.domain.purchase_requisition'`

- [ ] **Step 3: Implement `entities.py`**

```python
# app/domain/purchase_requisition/entities.py
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from app.domain.shared.errors import DomainValidationError
from app.domain.shared.state_machine import StateMachineMixin


class PRStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class PRLine:
    item_name: str
    quantity: int
    unit_price: float

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise DomainValidationError("quantity must be greater than 0")
        if self.unit_price <= 0:
            raise DomainValidationError("unit_price must be greater than 0")


class PurchaseRequisition(StateMachineMixin):
    TRANSITIONS = {
        PRStatus.DRAFT: {"submit": PRStatus.SUBMITTED},
        PRStatus.SUBMITTED: {
            "approve": PRStatus.APPROVED,
            "reject": PRStatus.REJECTED,
        },
    }

    def __init__(
        self,
        requested_by: str,
        lines: list[PRLine],
        id: int | None = None,
        status: PRStatus = PRStatus.DRAFT,
        created_at: datetime | None = None,
    ) -> None:
        if not lines:
            raise DomainValidationError("a purchase requisition needs at least one line")
        self.id = id
        self.requested_by = requested_by
        self.lines = lines
        self.status = status
        self.created_at = created_at or datetime.now(timezone.utc)

    @classmethod
    def create(cls, requested_by: str, lines: list[PRLine]) -> "PurchaseRequisition":
        return cls(requested_by=requested_by, lines=lines)

    @property
    def total_amount(self) -> float:
        return sum(line.quantity * line.unit_price for line in self.lines)

    def submit(self) -> None:
        self._transition("submit")

    def approve(self) -> None:
        self._transition("approve")

    def reject(self) -> None:
        self._transition("reject")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_purchase_requisition.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add app/domain/purchase_requisition/ tests/unit/test_purchase_requisition.py
git commit -m "Add PurchaseRequisition entity with Draft->Submitted->Approved/Rejected state machine"
```

---

## Task 4: Purchase Order entity (including partial/full goods receipt)

**Files:**
- Create: `app/domain/purchase_order/__init__.py` (empty)
- Create: `app/domain/purchase_order/entities.py`
- Test: `tests/unit/test_purchase_order.py`

**Interfaces:**
- Consumes: `PRStatus` (Task 3), `DomainValidationError`, `StateMachineMixin` (Task 1).
- Produces: `POStatus` (str Enum: `DRAFT`, `SUBMITTED`, `APPROVED`, `PARTIALLY_RECEIVED`, `RECEIVED`, `CLOSED`, `CANCELLED`); `POLine(line_number: int, item_name: str, quantity: int, unit_price: float, quantity_received: int = 0)` with `.remaining_quantity` property; `PurchaseOrder` with `.create_from_pr(pr_id, pr_status, vendor_name, lines) -> PurchaseOrder` classmethod (raises `DomainValidationError` if `pr_status != PRStatus.APPROVED`), `.id`, `.pr_id`, `.vendor_name`, `.lines`, `.status`, `.created_at`, `.total_amount` (property), `.submit()`, `.approve()`, `.cancel()`, `.close()`, `.receive_goods(received_lines: dict[int, int]) -> None`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_purchase_order.py
import pytest

from app.domain.purchase_order.entities import POLine, POStatus, PurchaseOrder
from app.domain.purchase_requisition.entities import PRStatus
from app.domain.shared.errors import DomainValidationError
from app.domain.shared.state_machine import InvalidStateTransitionError


def make_po(status: POStatus = POStatus.APPROVED) -> PurchaseOrder:
    po = PurchaseOrder.create_from_pr(
        pr_id=1,
        pr_status=PRStatus.APPROVED,
        vendor_name="Acme Supplies Co.",
        lines=[POLine(line_number=1, item_name="Laptop Stand", quantity=10, unit_price=25.50)],
    )
    po.status = status
    return po


def test_create_from_pr_requires_approved_pr():
    with pytest.raises(DomainValidationError):
        PurchaseOrder.create_from_pr(
            pr_id=1,
            pr_status=PRStatus.DRAFT,
            vendor_name="Acme Supplies Co.",
            lines=[POLine(line_number=1, item_name="Laptop Stand", quantity=10, unit_price=25.50)],
        )


def test_new_po_starts_as_draft():
    po = PurchaseOrder.create_from_pr(
        pr_id=1,
        pr_status=PRStatus.APPROVED,
        vendor_name="Acme Supplies Co.",
        lines=[POLine(line_number=1, item_name="Laptop Stand", quantity=10, unit_price=25.50)],
    )

    assert po.status == POStatus.DRAFT
    assert po.total_amount == 255.0


def test_cancel_allowed_from_approved():
    po = make_po(status=POStatus.APPROVED)

    po.cancel()

    assert po.status == POStatus.CANCELLED


def test_cancel_not_allowed_after_received():
    po = make_po(status=POStatus.RECEIVED)

    with pytest.raises(InvalidStateTransitionError):
        po.cancel()


def test_receive_goods_partial_moves_to_partially_received():
    po = make_po(status=POStatus.APPROVED)

    po.receive_goods({1: 4})

    assert po.status == POStatus.PARTIALLY_RECEIVED
    assert po.lines[0].quantity_received == 4
    assert po.lines[0].remaining_quantity == 6


def test_receive_goods_full_moves_to_received():
    po = make_po(status=POStatus.APPROVED)

    po.receive_goods({1: 10})

    assert po.status == POStatus.RECEIVED


def test_receive_goods_over_quantity_raises():
    po = make_po(status=POStatus.APPROVED)

    with pytest.raises(DomainValidationError):
        po.receive_goods({1: 11})


def test_receive_goods_rejected_if_not_approved_or_partially_received():
    po = make_po(status=POStatus.DRAFT)

    with pytest.raises(DomainValidationError):
        po.receive_goods({1: 1})


def test_receive_goods_unknown_line_number_raises():
    po = make_po(status=POStatus.APPROVED)

    with pytest.raises(DomainValidationError):
        po.receive_goods({99: 1})


def test_close_requires_received_status():
    po = make_po(status=POStatus.RECEIVED)

    po.close()

    assert po.status == POStatus.CLOSED
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_purchase_order.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.domain.purchase_order'`

- [ ] **Step 3: Implement `entities.py`**

```python
# app/domain/purchase_order/entities.py
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from app.domain.purchase_requisition.entities import PRStatus
from app.domain.shared.errors import DomainValidationError
from app.domain.shared.state_machine import StateMachineMixin


class POStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    PARTIALLY_RECEIVED = "partially_received"
    RECEIVED = "received"
    CLOSED = "closed"
    CANCELLED = "cancelled"


@dataclass
class POLine:
    line_number: int
    item_name: str
    quantity: int
    unit_price: float
    quantity_received: int = 0

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise DomainValidationError("quantity must be greater than 0")
        if self.unit_price <= 0:
            raise DomainValidationError("unit_price must be greater than 0")

    @property
    def remaining_quantity(self) -> int:
        return self.quantity - self.quantity_received


class PurchaseOrder(StateMachineMixin):
    TRANSITIONS = {
        POStatus.DRAFT: {"submit": POStatus.SUBMITTED, "cancel": POStatus.CANCELLED},
        POStatus.SUBMITTED: {
            "approve": POStatus.APPROVED,
            "cancel": POStatus.CANCELLED,
        },
        POStatus.APPROVED: {"cancel": POStatus.CANCELLED},
        POStatus.RECEIVED: {"close": POStatus.CLOSED},
    }

    def __init__(
        self,
        pr_id: int,
        vendor_name: str,
        lines: list[POLine],
        id: int | None = None,
        status: POStatus = POStatus.DRAFT,
        created_at: datetime | None = None,
    ) -> None:
        if not lines:
            raise DomainValidationError("a purchase order needs at least one line")
        self.id = id
        self.pr_id = pr_id
        self.vendor_name = vendor_name
        self.lines = lines
        self.status = status
        self.created_at = created_at or datetime.now(timezone.utc)

    @classmethod
    def create_from_pr(
        cls,
        pr_id: int,
        pr_status: PRStatus,
        vendor_name: str,
        lines: list[POLine],
    ) -> "PurchaseOrder":
        if pr_status != PRStatus.APPROVED:
            raise DomainValidationError(
                f"cannot create a purchase order from PR #{pr_id}: PR is not approved"
            )
        return cls(pr_id=pr_id, vendor_name=vendor_name, lines=lines)

    @property
    def total_amount(self) -> float:
        return sum(line.quantity * line.unit_price for line in self.lines)

    def submit(self) -> None:
        self._transition("submit")

    def approve(self) -> None:
        self._transition("approve")

    def cancel(self) -> None:
        self._transition("cancel")

    def close(self) -> None:
        self._transition("close")

    def receive_goods(self, received_lines: dict[int, int]) -> None:
        """
        received_lines: {line_number: quantity received in this delivery}.
        Not a plain `_transition()` call because the resulting status
        depends on the quantities, not just a fixed action->state map.
        """
        if self.status not in (POStatus.APPROVED, POStatus.PARTIALLY_RECEIVED):
            raise DomainValidationError(
                f"cannot receive goods against a PO in status '{self.status}'"
            )

        lines_by_number = {line.line_number: line for line in self.lines}
        for line_number, qty in received_lines.items():
            line = lines_by_number.get(line_number)
            if line is None:
                raise DomainValidationError(f"PO has no line number {line_number}")
            if qty > line.remaining_quantity:
                raise DomainValidationError(
                    f"line {line_number}: cannot receive {qty}, only "
                    f"{line.remaining_quantity} remaining"
                )
            line.quantity_received += qty

        if all(line.remaining_quantity == 0 for line in self.lines):
            self.status = POStatus.RECEIVED
        else:
            self.status = POStatus.PARTIALLY_RECEIVED
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_purchase_order.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add app/domain/purchase_order/ tests/unit/test_purchase_order.py
git commit -m "Add PurchaseOrder entity with partial/full goods receipt logic"
```

---

## Task 5: Goods Receipt entity + event

**Files:**
- Create: `app/domain/goods_receipt/__init__.py` (empty)
- Create: `app/domain/goods_receipt/events.py`
- Create: `app/domain/goods_receipt/entities.py`
- Test: `tests/unit/test_goods_receipt.py`

**Interfaces:**
- Consumes: `DomainEvent`, `AggregateRoot`, `StateMachineMixin`, `InvalidStateTransitionError`, `DomainValidationError` (Task 1).
- Produces: `GoodsReceiptPosted(gr_id: int, amount: float)` (frozen `DomainEvent`); `GRStatus` (str Enum: `DRAFT`, `POSTED`); `GRLine(line_number: int, quantity_received: int)`; `GoodsReceipt` with `.create(po_id, lines) -> GoodsReceipt` classmethod, `.id`, `.po_id`, `.lines`, `.status`, `.total_amount: float | None`, `.created_at`, `.post(amount: float) -> None` (transitions + records `GoodsReceiptPosted`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_goods_receipt.py
import pytest

from app.domain.goods_receipt.entities import GoodsReceipt, GRLine, GRStatus
from app.domain.goods_receipt.events import GoodsReceiptPosted
from app.domain.shared.errors import DomainValidationError
from app.domain.shared.state_machine import InvalidStateTransitionError


def make_gr() -> GoodsReceipt:
    return GoodsReceipt.create(po_id=1, lines=[GRLine(line_number=1, quantity_received=4)])


def test_new_gr_starts_as_draft():
    gr = make_gr()

    assert gr.status == GRStatus.DRAFT
    assert gr.total_amount is None


def test_post_moves_to_posted_and_records_event():
    gr = make_gr()
    gr.id = 7

    gr.post(amount=102.0)

    assert gr.status == GRStatus.POSTED
    assert gr.total_amount == 102.0
    events = gr.pull_events()
    assert len(events) == 1
    assert isinstance(events[0], GoodsReceiptPosted)
    assert events[0].gr_id == 7
    assert events[0].amount == 102.0


def test_cannot_post_twice():
    gr = make_gr()
    gr.id = 7
    gr.post(amount=102.0)

    with pytest.raises(InvalidStateTransitionError):
        gr.post(amount=102.0)


def test_gr_requires_at_least_one_line():
    with pytest.raises(DomainValidationError):
        GoodsReceipt.create(po_id=1, lines=[])


def test_gr_line_requires_positive_quantity():
    with pytest.raises(DomainValidationError):
        GRLine(line_number=1, quantity_received=0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_goods_receipt.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.domain.goods_receipt'`

- [ ] **Step 3: Implement `events.py`**

```python
# app/domain/goods_receipt/events.py
from dataclasses import dataclass

from app.domain.shared.domain_event import DomainEvent


@dataclass(frozen=True)
class GoodsReceiptPosted(DomainEvent):
    gr_id: int
    amount: float
```

- [ ] **Step 4: Implement `entities.py`**

```python
# app/domain/goods_receipt/entities.py
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from app.domain.goods_receipt.events import GoodsReceiptPosted
from app.domain.shared.domain_event import AggregateRoot
from app.domain.shared.errors import DomainValidationError
from app.domain.shared.state_machine import StateMachineMixin


class GRStatus(str, Enum):
    DRAFT = "draft"
    POSTED = "posted"


@dataclass
class GRLine:
    line_number: int
    quantity_received: int

    def __post_init__(self) -> None:
        if self.quantity_received <= 0:
            raise DomainValidationError("quantity_received must be greater than 0")


class GoodsReceipt(StateMachineMixin, AggregateRoot):
    TRANSITIONS = {
        GRStatus.DRAFT: {"post": GRStatus.POSTED},
    }

    def __init__(
        self,
        po_id: int,
        lines: list[GRLine],
        id: int | None = None,
        status: GRStatus = GRStatus.DRAFT,
        total_amount: float | None = None,
        created_at: datetime | None = None,
    ) -> None:
        AggregateRoot.__init__(self)
        if not lines:
            raise DomainValidationError("a goods receipt needs at least one line")
        self.id = id
        self.po_id = po_id
        self.lines = lines
        self.status = status
        self.total_amount = total_amount
        self.created_at = created_at or datetime.now(timezone.utc)

    @classmethod
    def create(cls, po_id: int, lines: list[GRLine]) -> "GoodsReceipt":
        return cls(po_id=po_id, lines=lines)

    def post(self, amount: float) -> None:
        self._transition("post")
        self.total_amount = amount
        self.record_event(GoodsReceiptPosted(gr_id=self.id, amount=amount))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_goods_receipt.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add app/domain/goods_receipt/ tests/unit/test_goods_receipt.py
git commit -m "Add GoodsReceipt entity emitting GoodsReceiptPosted on post()"
```

---

## Task 6: Payment entity + event

**Files:**
- Create: `app/domain/payment/__init__.py` (empty)
- Create: `app/domain/payment/events.py`
- Create: `app/domain/payment/entities.py`
- Test: `tests/unit/test_payment.py`

**Interfaces:**
- Consumes: `GRStatus` (Task 5), `DomainEvent`, `AggregateRoot`, `StateMachineMixin`, `InvalidStateTransitionError`, `DomainValidationError` (Task 1).
- Produces: `PaymentPaid(payment_id: int, gr_id: int, amount: float)` (frozen `DomainEvent`); `PaymentStatus` (str Enum: `DRAFT`, `APPROVED`, `PAID`); `Payment` with `.create_for_gr(gr_id, gr_status, gr_total_amount, amount) -> Payment` classmethod (raises `DomainValidationError` if GR not posted or amount mismatches), `.id`, `.gr_id`, `.amount`, `.status`, `.created_at`, `.approve()`, `.pay()` (transitions + records `PaymentPaid`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_payment.py
import pytest

from app.domain.goods_receipt.entities import GRStatus
from app.domain.payment.entities import Payment, PaymentStatus
from app.domain.payment.events import PaymentPaid
from app.domain.shared.errors import DomainValidationError
from app.domain.shared.state_machine import InvalidStateTransitionError


def test_create_for_gr_requires_posted_gr():
    with pytest.raises(DomainValidationError):
        Payment.create_for_gr(
            gr_id=1, gr_status=GRStatus.DRAFT, gr_total_amount=100.0, amount=100.0
        )


def test_create_for_gr_requires_matching_amount():
    with pytest.raises(DomainValidationError):
        Payment.create_for_gr(
            gr_id=1, gr_status=GRStatus.POSTED, gr_total_amount=100.0, amount=50.0
        )


def test_full_payment_flow_records_event():
    payment = Payment.create_for_gr(
        gr_id=1, gr_status=GRStatus.POSTED, gr_total_amount=100.0, amount=100.0
    )
    payment.id = 9

    payment.approve()
    payment.pay()

    assert payment.status == PaymentStatus.PAID
    events = payment.pull_events()
    assert len(events) == 1
    assert isinstance(events[0], PaymentPaid)
    assert events[0].payment_id == 9
    assert events[0].gr_id == 1
    assert events[0].amount == 100.0


def test_cannot_pay_before_approval():
    payment = Payment.create_for_gr(
        gr_id=1, gr_status=GRStatus.POSTED, gr_total_amount=100.0, amount=100.0
    )

    with pytest.raises(InvalidStateTransitionError):
        payment.pay()


def test_amount_must_be_positive():
    with pytest.raises(DomainValidationError):
        Payment(gr_id=1, amount=0.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_payment.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.domain.payment'`

- [ ] **Step 3: Implement `events.py`**

```python
# app/domain/payment/events.py
from dataclasses import dataclass

from app.domain.shared.domain_event import DomainEvent


@dataclass(frozen=True)
class PaymentPaid(DomainEvent):
    payment_id: int
    gr_id: int
    amount: float
```

- [ ] **Step 4: Implement `entities.py`**

```python
# app/domain/payment/entities.py
from datetime import datetime, timezone
from enum import Enum

from app.domain.goods_receipt.entities import GRStatus
from app.domain.payment.events import PaymentPaid
from app.domain.shared.domain_event import AggregateRoot
from app.domain.shared.errors import DomainValidationError
from app.domain.shared.state_machine import StateMachineMixin


class PaymentStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    PAID = "paid"


class Payment(StateMachineMixin, AggregateRoot):
    TRANSITIONS = {
        PaymentStatus.DRAFT: {"approve": PaymentStatus.APPROVED},
        PaymentStatus.APPROVED: {"pay": PaymentStatus.PAID},
    }

    def __init__(
        self,
        gr_id: int,
        amount: float,
        id: int | None = None,
        status: PaymentStatus = PaymentStatus.DRAFT,
        created_at: datetime | None = None,
    ) -> None:
        AggregateRoot.__init__(self)
        if amount <= 0:
            raise DomainValidationError("amount must be greater than 0")
        self.id = id
        self.gr_id = gr_id
        self.amount = amount
        self.status = status
        self.created_at = created_at or datetime.now(timezone.utc)

    @classmethod
    def create_for_gr(
        cls, gr_id: int, gr_status: GRStatus, gr_total_amount: float, amount: float
    ) -> "Payment":
        if gr_status != GRStatus.POSTED:
            raise DomainValidationError(
                f"cannot create a payment for GR #{gr_id}: GR is not posted"
            )
        if round(amount, 2) != round(gr_total_amount, 2):
            raise DomainValidationError(
                f"payment amount {amount} must equal the goods receipt total "
                f"{gr_total_amount}"
            )
        return cls(gr_id=gr_id, amount=amount)

    def approve(self) -> None:
        self._transition("approve")

    def pay(self) -> None:
        self._transition("pay")
        self.record_event(
            PaymentPaid(payment_id=self.id, gr_id=self.gr_id, amount=self.amount)
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_payment.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add app/domain/payment/ tests/unit/test_payment.py
git commit -m "Add Payment entity emitting PaymentPaid on pay()"
```

---

## Task 7: GL posting rules

**Files:**
- Create: `app/domain/accounting/posting_rules.py`
- Test: `tests/unit/test_posting_rules.py`

**Interfaces:**
- Consumes: `INVENTORY`, `CASH_BANK`, `GR_IR_CLEARING` (Task 2), `JournalEntry`, `JournalLine` (Task 2), `GoodsReceiptPosted` (Task 5), `PaymentPaid` (Task 6).
- Produces: `POSTING_RULES: dict[type, Callable]` mapping an event class to a `(event) -> JournalEntry` builder function.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_posting_rules.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_posting_rules.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.domain.accounting.posting_rules'`

- [ ] **Step 3: Implement `posting_rules.py`**

```python
# app/domain/accounting/posting_rules.py
from app.domain.accounting.chart_of_accounts import CASH_BANK, GR_IR_CLEARING, INVENTORY
from app.domain.accounting.entities import JournalEntry, JournalLine
from app.domain.goods_receipt.events import GoodsReceiptPosted
from app.domain.payment.events import PaymentPaid


def build_journal_entry_for_goods_receipt_posted(
    event: GoodsReceiptPosted,
) -> JournalEntry:
    return JournalEntry(
        source_event="GoodsReceiptPosted",
        source_id=event.gr_id,
        lines=[
            JournalLine(account_code=INVENTORY.code, debit=event.amount),
            JournalLine(account_code=GR_IR_CLEARING.code, credit=event.amount),
        ],
    )


def build_journal_entry_for_payment_paid(event: PaymentPaid) -> JournalEntry:
    return JournalEntry(
        source_event="PaymentPaid",
        source_id=event.payment_id,
        lines=[
            JournalLine(account_code=GR_IR_CLEARING.code, debit=event.amount),
            JournalLine(account_code=CASH_BANK.code, credit=event.amount),
        ],
    )


POSTING_RULES = {
    GoodsReceiptPosted: build_journal_entry_for_goods_receipt_posted,
    PaymentPaid: build_journal_entry_for_payment_paid,
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_posting_rules.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add app/domain/accounting/posting_rules.py tests/unit/test_posting_rules.py
git commit -m "Add GL posting rules mapping domain events to journal entries"
```

---

## Task 8: Infrastructure bootstrap — ORM models, engine/session, account seeding

**Files:**
- Create: `app/infrastructure/__init__.py` (empty)
- Create: `app/infrastructure/db/__init__.py` (empty)
- Create: `app/infrastructure/db/base.py`
- Create: `app/infrastructure/db/models.py`
- Create: `app/infrastructure/db/session.py`
- Test: `tests/integration/test_db_bootstrap.py`

**Interfaces:**
- Consumes: `SEED_ACCOUNTS` (Task 2).
- Produces: `Base` (SQLAlchemy declarative base); ORM models `AccountModel`, `PRModel`, `PRLineModel`, `POModel`, `POLineModel`, `GRModel`, `GRLineModel`, `PaymentModel`, `JournalEntryModel`, `JournalLineModel`; `engine`, `SessionLocal` (sessionmaker); `init_db() -> None`; `seed_accounts(session) -> None` (idempotent).

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_db_bootstrap.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.infrastructure.db.base import Base
from app.infrastructure.db.models import AccountModel
from app.infrastructure.db.session import seed_accounts


def test_seed_accounts_creates_the_three_fixed_accounts():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    with factory() as session:
        seed_accounts(session)
        session.commit()
        codes = {a.code for a in session.query(AccountModel).all()}

    assert codes == {"1000", "1100", "2100"}
    engine.dispose()


def test_seed_accounts_is_idempotent():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    with factory() as session:
        seed_accounts(session)
        session.commit()
        seed_accounts(session)
        session.commit()
        count = session.query(AccountModel).count()

    assert count == 3
    engine.dispose()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_db_bootstrap.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.infrastructure'`

- [ ] **Step 3: Add `sqlalchemy` to `requirements.txt`**

```
fastapi
uvicorn[standard]
pydantic
sqlalchemy

# Testing
pytest
httpx
```

Run: `pip install -r requirements.txt`

- [ ] **Step 4: Implement `base.py`**

```python
# app/infrastructure/db/base.py
from sqlalchemy.orm import declarative_base

Base = declarative_base()
```

- [ ] **Step 5: Implement `models.py`**

```python
# app/infrastructure/db/models.py
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.infrastructure.db.base import Base


class AccountModel(Base):
    __tablename__ = "accounts"

    code = Column(String, primary_key=True)
    name = Column(String, nullable=False)


class PRModel(Base):
    __tablename__ = "purchase_requisitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    requested_by = Column(String, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)

    lines = relationship("PRLineModel", cascade="all, delete-orphan", backref="pr")


class PRLineModel(Base):
    __tablename__ = "pr_lines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pr_id = Column(Integer, ForeignKey("purchase_requisitions.id"), nullable=False)
    item_name = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)


class POModel(Base):
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pr_id = Column(Integer, ForeignKey("purchase_requisitions.id"), nullable=False)
    vendor_name = Column(String, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)

    lines = relationship("POLineModel", cascade="all, delete-orphan", backref="po")


class POLineModel(Base):
    __tablename__ = "po_lines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    po_id = Column(Integer, ForeignKey("purchase_orders.id"), nullable=False)
    line_number = Column(Integer, nullable=False)
    item_name = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    quantity_received = Column(Integer, nullable=False, default=0)


class GRModel(Base):
    __tablename__ = "goods_receipts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    po_id = Column(Integer, ForeignKey("purchase_orders.id"), nullable=False)
    status = Column(String, nullable=False)
    total_amount = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False)

    lines = relationship("GRLineModel", cascade="all, delete-orphan", backref="gr")


class GRLineModel(Base):
    __tablename__ = "gr_lines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    gr_id = Column(Integer, ForeignKey("goods_receipts.id"), nullable=False)
    line_number = Column(Integer, nullable=False)
    quantity_received = Column(Integer, nullable=False)


class PaymentModel(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    gr_id = Column(Integer, ForeignKey("goods_receipts.id"), nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)


class JournalEntryModel(Base):
    __tablename__ = "journal_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_event = Column(String, nullable=False)
    source_id = Column(Integer, nullable=False)
    posted_at = Column(DateTime, nullable=False)

    lines = relationship(
        "JournalLineModel", cascade="all, delete-orphan", backref="entry"
    )


class JournalLineModel(Base):
    __tablename__ = "journal_lines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entry_id = Column(Integer, ForeignKey("journal_entries.id"), nullable=False)
    account_code = Column(String, nullable=False)
    debit = Column(Float, nullable=False, default=0.0)
    credit = Column(Float, nullable=False, default=0.0)
```

- [ ] **Step 6: Implement `session.py`**

```python
# app/infrastructure/db/session.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.domain.accounting.chart_of_accounts import SEED_ACCOUNTS
from app.infrastructure.db.base import Base
from app.infrastructure.db.models import AccountModel

DATABASE_URL = "sqlite:///./mini_erp.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)


def seed_accounts(session) -> None:
    for account in SEED_ACCOUNTS:
        if session.get(AccountModel, account.code) is None:
            session.add(AccountModel(code=account.code, name=account.name))


def init_db() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        seed_accounts(session)
        session.commit()
```

- [ ] **Step 7: Run test to verify it passes**

Run: `pytest tests/integration/test_db_bootstrap.py -v`
Expected: PASS (2 tests)

- [ ] **Step 8: Commit**

```bash
git add requirements.txt app/infrastructure/ tests/integration/test_db_bootstrap.py
git commit -m "Add SQLAlchemy ORM models, engine/session setup, and account seeding"
```

---

## Task 9: Mappers and repositories

**Files:**
- Create: `app/infrastructure/db/mappers.py`
- Create: `app/infrastructure/db/repositories.py`
- Create: `tests/conftest.py`
- Test: `tests/integration/test_persistence.py`

**Interfaces:**
- Consumes: all domain entities (Tasks 2–6), all ORM models (Task 8).
- Produces: mapper functions `pr_to_model`, `pr_to_domain`, `po_to_model`, `po_to_domain`, `gr_to_model`, `gr_to_domain`, `payment_to_model`, `payment_to_domain`, `journal_entry_to_model`, `journal_entry_to_domain`; repository classes `SqlAlchemyPRRepository`, `SqlAlchemyPORepository`, `SqlAlchemyGRRepository`, `SqlAlchemyPaymentRepository`, `SqlAlchemyJournalRepository`, each constructed with `(session)` and exposing `.add(entity) -> entity` (sets `.id`), `.get(id) -> entity | None`, `.list() -> list[entity]`, `.update(entity) -> None` (`PaymentRepository` additionally exposes `.get_by_gr_id(gr_id) -> Payment | None`; `JournalRepository` has no `.update`, entries are immutable once posted). `tests/conftest.py` produces pytest fixtures `session_factory` and `uow`, reused by every later integration/API test.

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_persistence.py
import pytest

from app.domain.accounting.entities import JournalEntry, JournalLine
from app.domain.goods_receipt.entities import GoodsReceipt, GRLine, GRStatus
from app.domain.payment.entities import Payment
from app.domain.purchase_order.entities import POLine, POStatus, PurchaseOrder
from app.domain.purchase_requisition.entities import (
    PRLine,
    PRStatus,
    PurchaseRequisition,
)
from app.infrastructure.db.repositories import (
    SqlAlchemyGRRepository,
    SqlAlchemyJournalRepository,
    SqlAlchemyPaymentRepository,
    SqlAlchemyPORepository,
    SqlAlchemyPRRepository,
)


def test_pr_round_trip(session_factory):
    with session_factory() as session:
        repo = SqlAlchemyPRRepository(session)
        pr = PurchaseRequisition.create(
            requested_by="alice",
            lines=[PRLine(item_name="Laptop Stand", quantity=10, unit_price=25.50)],
        )

        repo.add(pr)
        session.commit()

        fetched = repo.get(pr.id)

    assert fetched.requested_by == "alice"
    assert fetched.status == PRStatus.DRAFT
    assert fetched.lines[0].item_name == "Laptop Stand"


def test_po_round_trip_and_update(session_factory):
    with session_factory() as session:
        repo = SqlAlchemyPORepository(session)
        po = PurchaseOrder.create_from_pr(
            pr_id=1,
            pr_status=PRStatus.APPROVED,
            vendor_name="Acme Supplies Co.",
            lines=[
                POLine(line_number=1, item_name="Laptop Stand", quantity=10, unit_price=25.50)
            ],
        )
        repo.add(po)
        session.commit()

        po.receive_goods({1: 4})
        repo.update(po)
        session.commit()

        fetched = repo.get(po.id)

    assert fetched.status == POStatus.PARTIALLY_RECEIVED
    assert fetched.lines[0].quantity_received == 4


def test_gr_round_trip(session_factory):
    with session_factory() as session:
        repo = SqlAlchemyGRRepository(session)
        gr = GoodsReceipt.create(po_id=1, lines=[GRLine(line_number=1, quantity_received=4)])
        repo.add(gr)
        session.commit()

        gr.post(amount=102.0)
        repo.update(gr)
        session.commit()

        fetched = repo.get(gr.id)

    assert fetched.status == GRStatus.POSTED
    assert fetched.total_amount == 102.0


def test_payment_and_journal_round_trip(session_factory):
    with session_factory() as session:
        payment_repo = SqlAlchemyPaymentRepository(session)
        journal_repo = SqlAlchemyJournalRepository(session)

        payment = Payment.create_for_gr(
            gr_id=1, gr_status=GRStatus.POSTED, gr_total_amount=100.0, amount=100.0
        )
        payment_repo.add(payment)
        session.commit()

        assert payment_repo.get_by_gr_id(1).id == payment.id

        entry = JournalEntry(
            source_event="Test",
            source_id=1,
            lines=[
                JournalLine(account_code="1000", debit=100.0),
                JournalLine(account_code="2100", credit=100.0),
            ],
        )
        journal_repo.add(entry)
        session.commit()

        entries = journal_repo.list()

    assert len(entries) == 1
    assert entries[0].lines[0].account_code == "1000"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_persistence.py -v`
Expected: FAIL with `fixture 'session_factory' not found`

- [ ] **Step 3: Create `tests/conftest.py`**

```python
# tests/conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.infrastructure.db.base import Base
from app.infrastructure.db.session import seed_accounts


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        seed_accounts(session)
        session.commit()
    yield factory
    engine.dispose()
```

Task 10 appends a `uow` fixture to this same file once `SqlAlchemyUnitOfWork` exists — nothing here references it yet, so this task's tests are self-contained.

- [ ] **Step 4: Implement `mappers.py`**

```python
# app/infrastructure/db/mappers.py
from app.domain.accounting.entities import JournalEntry, JournalLine
from app.domain.goods_receipt.entities import GoodsReceipt, GRLine, GRStatus
from app.domain.payment.entities import Payment, PaymentStatus
from app.domain.purchase_order.entities import POLine, POStatus, PurchaseOrder
from app.domain.purchase_requisition.entities import (
    PRLine,
    PRStatus,
    PurchaseRequisition,
)
from app.infrastructure.db.models import (
    GRLineModel,
    GRModel,
    JournalEntryModel,
    JournalLineModel,
    PaymentModel,
    POLineModel,
    POModel,
    PRLineModel,
    PRModel,
)


def pr_to_model(pr: PurchaseRequisition) -> PRModel:
    return PRModel(
        id=pr.id,
        requested_by=pr.requested_by,
        status=pr.status.value,
        created_at=pr.created_at,
        lines=[
            PRLineModel(item_name=l.item_name, quantity=l.quantity, unit_price=l.unit_price)
            for l in pr.lines
        ],
    )


def pr_to_domain(model: PRModel) -> PurchaseRequisition:
    return PurchaseRequisition(
        id=model.id,
        requested_by=model.requested_by,
        status=PRStatus(model.status),
        created_at=model.created_at,
        lines=[
            PRLine(item_name=l.item_name, quantity=l.quantity, unit_price=l.unit_price)
            for l in model.lines
        ],
    )


def po_to_model(po: PurchaseOrder) -> POModel:
    return POModel(
        id=po.id,
        pr_id=po.pr_id,
        vendor_name=po.vendor_name,
        status=po.status.value,
        created_at=po.created_at,
        lines=[
            POLineModel(
                line_number=l.line_number,
                item_name=l.item_name,
                quantity=l.quantity,
                unit_price=l.unit_price,
                quantity_received=l.quantity_received,
            )
            for l in po.lines
        ],
    )


def po_to_domain(model: POModel) -> PurchaseOrder:
    return PurchaseOrder(
        id=model.id,
        pr_id=model.pr_id,
        vendor_name=model.vendor_name,
        status=POStatus(model.status),
        created_at=model.created_at,
        lines=[
            POLine(
                line_number=l.line_number,
                item_name=l.item_name,
                quantity=l.quantity,
                unit_price=l.unit_price,
                quantity_received=l.quantity_received,
            )
            for l in model.lines
        ],
    )


def gr_to_model(gr: GoodsReceipt) -> GRModel:
    return GRModel(
        id=gr.id,
        po_id=gr.po_id,
        status=gr.status.value,
        total_amount=gr.total_amount,
        created_at=gr.created_at,
        lines=[
            GRLineModel(line_number=l.line_number, quantity_received=l.quantity_received)
            for l in gr.lines
        ],
    )


def gr_to_domain(model: GRModel) -> GoodsReceipt:
    return GoodsReceipt(
        id=model.id,
        po_id=model.po_id,
        status=GRStatus(model.status),
        total_amount=model.total_amount,
        created_at=model.created_at,
        lines=[
            GRLine(line_number=l.line_number, quantity_received=l.quantity_received)
            for l in model.lines
        ],
    )


def payment_to_model(payment: Payment) -> PaymentModel:
    return PaymentModel(
        id=payment.id,
        gr_id=payment.gr_id,
        amount=payment.amount,
        status=payment.status.value,
        created_at=payment.created_at,
    )


def payment_to_domain(model: PaymentModel) -> Payment:
    return Payment(
        id=model.id,
        gr_id=model.gr_id,
        amount=model.amount,
        status=PaymentStatus(model.status),
        created_at=model.created_at,
    )


def journal_entry_to_model(entry: JournalEntry) -> JournalEntryModel:
    return JournalEntryModel(
        id=entry.id,
        source_event=entry.source_event,
        source_id=entry.source_id,
        posted_at=entry.posted_at,
        lines=[
            JournalLineModel(account_code=l.account_code, debit=l.debit, credit=l.credit)
            for l in entry.lines
        ],
    )


def journal_entry_to_domain(model: JournalEntryModel) -> JournalEntry:
    return JournalEntry(
        id=model.id,
        source_event=model.source_event,
        source_id=model.source_id,
        posted_at=model.posted_at,
        lines=[
            JournalLine(account_code=l.account_code, debit=l.debit, credit=l.credit)
            for l in model.lines
        ],
    )
```

- [ ] **Step 5: Implement `repositories.py`**

```python
# app/infrastructure/db/repositories.py
from app.infrastructure.db.mappers import (
    gr_to_domain,
    gr_to_model,
    journal_entry_to_domain,
    journal_entry_to_model,
    payment_to_domain,
    payment_to_model,
    po_to_domain,
    po_to_model,
    pr_to_domain,
    pr_to_model,
)
from app.infrastructure.db.models import (
    GRModel,
    JournalEntryModel,
    PaymentModel,
    POModel,
    PRModel,
)


class SqlAlchemyPRRepository:
    def __init__(self, session):
        self.session = session

    def add(self, pr):
        model = pr_to_model(pr)
        self.session.add(model)
        self.session.flush()
        pr.id = model.id
        return pr

    def get(self, pr_id):
        model = self.session.get(PRModel, pr_id)
        return pr_to_domain(model) if model else None

    def list(self):
        return [pr_to_domain(m) for m in self.session.query(PRModel).all()]

    def update(self, pr):
        model = self.session.get(PRModel, pr.id)
        model.status = pr.status.value
        self.session.flush()


class SqlAlchemyPORepository:
    def __init__(self, session):
        self.session = session

    def add(self, po):
        model = po_to_model(po)
        self.session.add(model)
        self.session.flush()
        po.id = model.id
        return po

    def get(self, po_id):
        model = self.session.get(POModel, po_id)
        return po_to_domain(model) if model else None

    def list(self):
        return [po_to_domain(m) for m in self.session.query(POModel).all()]

    def update(self, po):
        model = self.session.get(POModel, po.id)
        model.status = po.status.value
        lines_by_number = {l.line_number: l for l in model.lines}
        for line in po.lines:
            lines_by_number[line.line_number].quantity_received = line.quantity_received
        self.session.flush()


class SqlAlchemyGRRepository:
    def __init__(self, session):
        self.session = session

    def add(self, gr):
        model = gr_to_model(gr)
        self.session.add(model)
        self.session.flush()
        gr.id = model.id
        return gr

    def get(self, gr_id):
        model = self.session.get(GRModel, gr_id)
        return gr_to_domain(model) if model else None

    def list(self):
        return [gr_to_domain(m) for m in self.session.query(GRModel).all()]

    def update(self, gr):
        model = self.session.get(GRModel, gr.id)
        model.status = gr.status.value
        model.total_amount = gr.total_amount
        self.session.flush()


class SqlAlchemyPaymentRepository:
    def __init__(self, session):
        self.session = session

    def add(self, payment):
        model = payment_to_model(payment)
        self.session.add(model)
        self.session.flush()
        payment.id = model.id
        return payment

    def get(self, payment_id):
        model = self.session.get(PaymentModel, payment_id)
        return payment_to_domain(model) if model else None

    def list(self):
        return [payment_to_domain(m) for m in self.session.query(PaymentModel).all()]

    def update(self, payment):
        model = self.session.get(PaymentModel, payment.id)
        model.status = payment.status.value
        self.session.flush()

    def get_by_gr_id(self, gr_id):
        model = self.session.query(PaymentModel).filter_by(gr_id=gr_id).first()
        return payment_to_domain(model) if model else None


class SqlAlchemyJournalRepository:
    def __init__(self, session):
        self.session = session

    def add(self, entry):
        model = journal_entry_to_model(entry)
        self.session.add(model)
        self.session.flush()
        entry.id = model.id
        return entry

    def list(self):
        return [
            journal_entry_to_domain(m) for m in self.session.query(JournalEntryModel).all()
        ]
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/integration/test_persistence.py -v`
Expected: PASS (4 tests)

- [ ] **Step 7: Commit**

```bash
git add app/infrastructure/db/mappers.py app/infrastructure/db/repositories.py tests/conftest.py tests/integration/test_persistence.py
git commit -m "Add entity<->ORM mappers and SQLAlchemy repositories for all aggregates"
```

---

## Task 10: Unit of Work + application-layer repository protocols

**Files:**
- Create: `app/application/__init__.py` (empty)
- Create: `app/application/unit_of_work.py`
- Create: `app/infrastructure/db/unit_of_work.py`
- Test: `tests/integration/test_unit_of_work.py`

**Interfaces:**
- Consumes: repository classes (Task 9).
- Produces: `Protocol` classes `PRRepository`, `PORepository`, `GRRepository`, `PaymentRepository`, `JournalRepository`, `UnitOfWork` in `app/application/unit_of_work.py` (documentation/typing only — nothing imports these at runtime except as type hints); `SqlAlchemyUnitOfWork(session_factory)` in `app/infrastructure/db/unit_of_work.py` with `.pr_repo`, `.po_repo`, `.gr_repo`, `.payment_repo`, `.journal_repo` (set on `__enter__`), `.commit()`, `.rollback()`, usable as a context manager.

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_unit_of_work.py
import pytest

from app.domain.purchase_requisition.entities import PRLine, PurchaseRequisition
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork


def test_commit_persists_changes_visible_in_a_new_unit_of_work(session_factory):
    uow = SqlAlchemyUnitOfWork(session_factory)
    with uow:
        pr = PurchaseRequisition.create(
            requested_by="alice",
            lines=[PRLine(item_name="Laptop Stand", quantity=10, unit_price=25.50)],
        )
        uow.pr_repo.add(pr)
        uow.commit()
        pr_id = pr.id

    uow2 = SqlAlchemyUnitOfWork(session_factory)
    with uow2:
        fetched = uow2.pr_repo.get(pr_id)

    assert fetched is not None
    assert fetched.requested_by == "alice"


def test_exception_before_commit_rolls_back(session_factory):
    uow = SqlAlchemyUnitOfWork(session_factory)
    with pytest.raises(RuntimeError):
        with uow:
            pr = PurchaseRequisition.create(
                requested_by="alice",
                lines=[PRLine(item_name="Laptop Stand", quantity=10, unit_price=25.50)],
            )
            uow.pr_repo.add(pr)
            raise RuntimeError("boom before commit")

    uow2 = SqlAlchemyUnitOfWork(session_factory)
    with uow2:
        assert uow2.pr_repo.list() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_unit_of_work.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.infrastructure.db.unit_of_work'`

- [ ] **Step 3: Implement `app/infrastructure/db/unit_of_work.py`**

```python
# app/infrastructure/db/unit_of_work.py
from app.infrastructure.db.repositories import (
    SqlAlchemyGRRepository,
    SqlAlchemyJournalRepository,
    SqlAlchemyPaymentRepository,
    SqlAlchemyPORepository,
    SqlAlchemyPRRepository,
)


class SqlAlchemyUnitOfWork:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory
        self.session = None

    def __enter__(self) -> "SqlAlchemyUnitOfWork":
        self.session = self._session_factory()
        self.pr_repo = SqlAlchemyPRRepository(self.session)
        self.po_repo = SqlAlchemyPORepository(self.session)
        self.gr_repo = SqlAlchemyGRRepository(self.session)
        self.payment_repo = SqlAlchemyPaymentRepository(self.session)
        self.journal_repo = SqlAlchemyJournalRepository(self.session)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            self.session.rollback()
        self.session.close()

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()
```

- [ ] **Step 4: Implement `app/application/unit_of_work.py`** (typing-only Protocols; nothing else in the codebase imports these at runtime, but they document the port every concrete `UnitOfWork` must satisfy)

```python
# app/application/unit_of_work.py
from typing import Protocol

from app.domain.accounting.entities import JournalEntry
from app.domain.goods_receipt.entities import GoodsReceipt
from app.domain.payment.entities import Payment
from app.domain.purchase_order.entities import PurchaseOrder
from app.domain.purchase_requisition.entities import PurchaseRequisition


class PRRepository(Protocol):
    def add(self, pr: PurchaseRequisition) -> PurchaseRequisition: ...
    def get(self, pr_id: int) -> PurchaseRequisition | None: ...
    def list(self) -> list[PurchaseRequisition]: ...
    def update(self, pr: PurchaseRequisition) -> None: ...


class PORepository(Protocol):
    def add(self, po: PurchaseOrder) -> PurchaseOrder: ...
    def get(self, po_id: int) -> PurchaseOrder | None: ...
    def list(self) -> list[PurchaseOrder]: ...
    def update(self, po: PurchaseOrder) -> None: ...


class GRRepository(Protocol):
    def add(self, gr: GoodsReceipt) -> GoodsReceipt: ...
    def get(self, gr_id: int) -> GoodsReceipt | None: ...
    def list(self) -> list[GoodsReceipt]: ...
    def update(self, gr: GoodsReceipt) -> None: ...


class PaymentRepository(Protocol):
    def add(self, payment: Payment) -> Payment: ...
    def get(self, payment_id: int) -> Payment | None: ...
    def list(self) -> list[Payment]: ...
    def update(self, payment: Payment) -> None: ...
    def get_by_gr_id(self, gr_id: int) -> Payment | None: ...


class JournalRepository(Protocol):
    def add(self, entry: JournalEntry) -> JournalEntry: ...
    def list(self) -> list[JournalEntry]: ...


class UnitOfWork(Protocol):
    pr_repo: PRRepository
    po_repo: PORepository
    gr_repo: GRRepository
    payment_repo: PaymentRepository
    journal_repo: JournalRepository

    def __enter__(self) -> "UnitOfWork": ...
    def __exit__(self, *args) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
```

- [ ] **Step 5: Append a `uow` fixture to `tests/conftest.py`**

```python
# tests/conftest.py — append below the existing session_factory fixture
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork


@pytest.fixture()
def uow(session_factory):
    return SqlAlchemyUnitOfWork(session_factory)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/integration/test_unit_of_work.py tests/integration/test_persistence.py tests/integration/test_db_bootstrap.py -v`
Expected: PASS (8 tests total)

- [ ] **Step 7: Commit**

```bash
git add app/application/unit_of_work.py app/infrastructure/db/unit_of_work.py tests/integration/test_unit_of_work.py tests/conftest.py
git commit -m "Add SqlAlchemyUnitOfWork and application-layer repository protocols"
```

---

## Task 11: GL Engine

**Files:**
- Create: `app/application/gl_engine.py`
- Test: `tests/unit/test_gl_engine.py`

**Interfaces:**
- Consumes: `POSTING_RULES` (Task 7).
- Produces: `UnsupportedDomainEventError`; `GLEngine` with `.handle(event: DomainEvent, uow) -> None` (looks up the posting rule, builds the `JournalEntry`, calls `uow.journal_repo.add(entry)`).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_gl_engine.py
from dataclasses import dataclass

import pytest

from app.application.gl_engine import GLEngine, UnsupportedDomainEventError
from app.domain.goods_receipt.events import GoodsReceiptPosted
from app.domain.shared.domain_event import DomainEvent


class FakeJournalRepo:
    def __init__(self) -> None:
        self.entries = []

    def add(self, entry):
        self.entries.append(entry)
        return entry


class FakeUow:
    def __init__(self) -> None:
        self.journal_repo = FakeJournalRepo()


def test_handle_posts_journal_entry_for_known_event():
    uow = FakeUow()
    engine = GLEngine()

    engine.handle(GoodsReceiptPosted(gr_id=1, amount=255.0), uow)

    assert len(uow.journal_repo.entries) == 1
    assert uow.journal_repo.entries[0].source_event == "GoodsReceiptPosted"


def test_handle_raises_for_unknown_event():
    @dataclass(frozen=True)
    class SomeOtherEvent(DomainEvent):
        pass

    uow = FakeUow()
    engine = GLEngine()

    with pytest.raises(UnsupportedDomainEventError):
        engine.handle(SomeOtherEvent(), uow)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_gl_engine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.application.gl_engine'`

- [ ] **Step 3: Implement `gl_engine.py`**

```python
# app/application/gl_engine.py
from app.domain.accounting.posting_rules import POSTING_RULES
from app.domain.shared.domain_event import DomainEvent


class UnsupportedDomainEventError(Exception):
    pass


class GLEngine:
    def handle(self, event: DomainEvent, uow) -> None:
        builder = POSTING_RULES.get(type(event))
        if builder is None:
            raise UnsupportedDomainEventError(
                f"no posting rule for {type(event).__name__}"
            )
        journal_entry = builder(event)
        uow.journal_repo.add(journal_entry)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_gl_engine.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add app/application/gl_engine.py tests/unit/test_gl_engine.py
git commit -m "Add GLEngine that dispatches domain events to posting rules"
```

---

## Task 12: PRService

**Files:**
- Create: `app/application/services/__init__.py` (empty)
- Create: `app/application/services/pr_service.py`
- Test: `tests/integration/test_pr_service.py`

**Interfaces:**
- Consumes: `PurchaseRequisition`, `PRLine` (Task 3), `NotFoundError` (Task 1), `uow` fixture (Task 9).
- Produces: `PRService(uow)` with `.create(requested_by: str, lines: list[dict]) -> PurchaseRequisition`, `.get(pr_id: int) -> PurchaseRequisition` (raises `NotFoundError`), `.list() -> list[PurchaseRequisition]`, `.submit(pr_id) -> PurchaseRequisition`, `.approve(pr_id) -> PurchaseRequisition`, `.reject(pr_id) -> PurchaseRequisition`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/integration/test_pr_service.py
import pytest

from app.application.services.pr_service import PRService
from app.domain.purchase_requisition.entities import PRStatus
from app.domain.shared.errors import NotFoundError
from app.domain.shared.state_machine import InvalidStateTransitionError


def test_create_and_get(uow):
    service = PRService(uow)

    pr = service.create(
        requested_by="alice",
        lines=[{"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}],
    )

    assert pr.id is not None
    fetched = service.get(pr.id)
    assert fetched.requested_by == "alice"


def test_full_approval_flow(uow):
    service = PRService(uow)
    pr = service.create(
        requested_by="alice",
        lines=[{"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}],
    )

    service.submit(pr.id)
    approved = service.approve(pr.id)

    assert approved.status == PRStatus.APPROVED


def test_approve_before_submit_raises(uow):
    service = PRService(uow)
    pr = service.create(
        requested_by="alice",
        lines=[{"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}],
    )

    with pytest.raises(InvalidStateTransitionError):
        service.approve(pr.id)


def test_get_missing_raises_not_found(uow):
    service = PRService(uow)

    with pytest.raises(NotFoundError):
        service.get(999)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/integration/test_pr_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.application.services'`

- [ ] **Step 3: Implement `pr_service.py`**

```python
# app/application/services/pr_service.py
from app.domain.purchase_requisition.entities import PRLine, PurchaseRequisition
from app.domain.shared.errors import NotFoundError


class PRService:
    def __init__(self, uow) -> None:
        self.uow = uow

    def create(self, requested_by: str, lines: list[dict]) -> PurchaseRequisition:
        with self.uow:
            pr = PurchaseRequisition.create(
                requested_by=requested_by,
                lines=[PRLine(**line) for line in lines],
            )
            self.uow.pr_repo.add(pr)
            self.uow.commit()
            return pr

    def get(self, pr_id: int) -> PurchaseRequisition:
        with self.uow:
            pr = self.uow.pr_repo.get(pr_id)
            if pr is None:
                raise NotFoundError(f"purchase requisition {pr_id} not found")
            return pr

    def list(self) -> list[PurchaseRequisition]:
        with self.uow:
            return self.uow.pr_repo.list()

    def submit(self, pr_id: int) -> PurchaseRequisition:
        return self._transition(pr_id, "submit")

    def approve(self, pr_id: int) -> PurchaseRequisition:
        return self._transition(pr_id, "approve")

    def reject(self, pr_id: int) -> PurchaseRequisition:
        return self._transition(pr_id, "reject")

    def _transition(self, pr_id: int, action: str) -> PurchaseRequisition:
        with self.uow:
            pr = self.uow.pr_repo.get(pr_id)
            if pr is None:
                raise NotFoundError(f"purchase requisition {pr_id} not found")
            getattr(pr, action)()
            self.uow.pr_repo.update(pr)
            self.uow.commit()
            return pr
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/integration/test_pr_service.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add app/application/services/ tests/integration/test_pr_service.py
git commit -m "Add PRService use cases"
```

---

## Task 13: POService

**Files:**
- Create: `app/application/services/po_service.py`
- Test: `tests/integration/test_po_service.py`

**Interfaces:**
- Consumes: `PurchaseOrder`, `POLine` (Task 4), `NotFoundError`, `DomainValidationError` (Task 1), `PRService` (Task 12, test-only helper).
- Produces: `POService(uow)` with `.create(pr_id: int, vendor_name: str, lines: list[dict]) -> PurchaseOrder` (assigns `line_number` sequentially starting at 1, raises `NotFoundError` if the PR doesn't exist, raises `DomainValidationError` if the PR isn't approved), `.get(po_id) -> PurchaseOrder`, `.list() -> list[PurchaseOrder]`, `.submit(po_id)`, `.approve(po_id)`, `.cancel(po_id)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/integration/test_po_service.py
import pytest

from app.application.services.po_service import POService
from app.application.services.pr_service import PRService
from app.domain.shared.errors import DomainValidationError


def approved_pr_id(uow) -> int:
    pr_service = PRService(uow)
    pr = pr_service.create(
        requested_by="alice",
        lines=[{"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}],
    )
    pr_service.submit(pr.id)
    pr_service.approve(pr.id)
    return pr.id


def test_create_po_from_approved_pr(uow):
    pr_id = approved_pr_id(uow)
    service = POService(uow)

    po = service.create(
        pr_id=pr_id,
        vendor_name="Acme Supplies Co.",
        lines=[{"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}],
    )

    assert po.pr_id == pr_id
    assert po.lines[0].line_number == 1


def test_create_po_from_non_approved_pr_raises(uow):
    pr_service = PRService(uow)
    pr = pr_service.create(
        requested_by="alice",
        lines=[{"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}],
    )
    service = POService(uow)

    with pytest.raises(DomainValidationError):
        service.create(
            pr_id=pr.id,
            vendor_name="Acme Supplies Co.",
            lines=[{"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}],
        )


def test_approve_and_cancel_flow(uow):
    pr_id = approved_pr_id(uow)
    service = POService(uow)
    po = service.create(
        pr_id=pr_id,
        vendor_name="Acme Supplies Co.",
        lines=[{"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}],
    )

    service.submit(po.id)
    approved = service.approve(po.id)
    assert approved.status.value == "approved"

    cancelled = service.cancel(po.id)
    assert cancelled.status.value == "cancelled"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/integration/test_po_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.application.services.po_service'`

- [ ] **Step 3: Implement `po_service.py`**

```python
# app/application/services/po_service.py
from app.domain.purchase_order.entities import POLine, PurchaseOrder
from app.domain.shared.errors import NotFoundError


class POService:
    def __init__(self, uow) -> None:
        self.uow = uow

    def create(self, pr_id: int, vendor_name: str, lines: list[dict]) -> PurchaseOrder:
        with self.uow:
            pr = self.uow.pr_repo.get(pr_id)
            if pr is None:
                raise NotFoundError(f"purchase requisition {pr_id} not found")
            po = PurchaseOrder.create_from_pr(
                pr_id=pr_id,
                pr_status=pr.status,
                vendor_name=vendor_name,
                lines=[POLine(line_number=i + 1, **line) for i, line in enumerate(lines)],
            )
            self.uow.po_repo.add(po)
            self.uow.commit()
            return po

    def get(self, po_id: int) -> PurchaseOrder:
        with self.uow:
            po = self.uow.po_repo.get(po_id)
            if po is None:
                raise NotFoundError(f"purchase order {po_id} not found")
            return po

    def list(self) -> list[PurchaseOrder]:
        with self.uow:
            return self.uow.po_repo.list()

    def submit(self, po_id: int) -> PurchaseOrder:
        return self._transition(po_id, "submit")

    def approve(self, po_id: int) -> PurchaseOrder:
        return self._transition(po_id, "approve")

    def cancel(self, po_id: int) -> PurchaseOrder:
        return self._transition(po_id, "cancel")

    def _transition(self, po_id: int, action: str) -> PurchaseOrder:
        with self.uow:
            po = self.uow.po_repo.get(po_id)
            if po is None:
                raise NotFoundError(f"purchase order {po_id} not found")
            getattr(po, action)()
            self.uow.po_repo.update(po)
            self.uow.commit()
            return po
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/integration/test_po_service.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add app/application/services/po_service.py tests/integration/test_po_service.py
git commit -m "Add POService use cases requiring an approved PR"
```

---

## Task 14: GRService (GL trigger #1)

**Files:**
- Create: `app/application/services/gr_service.py`
- Test: `tests/integration/test_gr_service.py`

**Interfaces:**
- Consumes: `GoodsReceipt`, `GRLine` (Task 5), `GLEngine` (Task 11), `NotFoundError`, `DomainValidationError` (Task 1), `POService`, `PRService` (Tasks 12–13, test-only helpers). Test verifies GL posting via `uow.journal_repo.list()` directly (entered with `with uow:`), not through `LedgerService` (built next task) — keeps this task's tests self-contained.
- Produces: `GRService(uow, gl_engine: GLEngine | None = None)` with `.create(po_id, lines: list[dict]) -> GoodsReceipt`, `.get(gr_id) -> GoodsReceipt`, `.list() -> list[GoodsReceipt]`, `.post(gr_id) -> GoodsReceipt` (computes the receipt amount from the PO's line unit prices, calls `po.receive_goods(...)`, `gr.post(amount)`, dispatches `gr.pull_events()` through the GL engine, commits once).

- [ ] **Step 1: Write the failing tests**

```python
# tests/integration/test_gr_service.py
import pytest

from app.application.services.gr_service import GRService
from app.application.services.po_service import POService
from app.application.services.pr_service import PRService
from app.domain.shared.errors import DomainValidationError


def approved_po(uow):
    pr_service = PRService(uow)
    pr = pr_service.create(
        requested_by="alice",
        lines=[{"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}],
    )
    pr_service.submit(pr.id)
    pr_service.approve(pr.id)

    po_service = POService(uow)
    po = po_service.create(
        pr_id=pr.id,
        vendor_name="Acme Supplies Co.",
        lines=[{"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}],
    )
    po_service.submit(po.id)
    return po_service.approve(po.id)


def test_posting_a_full_receipt_updates_po_and_creates_journal_entry(uow):
    po = approved_po(uow)
    gr_service = GRService(uow)
    gr = gr_service.create(po_id=po.id, lines=[{"line_number": 1, "quantity_received": 10}])

    posted = gr_service.post(gr.id)

    assert posted.status.value == "posted"
    assert posted.total_amount == 255.0

    updated_po = POService(uow).get(po.id)
    assert updated_po.status.value == "received"

    with uow:
        entries = uow.journal_repo.list()
    assert len(entries) == 1
    assert entries[0].source_event == "GoodsReceiptPosted"
    debit_line = next(l for l in entries[0].lines if l.debit)
    assert (debit_line.account_code, debit_line.debit) == ("1000", 255.0)


def test_partial_receipt_keeps_po_partially_received(uow):
    po = approved_po(uow)
    gr_service = GRService(uow)
    gr = gr_service.create(po_id=po.id, lines=[{"line_number": 1, "quantity_received": 4}])

    gr_service.post(gr.id)

    updated_po = POService(uow).get(po.id)
    assert updated_po.status.value == "partially_received"
    assert updated_po.lines[0].quantity_received == 4


def test_over_receiving_raises(uow):
    po = approved_po(uow)
    gr_service = GRService(uow)
    gr = gr_service.create(po_id=po.id, lines=[{"line_number": 1, "quantity_received": 11}])

    with pytest.raises(DomainValidationError):
        gr_service.post(gr.id)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/integration/test_gr_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.application.services.gr_service'`

- [ ] **Step 3: Implement `gr_service.py`**

```python
# app/application/services/gr_service.py
from app.application.gl_engine import GLEngine
from app.domain.goods_receipt.entities import GoodsReceipt, GRLine
from app.domain.shared.errors import DomainValidationError, NotFoundError


class GRService:
    def __init__(self, uow, gl_engine: GLEngine | None = None) -> None:
        self.uow = uow
        self.gl_engine = gl_engine or GLEngine()

    def create(self, po_id: int, lines: list[dict]) -> GoodsReceipt:
        with self.uow:
            po = self.uow.po_repo.get(po_id)
            if po is None:
                raise NotFoundError(f"purchase order {po_id} not found")
            gr = GoodsReceipt.create(po_id=po_id, lines=[GRLine(**line) for line in lines])
            self.uow.gr_repo.add(gr)
            self.uow.commit()
            return gr

    def get(self, gr_id: int) -> GoodsReceipt:
        with self.uow:
            gr = self.uow.gr_repo.get(gr_id)
            if gr is None:
                raise NotFoundError(f"goods receipt {gr_id} not found")
            return gr

    def list(self) -> list[GoodsReceipt]:
        with self.uow:
            return self.uow.gr_repo.list()

    def post(self, gr_id: int) -> GoodsReceipt:
        with self.uow:
            gr = self.uow.gr_repo.get(gr_id)
            if gr is None:
                raise NotFoundError(f"goods receipt {gr_id} not found")
            po = self.uow.po_repo.get(gr.po_id)
            if po is None:
                raise NotFoundError(f"purchase order {gr.po_id} not found")

            po_lines_by_number = {line.line_number: line for line in po.lines}
            amount = 0.0
            for gr_line in gr.lines:
                po_line = po_lines_by_number.get(gr_line.line_number)
                if po_line is None:
                    raise DomainValidationError(
                        f"PO has no line number {gr_line.line_number}"
                    )
                amount += gr_line.quantity_received * po_line.unit_price

            po.receive_goods(
                {line.line_number: line.quantity_received for line in gr.lines}
            )
            gr.post(amount)

            self.uow.po_repo.update(po)
            self.uow.gr_repo.update(gr)
            for event in gr.pull_events():
                self.gl_engine.handle(event, self.uow)
            self.uow.commit()
            return gr
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/integration/test_gr_service.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add app/application/services/gr_service.py tests/integration/test_gr_service.py
git commit -m "Add GRService: the first GL trigger (goods receipt posts Dr Inventory/Cr GR-IR)"
```

---

## Task 15: PaymentService (GL trigger #2) + LedgerService

**Files:**
- Create: `app/application/services/payment_service.py`
- Create: `app/application/services/ledger_service.py`
- Test: `tests/integration/test_payment_service.py`

**Interfaces:**
- Consumes: `Payment` (Task 6), `GLEngine` (Task 11), `NotFoundError`, `DomainValidationError` (Task 1), `SEED_ACCOUNTS` (Task 2), `GRService`, `POService`, `PRService` (test-only helpers).
- Produces: `PaymentService(uow, gl_engine=None)` with `.create(gr_id, amount) -> Payment` (raises `DomainValidationError` if the GR already has a payment, or if the GR isn't posted, or if `amount` doesn't match the GR total), `.get(payment_id) -> Payment`, `.list()`, `.approve(payment_id)`, `.pay(payment_id)` (dispatches `PaymentPaid` through the GL engine). `LedgerService(uow)` with `.list_journal_entries() -> list[JournalEntry]`, `.trial_balance() -> dict[str, dict]` (`{account_code: {"name": str, "debit": float, "credit": float}}`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/integration/test_payment_service.py
import pytest

from app.application.services.gr_service import GRService
from app.application.services.ledger_service import LedgerService
from app.application.services.payment_service import PaymentService
from app.application.services.po_service import POService
from app.application.services.pr_service import PRService
from app.domain.shared.errors import DomainValidationError


def posted_gr(uow):
    pr_service = PRService(uow)
    pr = pr_service.create(
        requested_by="alice",
        lines=[{"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}],
    )
    pr_service.submit(pr.id)
    pr_service.approve(pr.id)

    po_service = POService(uow)
    po = po_service.create(
        pr_id=pr.id,
        vendor_name="Acme Supplies Co.",
        lines=[{"item_name": "Laptop Stand", "quantity": 10, "unit_price": 25.50}],
    )
    po_service.submit(po.id)
    po_service.approve(po.id)

    gr_service = GRService(uow)
    gr = gr_service.create(po_id=po.id, lines=[{"line_number": 1, "quantity_received": 10}])
    return gr_service.post(gr.id)


def test_paying_creates_a_second_balanced_journal_entry(uow):
    gr = posted_gr(uow)
    payment_service = PaymentService(uow)
    payment = payment_service.create(gr_id=gr.id, amount=gr.total_amount)
    payment_service.approve(payment.id)

    paid = payment_service.pay(payment.id)

    assert paid.status.value == "paid"
    entries = LedgerService(uow).list_journal_entries()
    assert len(entries) == 2
    assert entries[1].source_event == "PaymentPaid"


def test_second_payment_for_same_gr_rejected(uow):
    gr = posted_gr(uow)
    payment_service = PaymentService(uow)
    payment_service.create(gr_id=gr.id, amount=gr.total_amount)

    with pytest.raises(DomainValidationError):
        payment_service.create(gr_id=gr.id, amount=gr.total_amount)


def test_payment_amount_must_match_gr_total(uow):
    gr = posted_gr(uow)
    payment_service = PaymentService(uow)

    with pytest.raises(DomainValidationError):
        payment_service.create(gr_id=gr.id, amount=gr.total_amount - 1)


def test_trial_balance_is_balanced_after_full_flow(uow):
    gr = posted_gr(uow)
    payment_service = PaymentService(uow)
    payment = payment_service.create(gr_id=gr.id, amount=gr.total_amount)
    payment_service.approve(payment.id)
    payment_service.pay(payment.id)

    balances = LedgerService(uow).trial_balance()

    total_debit = sum(row["debit"] for row in balances.values())
    total_credit = sum(row["credit"] for row in balances.values())
    assert total_debit == total_credit
    assert balances["2100"]["debit"] == balances["2100"]["credit"] == gr.total_amount
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_payment_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.application.services.payment_service'`

- [ ] **Step 3: Implement `payment_service.py`**

```python
# app/application/services/payment_service.py
from app.application.gl_engine import GLEngine
from app.domain.payment.entities import Payment
from app.domain.shared.errors import DomainValidationError, NotFoundError


class PaymentService:
    def __init__(self, uow, gl_engine: GLEngine | None = None) -> None:
        self.uow = uow
        self.gl_engine = gl_engine or GLEngine()

    def create(self, gr_id: int, amount: float) -> Payment:
        with self.uow:
            gr = self.uow.gr_repo.get(gr_id)
            if gr is None:
                raise NotFoundError(f"goods receipt {gr_id} not found")
            existing = self.uow.payment_repo.get_by_gr_id(gr_id)
            if existing is not None:
                raise DomainValidationError(
                    f"goods receipt {gr_id} already has a payment"
                )
            payment = Payment.create_for_gr(
                gr_id=gr_id,
                gr_status=gr.status,
                gr_total_amount=gr.total_amount,
                amount=amount,
            )
            self.uow.payment_repo.add(payment)
            self.uow.commit()
            return payment

    def get(self, payment_id: int) -> Payment:
        with self.uow:
            payment = self.uow.payment_repo.get(payment_id)
            if payment is None:
                raise NotFoundError(f"payment {payment_id} not found")
            return payment

    def list(self) -> list[Payment]:
        with self.uow:
            return self.uow.payment_repo.list()

    def approve(self, payment_id: int) -> Payment:
        return self._transition(payment_id, "approve")

    def pay(self, payment_id: int) -> Payment:
        with self.uow:
            payment = self.uow.payment_repo.get(payment_id)
            if payment is None:
                raise NotFoundError(f"payment {payment_id} not found")
            payment.pay()
            self.uow.payment_repo.update(payment)
            for event in payment.pull_events():
                self.gl_engine.handle(event, self.uow)
            self.uow.commit()
            return payment

    def _transition(self, payment_id: int, action: str) -> Payment:
        with self.uow:
            payment = self.uow.payment_repo.get(payment_id)
            if payment is None:
                raise NotFoundError(f"payment {payment_id} not found")
            getattr(payment, action)()
            self.uow.payment_repo.update(payment)
            self.uow.commit()
            return payment
```

- [ ] **Step 4: Implement `ledger_service.py`**

```python
# app/application/services/ledger_service.py
from app.domain.accounting.chart_of_accounts import SEED_ACCOUNTS
from app.domain.accounting.entities import JournalEntry


class LedgerService:
    def __init__(self, uow) -> None:
        self.uow = uow

    def list_journal_entries(self) -> list[JournalEntry]:
        with self.uow:
            return self.uow.journal_repo.list()

    def trial_balance(self) -> dict[str, dict]:
        with self.uow:
            entries = self.uow.journal_repo.list()

        balances = {
            account.code: {"name": account.name, "debit": 0.0, "credit": 0.0}
            for account in SEED_ACCOUNTS
        }
        for entry in entries:
            for line in entry.lines:
                balances[line.account_code]["debit"] += line.debit
                balances[line.account_code]["credit"] += line.credit
        return balances
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/integration/ -v`
Expected: PASS (all integration tests from Tasks 8–15)

- [ ] **Step 6: Commit**

```bash
git add app/application/services/payment_service.py app/application/services/ledger_service.py tests/integration/test_payment_service.py
git commit -m "Add PaymentService (second GL trigger) and LedgerService"
```

---

## Task 16: Pydantic schemas, dependency wiring, error handling

**Files:**
- Create: `app/interface/__init__.py` (empty)
- Create: `app/interface/api/__init__.py` (empty)
- Create: `app/interface/api/schemas.py`
- Create: `app/interface/api/deps.py`
- Create: `app/interface/api/error_handling.py`

**Interfaces:**
- Consumes: all domain entities, `NotFoundError`, `DomainValidationError` (Task 1), `InvalidStateTransitionError` (Task 1), all services (Tasks 12, 13, 14, 15), `SqlAlchemyUnitOfWork` (Task 10), `SessionLocal` (Task 8).
- Produces: Pydantic DTOs `LineItemIn`, `PRCreate`, `PRLineOut`, `PROut`, `POCreate`, `POLineOut`, `POOut`, `GRLineIn`, `GRCreate`, `GRLineOut`, `GROut`, `PaymentCreate`, `PaymentOut`, `JournalLineOut`, `JournalEntryOut`, `TrialBalanceRowOut`; `get_uow()`, `get_pr_service(uow=Depends(get_uow))`, `get_po_service(...)`, `get_gr_service(...)`, `get_payment_service(...)`, `get_ledger_service(...)`; `run(action: Callable)` that maps `NotFoundError`→404, `InvalidStateTransitionError`→409, `DomainValidationError`→400 into `fastapi.HTTPException`.

This task is plumbing consumed entirely by Task 17's router tests — no dedicated test file, verified by import.

- [ ] **Step 1: Implement `schemas.py`**

```python
# app/interface/api/schemas.py
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LineItemIn(BaseModel):
    item_name: str = Field(..., min_length=1)
    quantity: int = Field(..., gt=0)
    unit_price: float = Field(..., gt=0)


class PRCreate(BaseModel):
    requested_by: str = Field(..., min_length=1)
    lines: list[LineItemIn] = Field(..., min_length=1)


class PRLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    item_name: str
    quantity: int
    unit_price: float


class PROut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    requested_by: str
    status: str
    total_amount: float
    lines: list[PRLineOut]
    created_at: datetime


class POCreate(BaseModel):
    pr_id: int
    vendor_name: str = Field(..., min_length=1)
    lines: list[LineItemIn] = Field(..., min_length=1)


class POLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    line_number: int
    item_name: str
    quantity: int
    unit_price: float
    quantity_received: int


class POOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pr_id: int
    vendor_name: str
    status: str
    total_amount: float
    lines: list[POLineOut]
    created_at: datetime


class GRLineIn(BaseModel):
    line_number: int
    quantity_received: int = Field(..., gt=0)


class GRCreate(BaseModel):
    po_id: int
    lines: list[GRLineIn] = Field(..., min_length=1)


class GRLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    line_number: int
    quantity_received: int


class GROut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    po_id: int
    status: str
    total_amount: float | None
    lines: list[GRLineOut]
    created_at: datetime


class PaymentCreate(BaseModel):
    gr_id: int
    amount: float = Field(..., gt=0)


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    gr_id: int
    amount: float
    status: str
    created_at: datetime


class JournalLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    account_code: str
    debit: float
    credit: float


class JournalEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_event: str
    source_id: int
    posted_at: datetime
    lines: list[JournalLineOut]


class TrialBalanceRowOut(BaseModel):
    account_code: str
    account_name: str
    debit: float
    credit: float
```

- [ ] **Step 2: Implement `deps.py`**

```python
# app/interface/api/deps.py
from fastapi import Depends

from app.application.services.gr_service import GRService
from app.application.services.ledger_service import LedgerService
from app.application.services.payment_service import PaymentService
from app.application.services.po_service import POService
from app.application.services.pr_service import PRService
from app.infrastructure.db.session import SessionLocal
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork


def get_uow() -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(SessionLocal)


def get_pr_service(uow: SqlAlchemyUnitOfWork = Depends(get_uow)) -> PRService:
    return PRService(uow)


def get_po_service(uow: SqlAlchemyUnitOfWork = Depends(get_uow)) -> POService:
    return POService(uow)


def get_gr_service(uow: SqlAlchemyUnitOfWork = Depends(get_uow)) -> GRService:
    return GRService(uow)


def get_payment_service(
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> PaymentService:
    return PaymentService(uow)


def get_ledger_service(
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> LedgerService:
    return LedgerService(uow)
```

- [ ] **Step 3: Implement `error_handling.py`**

```python
# app/interface/api/error_handling.py
from typing import Callable, TypeVar

from fastapi import HTTPException

from app.domain.shared.errors import DomainValidationError, NotFoundError
from app.domain.shared.state_machine import InvalidStateTransitionError

T = TypeVar("T")


def run(action: Callable[[], T]) -> T:
    try:
        return action()
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidStateTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DomainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
```

- [ ] **Step 4: Verify the modules import cleanly**

Run: `python -c "import app.interface.api.schemas, app.interface.api.deps, app.interface.api.error_handling"`
Expected: no output, exit code 0

- [ ] **Step 5: Commit**

```bash
git add app/interface/
git commit -m "Add API schemas, dependency wiring, and centralized error mapping"
```

---

## Task 17: Routers, main.py, and API tests

**Files:**
- Create: `app/interface/api/routers/__init__.py` (empty)
- Create: `app/interface/api/routers/purchase_requisitions.py`
- Create: `app/interface/api/routers/purchase_orders.py`
- Create: `app/interface/api/routers/goods_receipts.py`
- Create: `app/interface/api/routers/payments.py`
- Create: `app/interface/api/routers/ledger.py`
- Modify: `app/main.py` (full rewrite)
- Modify: `tests/conftest.py` (add `client` fixture)
- Test: `tests/api/test_purchase_requisitions_api.py`
- Test: `tests/api/test_purchase_orders_api.py`
- Test: `tests/api/test_goods_receipts_api.py`
- Test: `tests/api/test_payments_and_ledger_api.py`

**Interfaces:**
- Consumes: schemas, deps, `run()` (Task 16), all services (Tasks 12–15).
- Produces: the full HTTP API described in the design doc; `client` pytest fixture (a `TestClient` with `get_uow` overridden to a fresh in-memory DB per test).

- [ ] **Step 1: Write the failing API tests**

```python
# tests/api/test_purchase_requisitions_api.py
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
```

```python
# tests/api/test_purchase_orders_api.py
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
```

```python
# tests/api/test_goods_receipts_api.py
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
```

```python
# tests/api/test_payments_and_ledger_api.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/api/ -v`
Expected: FAIL with `fixture 'client' not found`

- [ ] **Step 3: Add the `client` fixture to `tests/conftest.py`**

```python
# tests/conftest.py — append below the existing fixtures
from fastapi.testclient import TestClient

from app.interface.api.deps import get_uow
from app.main import app


@pytest.fixture()
def client(session_factory):
    from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

    def override_get_uow():
        return SqlAlchemyUnitOfWork(session_factory)

    app.dependency_overrides[get_uow] = override_get_uow
    yield TestClient(app)
    app.dependency_overrides.clear()
```

- [ ] **Step 4: Implement `purchase_requisitions.py`**

```python
# app/interface/api/routers/purchase_requisitions.py
from fastapi import APIRouter, Depends

from app.application.services.pr_service import PRService
from app.interface.api.deps import get_pr_service
from app.interface.api.error_handling import run
from app.interface.api.schemas import PRCreate, PROut

router = APIRouter(prefix="/purchase-requisitions", tags=["Purchase Requisitions"])


@router.post("", response_model=PROut, status_code=201)
def create_pr(payload: PRCreate, service: PRService = Depends(get_pr_service)) -> PROut:
    pr = service.create(
        requested_by=payload.requested_by,
        lines=[line.model_dump() for line in payload.lines],
    )
    return PROut.model_validate(pr)


@router.get("", response_model=list[PROut])
def list_prs(service: PRService = Depends(get_pr_service)) -> list[PROut]:
    return [PROut.model_validate(pr) for pr in service.list()]


@router.get("/{pr_id}", response_model=PROut)
def get_pr(pr_id: int, service: PRService = Depends(get_pr_service)) -> PROut:
    return PROut.model_validate(run(lambda: service.get(pr_id)))


@router.post("/{pr_id}/submit", response_model=PROut)
def submit_pr(pr_id: int, service: PRService = Depends(get_pr_service)) -> PROut:
    return PROut.model_validate(run(lambda: service.submit(pr_id)))


@router.post("/{pr_id}/approve", response_model=PROut)
def approve_pr(pr_id: int, service: PRService = Depends(get_pr_service)) -> PROut:
    return PROut.model_validate(run(lambda: service.approve(pr_id)))


@router.post("/{pr_id}/reject", response_model=PROut)
def reject_pr(pr_id: int, service: PRService = Depends(get_pr_service)) -> PROut:
    return PROut.model_validate(run(lambda: service.reject(pr_id)))
```

- [ ] **Step 5: Implement `purchase_orders.py`**

```python
# app/interface/api/routers/purchase_orders.py
from fastapi import APIRouter, Depends

from app.application.services.po_service import POService
from app.interface.api.deps import get_po_service
from app.interface.api.error_handling import run
from app.interface.api.schemas import POCreate, POOut

router = APIRouter(prefix="/purchase-orders", tags=["Purchase Orders"])


@router.post("", response_model=POOut, status_code=201)
def create_po(payload: POCreate, service: POService = Depends(get_po_service)) -> POOut:
    po = run(
        lambda: service.create(
            pr_id=payload.pr_id,
            vendor_name=payload.vendor_name,
            lines=[line.model_dump() for line in payload.lines],
        )
    )
    return POOut.model_validate(po)


@router.get("", response_model=list[POOut])
def list_pos(service: POService = Depends(get_po_service)) -> list[POOut]:
    return [POOut.model_validate(po) for po in service.list()]


@router.get("/{po_id}", response_model=POOut)
def get_po(po_id: int, service: POService = Depends(get_po_service)) -> POOut:
    return POOut.model_validate(run(lambda: service.get(po_id)))


@router.post("/{po_id}/submit", response_model=POOut)
def submit_po(po_id: int, service: POService = Depends(get_po_service)) -> POOut:
    return POOut.model_validate(run(lambda: service.submit(po_id)))


@router.post("/{po_id}/approve", response_model=POOut)
def approve_po(po_id: int, service: POService = Depends(get_po_service)) -> POOut:
    return POOut.model_validate(run(lambda: service.approve(po_id)))


@router.post("/{po_id}/cancel", response_model=POOut)
def cancel_po(po_id: int, service: POService = Depends(get_po_service)) -> POOut:
    return POOut.model_validate(run(lambda: service.cancel(po_id)))
```

- [ ] **Step 6: Implement `goods_receipts.py`**

```python
# app/interface/api/routers/goods_receipts.py
from fastapi import APIRouter, Depends

from app.application.services.gr_service import GRService
from app.interface.api.deps import get_gr_service
from app.interface.api.error_handling import run
from app.interface.api.schemas import GRCreate, GROut

router = APIRouter(prefix="/goods-receipts", tags=["Goods Receipts"])


@router.post("", response_model=GROut, status_code=201)
def create_gr(payload: GRCreate, service: GRService = Depends(get_gr_service)) -> GROut:
    gr = run(
        lambda: service.create(
            po_id=payload.po_id, lines=[line.model_dump() for line in payload.lines]
        )
    )
    return GROut.model_validate(gr)


@router.get("", response_model=list[GROut])
def list_grs(service: GRService = Depends(get_gr_service)) -> list[GROut]:
    return [GROut.model_validate(gr) for gr in service.list()]


@router.get("/{gr_id}", response_model=GROut)
def get_gr(gr_id: int, service: GRService = Depends(get_gr_service)) -> GROut:
    return GROut.model_validate(run(lambda: service.get(gr_id)))


@router.post("/{gr_id}/post", response_model=GROut)
def post_gr(gr_id: int, service: GRService = Depends(get_gr_service)) -> GROut:
    return GROut.model_validate(run(lambda: service.post(gr_id)))
```

- [ ] **Step 7: Implement `payments.py`**

```python
# app/interface/api/routers/payments.py
from fastapi import APIRouter, Depends

from app.application.services.payment_service import PaymentService
from app.interface.api.deps import get_payment_service
from app.interface.api.error_handling import run
from app.interface.api.schemas import PaymentCreate, PaymentOut

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post("", response_model=PaymentOut, status_code=201)
def create_payment(
    payload: PaymentCreate, service: PaymentService = Depends(get_payment_service)
) -> PaymentOut:
    payment = run(lambda: service.create(gr_id=payload.gr_id, amount=payload.amount))
    return PaymentOut.model_validate(payment)


@router.get("", response_model=list[PaymentOut])
def list_payments(
    service: PaymentService = Depends(get_payment_service),
) -> list[PaymentOut]:
    return [PaymentOut.model_validate(p) for p in service.list()]


@router.get("/{payment_id}", response_model=PaymentOut)
def get_payment(
    payment_id: int, service: PaymentService = Depends(get_payment_service)
) -> PaymentOut:
    return PaymentOut.model_validate(run(lambda: service.get(payment_id)))


@router.post("/{payment_id}/approve", response_model=PaymentOut)
def approve_payment(
    payment_id: int, service: PaymentService = Depends(get_payment_service)
) -> PaymentOut:
    return PaymentOut.model_validate(run(lambda: service.approve(payment_id)))


@router.post("/{payment_id}/pay", response_model=PaymentOut)
def pay_payment(
    payment_id: int, service: PaymentService = Depends(get_payment_service)
) -> PaymentOut:
    return PaymentOut.model_validate(run(lambda: service.pay(payment_id)))
```

- [ ] **Step 8: Implement `ledger.py`**

```python
# app/interface/api/routers/ledger.py
from fastapi import APIRouter, Depends

from app.application.services.ledger_service import LedgerService
from app.interface.api.deps import get_ledger_service
from app.interface.api.schemas import JournalEntryOut, TrialBalanceRowOut

router = APIRouter(prefix="/ledger", tags=["Ledger"])


@router.get("/journal-entries", response_model=list[JournalEntryOut])
def list_journal_entries(
    service: LedgerService = Depends(get_ledger_service),
) -> list[JournalEntryOut]:
    return [JournalEntryOut.model_validate(e) for e in service.list_journal_entries()]


@router.get("/trial-balance", response_model=list[TrialBalanceRowOut])
def trial_balance(
    service: LedgerService = Depends(get_ledger_service),
) -> list[TrialBalanceRowOut]:
    balances = service.trial_balance()
    return [
        TrialBalanceRowOut(
            account_code=code,
            account_name=data["name"],
            debit=data["debit"],
            credit=data["credit"],
        )
        for code, data in balances.items()
    ]
```

- [ ] **Step 9: Rewrite `main.py`**

```python
# app/main.py
"""
Entry point for the Mini ERP API.

Run it with:
    uvicorn app.main:app --reload

Then open http://127.0.0.1:8000/docs for the interactive API docs.
"""

from fastapi import FastAPI

from app.infrastructure.db.session import init_db
from app.interface.api.routers import (
    goods_receipts,
    ledger,
    payments,
    purchase_orders,
    purchase_requisitions,
)

app = FastAPI(
    title="Mini ERP API",
    description="A Procure-to-Pay backend with an automated double-entry GL engine.",
    version="0.2.0",
)

app.include_router(purchase_requisitions.router)
app.include_router(purchase_orders.router)
app.include_router(goods_receipts.router)
app.include_router(payments.router)
app.include_router(ledger.router)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/")
def root():
    """Simple health-check / welcome route."""
    return {"message": "Mini ERP API is running. Visit /docs to try it out."}
```

- [ ] **Step 10: Run all API tests to verify they pass**

Run: `pytest tests/api/ -v`
Expected: PASS (9 tests)

- [ ] **Step 11: Commit**

```bash
git add app/interface/api/routers/ app/main.py tests/conftest.py tests/api/
git commit -m "Wire routers for PR/PO/GR/Payment/Ledger into the FastAPI app"
```

---

## Task 18: Remove the superseded in-memory implementation

**Files:**
- Delete: `app/database.py`
- Delete: `app/models.py`
- Delete: `app/routers/purchase_orders.py`
- Delete: `app/routers/__init__.py`
- Delete: `tests/test_purchase_orders.py`

**Interfaces:** none — this task only removes code now fully replaced by Tasks 1–17.

- [ ] **Step 1: Confirm nothing still imports the old modules**

Run: `grep -rn "app.database\|app.models\|app.routers" app tests --include="*.py"`
Expected: no output (the old flat `app/models.py` and `app/routers/` package are unused now that `app/domain/**` and `app/interface/api/routers/**` exist)

- [ ] **Step 2: Delete the superseded files**

```bash
git rm app/database.py app/models.py tests/test_purchase_orders.py
git rm -r app/routers
```

- [ ] **Step 3: Run the full test suite to confirm nothing broke**

Run: `pytest -v`
Expected: PASS (every test from Tasks 1–17, none referencing the deleted files)

- [ ] **Step 4: Commit**

```bash
git commit -m "Remove superseded in-memory PO implementation and its router/tests"
```

---

## Task 19: End-to-end golden-path test + README update

**Files:**
- Create: `tests/test_full_p2p_flow.py`
- Modify: `README.md`

**Interfaces:** none new — this exercises the whole system built in Tasks 1–17 through the public API.

- [ ] **Step 1: Write the end-to-end test**

```python
# tests/test_full_p2p_flow.py
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
```

- [ ] **Step 2: Run test to verify it fails or passes**

Run: `pytest tests/test_full_p2p_flow.py -v`
Expected: PASS immediately (Tasks 1–18 already implement everything this test exercises) — if it fails, the failure points at an integration gap between layers that the narrower per-task tests didn't catch; fix it before proceeding.

- [ ] **Step 3: Rewrite `README.md`**

```markdown
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
```

- [ ] **Step 4: Run the entire suite one final time**

Run: `pytest -v`
Expected: PASS (every test across `tests/unit/`, `tests/integration/`, `tests/api/`, and `tests/test_full_p2p_flow.py`)

- [ ] **Step 5: Commit**

```bash
git add tests/test_full_p2p_flow.py README.md
git commit -m "Add end-to-end P2P golden-path test and rewrite README for the new architecture"
```
