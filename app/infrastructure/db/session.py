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
