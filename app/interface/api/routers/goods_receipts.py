# app/interface/api/routers/goods_receipts.py
from fastapi import APIRouter, Depends

from app.application.services.gr_service import GRService
from app.interface.api.deps import get_gr_service
from app.interface.api.error_handling import run
from app.interface.api.schemas import GRCreate, GROut

router = APIRouter(prefix="/goods-receipts", tags=["Goods Receipts"])


@router.post("", response_model=GROut, status_code=201)
def create_gr(payload: GRCreate, service: GRService = Depends(get_gr_service)) -> GROut:
    gr = run(
        lambda: service.create(
            po_id=payload.po_id, lines=[line.model_dump() for line in payload.lines]
        )
    )
    return GROut.model_validate(gr)


@router.get("", response_model=list[GROut])
def list_grs(service: GRService = Depends(get_gr_service)) -> list[GROut]:
    return [GROut.model_validate(gr) for gr in service.list()]


@router.get("/{gr_id}", response_model=GROut)
def get_gr(gr_id: int, service: GRService = Depends(get_gr_service)) -> GROut:
    return GROut.model_validate(run(lambda: service.get(gr_id)))


@router.post("/{gr_id}/post", response_model=GROut)
def post_gr(gr_id: int, service: GRService = Depends(get_gr_service)) -> GROut:
    return GROut.model_validate(run(lambda: service.post(gr_id)))
