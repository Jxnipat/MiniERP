# tests/conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.infrastructure.db.base import Base
from app.infrastructure.db.session import seed_accounts
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork


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


@pytest.fixture()
def uow(session_factory):
    return SqlAlchemyUnitOfWork(session_factory)
