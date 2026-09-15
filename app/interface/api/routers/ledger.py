# app/interface/api/routers/ledger.py
from fastapi import APIRouter, Depends

from app.application.services.ledger_service import LedgerService
from app.interface.api.deps import get_ledger_service
from app.interface.api.schemas import JournalEntryOut, TrialBalanceRowOut

router = APIRouter(prefix="/ledger", tags=["Ledger"])


@router.get("/journal-entries", response_model=list[JournalEntryOut])
def list_journal_entries(
    service: LedgerService = Depends(get_ledger_service),
) -> list[JournalEntryOut]:
    return [JournalEntryOut.model_validate(e) for e in service.list_journal_entries()]


@router.get("/trial-balance", response_model=list[TrialBalanceRowOut])
def trial_balance(
    service: LedgerService = Depends(get_ledger_service),
) -> list[TrialBalanceRowOut]:
    balances = service.trial_balance()
    return [
        TrialBalanceRowOut(
            account_code=code,
            account_name=data["name"],
            debit=data["debit"],
            credit=data["credit"],
        )
        for code, data in balances.items()
    ]
