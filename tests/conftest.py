# tests/conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.db.base import Base
from app.infrastructure.db.session import seed_accounts
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
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
