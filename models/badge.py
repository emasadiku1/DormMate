from datetime import datetime

from . import db


class Badge(db.Model):
    __tablename__ = "badges"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    label = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    icon = db.Column(db.String(10), nullable=False, default="🏅")

    user_badges = db.relationship("UserBadge", back_populates="badge", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Badge {self.code}>"
