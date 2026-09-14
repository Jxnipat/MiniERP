from app.application.gl_engine import GLEngine
from app.domain.payment.entities import Payment
from app.domain.shared.errors import DomainValidationError, NotFoundError


class PaymentService:
    def __init__(self, uow, gl_engine: GLEngine | None = None) -> None:
        self.uow = uow
        self.gl_engine = gl_engine or GLEngine()

    def create(self, gr_id: int, amount: float) -> Payment:
        with self.uow:
            gr = self.uow.gr_repo.get(gr_id)
            if gr is None:
                raise NotFoundError(f"goods receipt {gr_id} not found")
            existing = self.uow.payment_repo.get_by_gr_id(gr_id)
            if existing is not None:
                raise DomainValidationError(
                    f"goods receipt {gr_id} already has a payment"
                )
            payment = Payment.create_for_gr(
                gr_id=gr_id,
                gr_status=gr.status,
                gr_total_amount=gr.total_amount,
                amount=amount,
            )
            self.uow.payment_repo.add(payment)
            self.uow.commit()
            return payment

    def get(self, payment_id: int) -> Payment:
        with self.uow:
            payment = self.uow.payment_repo.get(payment_id)
            if payment is None:
                raise NotFoundError(f"payment {payment_id} not found")
            return payment

    def list(self) -> list[Payment]:
        with self.uow:
            return self.uow.payment_repo.list()

    def approve(self, payment_id: int) -> Payment:
        return self._transition(payment_id, "approve")

    def pay(self, payment_id: int) -> Payment:
        with self.uow:
            payment = self.uow.payment_repo.get(payment_id)
            if payment is None:
                raise NotFoundError(f"payment {payment_id} not found")
            payment.pay()
            self.uow.payment_repo.update(payment)
            for event in payment.pull_events():
                self.gl_engine.handle(event, self.uow)
            self.uow.commit()
            return payment

    def _transition(self, payment_id: int, action: str) -> Payment:
        with self.uow:
            payment = self.uow.payment_repo.get(payment_id)
            if payment is None:
                raise NotFoundError(f"payment {payment_id} not found")
            getattr(payment, action)()
            self.uow.payment_repo.update(payment)
            self.uow.commit()
            return payment
