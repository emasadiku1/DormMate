from datetime import datetime, date

from . import db


class Event(db.Model):
    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey("households.id"), nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    date = db.Column(db.Date, nullable=False)
    type = db.Column(db.String(20), nullable=False, default="custom")  # rent_due | chore | custom
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    TYPES = [
        ("rent_due", "Rent Due"),
        ("chore", "Chore"),
        ("custom", "Custom"),
    ]

    household = db.relationship("Household", backref=db.backref("events", lazy="dynamic"))
    created_by = db.relationship("User", backref=db.backref("created_events", lazy="dynamic"))

    def __repr__(self):
        return f"<Event #{self.id} '{self.title}' on {self.date}>"
