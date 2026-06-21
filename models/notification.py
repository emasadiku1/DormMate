from datetime import datetime
from . import db


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    household_id = db.Column(db.Integer, db.ForeignKey("households.id"), nullable=True, index=True)

    # Type: expense_added | expense_updated | expense_deleted | chore_due |
    #       chore_overdue | payment_received | payment_sent | chore_completed |
    #       member_joined
    notif_type = db.Column(db.String(40), nullable=False)
    title = db.Column(db.String(140), nullable=False)
    body = db.Column(db.String(400), nullable=True)

    # Optional deep-link
    link_url = db.Column(db.String(255), nullable=True)

    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", backref=db.backref("notifications", lazy="dynamic"))

    # Icons per type
    ICONS = {
        "expense_added":   "💸",
        "expense_updated": "✏️",
        "expense_deleted": "🗑️",
        "chore_due":       "🧹",
        "chore_overdue":   "⚠️",
        "chore_completed": "✅",
        "payment_received": "💰",
        "payment_sent":    "📤",
        "member_joined":   "🏠",
    }

    @property
    def icon(self):
        return self.ICONS.get(self.notif_type, "🔔")

    @property
    def time_ago(self):
        delta = datetime.utcnow() - self.created_at
        s = int(delta.total_seconds())
        if s < 60:
            return "just now"
        if s < 3600:
            return f"{s // 60}m ago"
        if s < 86400:
            return f"{s // 3600}h ago"
        return f"{delta.days}d ago"

    def mark_read(self):
        self.is_read = True

    def __repr__(self):
        return f"<Notification {self.notif_type} → user {self.user_id}>"
