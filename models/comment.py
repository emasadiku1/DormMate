from datetime import datetime

from . import db


class Comment(db.Model):
    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True)
    expense_id = db.Column(db.Integer, db.ForeignKey("expenses.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    expense = db.relationship("Expense", backref=db.backref("comments", lazy="dynamic", order_by="Comment.created_at"))
    user = db.relationship("User", backref=db.backref("comments", lazy="dynamic"))

    def __repr__(self):
        return f"<Comment #{self.id} on expense={self.expense_id}>"
