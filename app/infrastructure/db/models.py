from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.infrastructure.db.base import Base


class AccountModel(Base):
    __tablename__ = "accounts"

    code = Column(String, primary_key=True)
    name = Column(String, nullable=False)


class PRModel(Base):
    __tablename__ = "purchase_requisitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    requested_by = Column(String, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)

    lines = relationship("PRLineModel", cascade="all, delete-orphan", backref="pr")


class PRLineModel(Base):
    __tablename__ = "pr_lines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pr_id = Column(Integer, ForeignKey("purchase_requisitions.id"), nullable=False)
    item_name = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)


class POModel(Base):
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pr_id = Column(Integer, ForeignKey("purchase_requisitions.id"), nullable=False)
    vendor_name = Column(String, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)

    lines = relationship("POLineModel", cascade="all, delete-orphan", backref="po")


class POLineModel(Base):
    __tablename__ = "po_lines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    po_id = Column(Integer, ForeignKey("purchase_orders.id"), nullable=False)
    line_number = Column(Integer, nullable=False)
    item_name = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    quantity_received = Column(Integer, nullable=False, default=0)


class GRModel(Base):
    __tablename__ = "goods_receipts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    po_id = Column(Integer, ForeignKey("purchase_orders.id"), nullable=False)
    status = Column(String, nullable=False)
    total_amount = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False)

    lines = relationship("GRLineModel", cascade="all, delete-orphan", backref="gr")


class GRLineModel(Base):
    __tablename__ = "gr_lines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    gr_id = Column(Integer, ForeignKey("goods_receipts.id"), nullable=False)
    line_number = Column(Integer, nullable=False)
    quantity_received = Column(Integer, nullable=False)


class PaymentModel(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    gr_id = Column(Integer, ForeignKey("goods_receipts.id"), nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)


class JournalEntryModel(Base):
    __tablename__ = "journal_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_event = Column(String, nullable=False)
    source_id = Column(Integer, nullable=False)
    posted_at = Column(DateTime, nullable=False)

    lines = relationship(
        "JournalLineModel", cascade="all, delete-orphan", backref="entry"
    )


class JournalLineModel(Base):
    __tablename__ = "journal_lines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entry_id = Column(Integer, ForeignKey("journal_entries.id"), nullable=False)
    account_code = Column(String, nullable=False)
    debit = Column(Float, nullable=False, default=0.0)
    credit = Column(Float, nullable=False, default=0.0)
