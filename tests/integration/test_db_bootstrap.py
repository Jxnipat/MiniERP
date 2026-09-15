from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.infrastructure.db.base import Base
from app.infrastructure.db.models import AccountModel
from app.infrastructure.db.session import seed_accounts


def test_seed_accounts_creates_the_three_fixed_accounts():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    with factory() as session:
        seed_accounts(session)
        session.commit()
        codes = {a.code for a in session.query(AccountModel).all()}

    assert codes == {"1000", "1100", "2100"}
    engine.dispose()


def test_seed_accounts_is_idempotent():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    with factory() as session:
        seed_accounts(session)
        session.commit()
        seed_accounts(session)
        session.commit()
        count = session.query(AccountModel).count()

    assert count == 3
    engine.dispose()
