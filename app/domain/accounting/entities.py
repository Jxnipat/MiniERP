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
