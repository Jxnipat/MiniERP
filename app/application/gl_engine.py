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
