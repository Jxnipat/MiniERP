from app.domain.purchase_requisition.entities import PRLine, PurchaseRequisition
from app.domain.shared.errors import NotFoundError


class PRService:
    def __init__(self, uow) -> None:
        self.uow = uow

    def create(self, requested_by: str, lines: list[dict]) -> PurchaseRequisition:
        with self.uow:
            pr = PurchaseRequisition.create(
                requested_by=requested_by,
                lines=[PRLine(**line) for line in lines],
            )
            self.uow.pr_repo.add(pr)
            self.uow.commit()
            return pr

    def get(self, pr_id: int) -> PurchaseRequisition:
        with self.uow:
            pr = self.uow.pr_repo.get(pr_id)
            if pr is None:
                raise NotFoundError(f"purchase requisition {pr_id} not found")
            return pr

    def list(self) -> list[PurchaseRequisition]:
        with self.uow:
            return self.uow.pr_repo.list()

    def submit(self, pr_id: int) -> PurchaseRequisition:
        return self._transition(pr_id, "submit")

    def approve(self, pr_id: int) -> PurchaseRequisition:
        return self._transition(pr_id, "approve")

    def reject(self, pr_id: int) -> PurchaseRequisition:
        return self._transition(pr_id, "reject")

    def _transition(self, pr_id: int, action: str) -> PurchaseRequisition:
        with self.uow:
            pr = self.uow.pr_repo.get(pr_id)
            if pr is None:
                raise NotFoundError(f"purchase requisition {pr_id} not found")
            getattr(pr, action)()
            self.uow.pr_repo.update(pr)
            self.uow.commit()
            return pr
