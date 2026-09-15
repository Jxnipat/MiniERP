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
