# app/infrastructure/db/repositories.py
from app.infrastructure.db.mappers import (
    gr_to_domain,
    gr_to_model,
    journal_entry_to_domain,
    journal_entry_to_model,
    payment_to_domain,
    payment_to_model,
    po_to_domain,
    po_to_model,
    pr_to_domain,
    pr_to_model,
)
from app.infrastructure.db.models import (
    GRModel,
    JournalEntryModel,
    PaymentModel,
    POModel,
    PRModel,
)


class SqlAlchemyPRRepository:
    def __init__(self, session):
        self.session = session

    def add(self, pr):
        model = pr_to_model(pr)
        self.session.add(model)
        self.session.flush()
        pr.id = model.id
        return pr

    def get(self, pr_id):
        model = self.session.get(PRModel, pr_id)
        return pr_to_domain(model) if model else None

    def list(self):
        return [pr_to_domain(m) for m in self.session.query(PRModel).all()]

    def update(self, pr):
        model = self.session.get(PRModel, pr.id)
        model.status = pr.status.value
        self.session.flush()


class SqlAlchemyPORepository:
    def __init__(self, session):
        self.session = session

    def add(self, po):
        model = po_to_model(po)
        self.session.add(model)
        self.session.flush()
        po.id = model.id
        return po

    def get(self, po_id):
        model = self.session.get(POModel, po_id)
        return po_to_domain(model) if model else None

    def list(self):
        return [po_to_domain(m) for m in self.session.query(POModel).all()]

    def update(self, po):
        model = self.session.get(POModel, po.id)
        model.status = po.status.value
        lines_by_number = {l.line_number: l for l in model.lines}
        for line in po.lines:
            lines_by_number[line.line_number].quantity_received = line.quantity_received
        self.session.flush()


class SqlAlchemyGRRepository:
    def __init__(self, session):
        self.session = session

    def add(self, gr):
        model = gr_to_model(gr)
        self.session.add(model)
        self.session.flush()
        gr.id = model.id
        return gr

    def get(self, gr_id):
        model = self.session.get(GRModel, gr_id)
        return gr_to_domain(model) if model else None

    def list(self):
        return [gr_to_domain(m) for m in self.session.query(GRModel).all()]

    def update(self, gr):
        model = self.session.get(GRModel, gr.id)
        model.status = gr.status.value
        model.total_amount = gr.total_amount
        self.session.flush()


class SqlAlchemyPaymentRepository:
    def __init__(self, session):
        self.session = session

    def add(self, payment):
        model = payment_to_model(payment)
        self.session.add(model)
        self.session.flush()
        payment.id = model.id
        return payment

    def get(self, payment_id):
        model = self.session.get(PaymentModel, payment_id)
        return payment_to_domain(model) if model else None

    def list(self):
        return [payment_to_domain(m) for m in self.session.query(PaymentModel).all()]

    def update(self, payment):
        model = self.session.get(PaymentModel, payment.id)
        model.status = payment.status.value
        self.session.flush()

    def get_by_gr_id(self, gr_id):
        model = self.session.query(PaymentModel).filter_by(gr_id=gr_id).first()
        return payment_to_domain(model) if model else None


class SqlAlchemyJournalRepository:
    def __init__(self, session):
        self.session = session

    def add(self, entry):
        model = journal_entry_to_model(entry)
        self.session.add(model)
        self.session.flush()
        entry.id = model.id
        return entry

    def list(self):
        return [
            journal_entry_to_domain(m) for m in self.session.query(JournalEntryModel).all()
        ]
