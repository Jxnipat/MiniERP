# app/interface/api/routers/purchase_requisitions.py
from fastapi import APIRouter, Depends

from app.application.services.pr_service import PRService
from app.interface.api.deps import get_pr_service
from app.interface.api.error_handling import run
from app.interface.api.schemas import PRCreate, PROut

router = APIRouter(prefix="/purchase-requisitions", tags=["Purchase Requisitions"])


@router.post("", response_model=PROut, status_code=201)
def create_pr(payload: PRCreate, service: PRService = Depends(get_pr_service)) -> PROut:
    pr = service.create(
        requested_by=payload.requested_by,
        lines=[line.model_dump() for line in payload.lines],
    )
    return PROut.model_validate(pr)


@router.get("", response_model=list[PROut])
def list_prs(service: PRService = Depends(get_pr_service)) -> list[PROut]:
    return [PROut.model_validate(pr) for pr in service.list()]


@router.get("/{pr_id}", response_model=PROut)
def get_pr(pr_id: int, service: PRService = Depends(get_pr_service)) -> PROut:
    return PROut.model_validate(run(lambda: service.get(pr_id)))


@router.post("/{pr_id}/submit", response_model=PROut)
def submit_pr(pr_id: int, service: PRService = Depends(get_pr_service)) -> PROut:
    return PROut.model_validate(run(lambda: service.submit(pr_id)))


@router.post("/{pr_id}/approve", response_model=PROut)
def approve_pr(pr_id: int, service: PRService = Depends(get_pr_service)) -> PROut:
    return PROut.model_validate(run(lambda: service.approve(pr_id)))


@router.post("/{pr_id}/reject", response_model=PROut)
def reject_pr(pr_id: int, service: PRService = Depends(get_pr_service)) -> PROut:
    return PROut.model_validate(run(lambda: service.reject(pr_id)))
