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
