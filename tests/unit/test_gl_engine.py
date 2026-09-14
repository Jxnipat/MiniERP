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
