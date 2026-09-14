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
