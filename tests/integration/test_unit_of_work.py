import pytest

from app.domain.purchase_requisition.entities import PRLine, PurchaseRequisition
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork


def test_commit_persists_changes_visible_in_a_new_unit_of_work(session_factory):
    uow = SqlAlchemyUnitOfWork(session_factory)
    with uow:
        pr = PurchaseRequisition.create(
            requested_by="alice",
            lines=[PRLine(item_name="Laptop Stand", quantity=10, unit_price=25.50)],
        )
        uow.pr_repo.add(pr)
        uow.commit()
        pr_id = pr.id

    uow2 = SqlAlchemyUnitOfWork(session_factory)
    with uow2:
        fetched = uow2.pr_repo.get(pr_id)

    assert fetched is not None
    assert fetched.requested_by == "alice"


def test_exception_before_commit_rolls_back(session_factory):
    uow = SqlAlchemyUnitOfWork(session_factory)
    with pytest.raises(RuntimeError):
        with uow:
            pr = PurchaseRequisition.create(
                requested_by="alice",
                lines=[PRLine(item_name="Laptop Stand", quantity=10, unit_price=25.50)],
            )
            uow.pr_repo.add(pr)
            raise RuntimeError("boom before commit")

    uow2 = SqlAlchemyUnitOfWork(session_factory)
    with uow2:
        assert uow2.pr_repo.list() == []
