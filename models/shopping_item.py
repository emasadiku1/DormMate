from datetime import datetime

from . import db


class ShoppingItem(db.Model):
    __tablename__ = "shopping_items"

    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey("households.id"), nullable=False, index=True)
    added_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    title = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    note = db.Column(db.String(255), nullable=True)

    is_purchased = db.Column(db.Boolean, default=False, nullable=False)
    purchased_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    purchased_at = db.Column(db.DateTime, nullable=True)

    # Optional: link to an expense logged after buying
    expense_id = db.Column(db.Integer, db.ForeignKey("expenses.id"), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    household = db.relationship("Household", backref=db.backref("shopping_items", lazy="dynamic"))
    adder = db.relationship("User", foreign_keys=[added_by], backref=db.backref("added_items", lazy="dynamic"))
    buyer = db.relationship("User", foreign_keys=[purchased_by], backref=db.backref("purchased_items", lazy="dynamic"))
    expense = db.relationship("Expense", backref=db.backref("shopping_items", lazy="dynamic"))

    def mark_purchased(self, user_id):
        self.is_purchased = True
        self.purchased_by = user_id
        self.purchased_at = datetime.utcnow()

    def unmark_purchased(self):
        self.is_purchased = False
        self.purchased_by = None
        self.purchased_at = None

    def __repr__(self):
        return f"<ShoppingItem #{self.id} '{self.title}' purchased={self.is_purchased}>"