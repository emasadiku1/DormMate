from datetime import datetime

from . import db


class UserBadge(db.Model):
    __tablename__ = "user_badges"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    badge_id = db.Column(db.Integer, db.ForeignKey("badges.id"), nullable=False)
    earned_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("user_badges", lazy="dynamic"))
    badge = db.relationship("Badge", back_populates="user_badges")

    def __repr__(self):
        return f"<UserBadge user={self.user_id} badge={self.badge_id}>"
