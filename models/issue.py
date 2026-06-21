from datetime import datetime

from . import db


class Issue(db.Model):
    __tablename__ = "issues"

    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey("households.id"), nullable=False, index=True)
    reported_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="open")  # open | in_progress | resolved
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)

    STATUSES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("resolved", "Resolved"),
    ]

    household = db.relationship("Household", backref=db.backref("issues", lazy="dynamic"))
    reported_by = db.relationship("User", backref=db.backref("reported_issues", lazy="dynamic"))

    def __repr__(self):
        return f"<Issue #{self.id} '{self.title}' [{self.status}]>"
