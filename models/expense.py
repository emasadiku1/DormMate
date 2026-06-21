from datetime import datetime, date

from . import db


class Expense(db.Model):
    __tablename__ = "expenses"

    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey("households.id"), nullable=False, index=True)
    payer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    category = db.Column(db.String(50), nullable=False, default="general")
    date = db.Column(db.Date, nullable=False, default=date.today)
    note = db.Column(db.String(255), nullable=True)
    split_type = db.Column(db.String(20), nullable=False, default="equal")  # equal | percentage | custom
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    household = db.relationship("Household", backref=db.backref("expenses", lazy="dynamic"))
    payer = db.relationship("User", backref=db.backref("paid_expenses", lazy="dynamic"))
    splits = db.relationship("ExpenseSplit", back_populates="expense", cascade="all, delete-orphan")

    CATEGORIES = [
        ("groceries", "Groceries"),
        ("utilities", "Utilities"),
        ("rent", "Rent"),
        ("cleaning", "Cleaning"),
        ("takeout", "Takeout"),
        ("transport", "Transport"),
        ("entertainment", "Entertainment"),
        ("general", "General"),
    ]

    SPLIT_TYPES = ["equal", "percentage", "custom"]

    def __repr__(self):
        return f"<Expense #{self.id} ${self.amount} by user {self.payer_id}>"