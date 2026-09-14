# app/interface/api/routers/purchase_orders.py
from fastapi import APIRouter, Depends

from app.application.services.po_service import POService
from app.interface.api.deps import get_po_service
from app.interface.api.error_handling import run
from app.interface.api.schemas import POCreate, POOut

router = APIRouter(prefix="/purchase-orders", tags=["Purchase Orders"])


@router.post("", response_model=POOut, status_code=201)
def create_po(payload: POCreate, service: POService = Depends(get_po_service)) -> POOut:
    po = run(
        lambda: service.create(
            pr_id=payload.pr_id,
            vendor_name=payload.vendor_name,
            lines=[line.model_dump() for line in payload.lines],
        )
    )
    return POOut.model_validate(po)


@router.get("", response_model=list[POOut])
def list_pos(service: POService = Depends(get_po_service)) -> list[POOut]:
    return [POOut.model_validate(po) for po in service.list()]


@router.get("/{po_id}", response_model=POOut)
def get_po(po_id: int, service: POService = Depends(get_po_service)) -> POOut:
    return POOut.model_validate(run(lambda: service.get(po_id)))


@router.post("/{po_id}/submit", response_model=POOut)
def submit_po(po_id: int, service: POService = Depends(get_po_service)) -> POOut:
    return POOut.model_validate(run(lambda: service.submit(po_id)))


@router.post("/{po_id}/approve", response_model=POOut)
def approve_po(po_id: int, service: POService = Depends(get_po_service)) -> POOut:
    return POOut.model_validate(run(lambda: service.approve(po_id)))


@router.post("/{po_id}/cancel", response_model=POOut)
def cancel_po(po_id: int, service: POService = Depends(get_po_service)) -> POOut:
    return POOut.model_validate(run(lambda: service.cancel(po_id)))
