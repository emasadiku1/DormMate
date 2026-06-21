from datetime import datetime

from . import db


class ExpenseSplit(db.Model):
    __tablename__ = "expense_splits"

    id = db.Column(db.Integer, primary_key=True)
    expense_id = db.Column(db.Integer, db.ForeignKey("expenses.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    amount_owed = db.Column(db.Numeric(10, 2), nullable=False)
    is_settled = db.Column(db.Boolean, default=False, nullable=False)
    settled_at = db.Column(db.DateTime, nullable=True)

    expense = db.relationship("Expense", back_populates="splits")
    user = db.relationship("User", backref=db.backref("splits_owed", lazy="dynamic"))

    def mark_paid(self):
        self.is_settled = True
        self.settled_at = datetime.utcnow()

    def __repr__(self):
        return f"<ExpenseSplit expense={self.expense_id} user={self.user_id} owes=${self.amount_owed} settled={self.is_settled}>"