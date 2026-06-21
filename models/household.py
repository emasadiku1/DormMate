import secrets
from datetime import datetime

from . import db


class Household(db.Model):
    __tablename__ = "households"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    invite_code = db.Column(db.String(12), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    memberships = db.relationship(
        "Membership", back_populates="household", cascade="all, delete-orphan"
    )

    @property
    def members(self):
        return [m.user for m in self.memberships]

    @staticmethod
    def generate_invite_code():
        while True:
            code = secrets.token_hex(3).upper()
            if not Household.query.filter_by(invite_code=code).first():
                return code

    def __repr__(self):
        return f"<Household {self.name}>"