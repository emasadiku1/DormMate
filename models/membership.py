from datetime import datetime

from . import db


class Membership(db.Model):
    __tablename__ = "memberships"
    __table_args__ = (
        db.UniqueConstraint("user_id", "household_id", name="uq_user_household"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    household_id = db.Column(db.Integer, db.ForeignKey("households.id"), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="member")  # "admin" or "member"
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="memberships")
    household = db.relationship("Household", back_populates="memberships")

    @property
    def is_admin(self):
        return self.role == "admin"

    def __repr__(self):
        return f"<Membership user={self.user_id} household={self.household_id} role={self.role}>"
