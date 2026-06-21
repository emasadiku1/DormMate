from datetime import datetime

from . import db


class HouseRule(db.Model):
    __tablename__ = "house_rules"

    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey("households.id"), nullable=False, unique=True)
    content = db.Column(db.Text, nullable=False, default="")
    updated_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    household = db.relationship("Household", backref=db.backref("house_rule", uselist=False))
    updated_by = db.relationship("User", backref=db.backref("rule_edits", lazy="dynamic"))

    def __repr__(self):
        return f"<HouseRule household={self.household_id}>"
