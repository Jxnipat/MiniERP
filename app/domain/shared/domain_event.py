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
