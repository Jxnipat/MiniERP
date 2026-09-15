# app/interface/api/routers/payments.py
from fastapi import APIRouter, Depends

from app.application.services.payment_service import PaymentService
from app.interface.api.deps import get_payment_service
from app.interface.api.error_handling import run
from app.interface.api.schemas import PaymentCreate, PaymentOut

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post("", response_model=PaymentOut, status_code=201)
def create_payment(
    payload: PaymentCreate, service: PaymentService = Depends(get_payment_service)
) -> PaymentOut:
    payment = run(lambda: service.create(gr_id=payload.gr_id, amount=payload.amount))
    return PaymentOut.model_validate(payment)


@router.get("", response_model=list[PaymentOut])
def list_payments(
    service: PaymentService = Depends(get_payment_service),
) -> list[PaymentOut]:
    return [PaymentOut.model_validate(p) for p in service.list()]


@router.get("/{payment_id}", response_model=PaymentOut)
def get_payment(
    payment_id: int, service: PaymentService = Depends(get_payment_service)
) -> PaymentOut:
    return PaymentOut.model_validate(run(lambda: service.get(payment_id)))


@router.post("/{payment_id}/approve", response_model=PaymentOut)
def approve_payment(
    payment_id: int, service: PaymentService = Depends(get_payment_service)
) -> PaymentOut:
    return PaymentOut.model_validate(run(lambda: service.approve(payment_id)))


@router.post("/{payment_id}/pay", response_model=PaymentOut)
def pay_payment(
    payment_id: int, service: PaymentService = Depends(get_payment_service)
) -> PaymentOut:
    return PaymentOut.model_validate(run(lambda: service.pay(payment_id)))
