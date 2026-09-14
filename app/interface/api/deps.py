# app/interface/api/deps.py
from fastapi import Depends

from app.application.services.gr_service import GRService
from app.application.services.ledger_service import LedgerService
from app.application.services.payment_service import PaymentService
from app.application.services.po_service import POService
from app.application.services.pr_service import PRService
from app.infrastructure.db.session import SessionLocal
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork


def get_uow() -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(SessionLocal)


def get_pr_service(uow: SqlAlchemyUnitOfWork = Depends(get_uow)) -> PRService:
    return PRService(uow)


def get_po_service(uow: SqlAlchemyUnitOfWork = Depends(get_uow)) -> POService:
    return POService(uow)


def get_gr_service(uow: SqlAlchemyUnitOfWork = Depends(get_uow)) -> GRService:
    return GRService(uow)


def get_payment_service(
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> PaymentService:
    return PaymentService(uow)


def get_ledger_service(
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> LedgerService:
    return LedgerService(uow)
