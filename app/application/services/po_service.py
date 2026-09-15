from app.domain.purchase_order.entities import POLine, PurchaseOrder
from app.domain.shared.errors import NotFoundError


class POService:
    def __init__(self, uow) -> None:
        self.uow = uow

    def create(self, pr_id: int, vendor_name: str, lines: list[dict]) -> PurchaseOrder:
        with self.uow:
            pr = self.uow.pr_repo.get(pr_id)
            if pr is None:
                raise NotFoundError(f"purchase requisition {pr_id} not found")
            po = PurchaseOrder.create_from_pr(
                pr_id=pr_id,
                pr_status=pr.status,
                vendor_name=vendor_name,
                lines=[POLine(line_number=i + 1, **line) for i, line in enumerate(lines)],
            )
            self.uow.po_repo.add(po)
            self.uow.commit()
            return po

    def get(self, po_id: int) -> PurchaseOrder:
        with self.uow:
            po = self.uow.po_repo.get(po_id)
            if po is None:
                raise NotFoundError(f"purchase order {po_id} not found")
            return po

    def list(self) -> list[PurchaseOrder]:
        with self.uow:
            return self.uow.po_repo.list()

    def submit(self, po_id: int) -> PurchaseOrder:
        return self._transition(po_id, "submit")

    def approve(self, po_id: int) -> PurchaseOrder:
        return self._transition(po_id, "approve")

    def cancel(self, po_id: int) -> PurchaseOrder:
        return self._transition(po_id, "cancel")

    def _transition(self, po_id: int, action: str) -> PurchaseOrder:
        with self.uow:
            po = self.uow.po_repo.get(po_id)
            if po is None:
                raise NotFoundError(f"purchase order {po_id} not found")
            getattr(po, action)()
            self.uow.po_repo.update(po)
            self.uow.commit()
            return po
