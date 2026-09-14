from app.domain.accounting.entities import Account

INVENTORY = Account(code="1000", name="Inventory")
CASH_BANK = Account(code="1100", name="Cash/Bank")
GR_IR_CLEARING = Account(code="2100", name="GR/IR Clearing")

SEED_ACCOUNTS: list[Account] = [INVENTORY, CASH_BANK, GR_IR_CLEARING]
