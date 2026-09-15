from app.application.gl_engine import GLEngine
from app.domain.goods_receipt.entities import GoodsReceipt, GRLine
from app.domain.purchase_order.entities import POStatus
from app.domain.shared.errors import DomainValidationError, NotFoundError


class GRService:
    def __init__(self, uow, gl_engine: GLEngine | None = None) -> None:
        self.uow = uow
        self.gl_engine = gl_engine or GLEngine()

    def create(self, po_id: int, lines: list[dict]) -> GoodsReceipt:
        with self.uow:
            po = self.uow.po_repo.get(po_id)
            if po is None:
                raise NotFoundError(f"purchase order {po_id} not found")
            if po.status not in (POStatus.APPROVED, POStatus.PARTIALLY_RECEIVED):
                raise DomainValidationError(
                    f"cannot create a goods receipt against a purchase order in status '{po.status}'"
                )
            gr = GoodsReceipt.create(po_id=po_id, lines=[GRLine(**line) for line in lines])
            self.uow.gr_repo.add(gr)
            self.uow.commit()
            return gr

    def get(self, gr_id: int) -> GoodsReceipt:
        with self.uow:
            gr = self.uow.gr_repo.get(gr_id)
            if gr is None:
                raise NotFoundError(f"goods receipt {gr_id} not found")
            return gr

    def list(self) -> list[GoodsReceipt]:
        with self.uow:
            return self.uow.gr_repo.list()

    def post(self, gr_id: int) -> GoodsReceipt:
        with self.uow:
            gr = self.uow.gr_repo.get(gr_id)
            if gr is None:
                raise NotFoundError(f"goods receipt {gr_id} not found")
            po = self.uow.po_repo.get(gr.po_id)
            if po is None:
                raise NotFoundError(f"purchase order {gr.po_id} not found")

            po_lines_by_number = {line.line_number: line for line in po.lines}
            amount = 0.0
            for gr_line in gr.lines:
                po_line = po_lines_by_number.get(gr_line.line_number)
                if po_line is None:
                    raise DomainValidationError(
                        f"PO has no line number {gr_line.line_number}"
                    )
                amount += gr_line.quantity_received * po_line.unit_price

            po.receive_goods(
                {line.line_number: line.quantity_received for line in gr.lines}
            )
            gr.post(amount)

            self.uow.po_repo.update(po)
            self.uow.gr_repo.update(gr)
            for event in gr.pull_events():
                self.gl_engine.handle(event, self.uow)
            self.uow.commit()
            return gr
