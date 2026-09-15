from app.domain.accounting.chart_of_accounts import SEED_ACCOUNTS
from app.domain.accounting.entities import JournalEntry


class LedgerService:
    def __init__(self, uow) -> None:
        self.uow = uow

    def list_journal_entries(self) -> list[JournalEntry]:
        with self.uow:
            return self.uow.journal_repo.list()

    def trial_balance(self) -> dict[str, dict]:
        with self.uow:
            entries = self.uow.journal_repo.list()

        balances = {
            account.code: {"name": account.name, "debit": 0.0, "credit": 0.0}
            for account in SEED_ACCOUNTS
        }
        for entry in entries:
            for line in entry.lines:
                balances.setdefault(
                    line.account_code,
                    {"name": line.account_code, "debit": 0.0, "credit": 0.0},
                )
                balances[line.account_code]["debit"] += line.debit
                balances[line.account_code]["credit"] += line.credit
        return balances
