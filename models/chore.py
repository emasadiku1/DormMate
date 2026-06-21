from datetime import datetime, date, timedelta

from . import db


FREQUENCY_DAYS = {
    "daily": 1,
    "weekly": 7,
    "biweekly": 14,
    "monthly": 30,
    "custom": None,
}


class Chore(db.Model):
    __tablename__ = "chores"

    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey("households.id"), nullable=False, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(400), nullable=True)

    frequency = db.Column(db.String(20), nullable=False, default="weekly")
    custom_interval_days = db.Column(db.Integer, nullable=True)  # used when frequency == "custom"

    # Assignment: fixed user or auto-rotation
    rotation_mode = db.Column(db.Boolean, default=False, nullable=False)  # False = fixed, True = rotate
    assigned_to = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)  # fixed assignee
    rotation_index = db.Column(db.Integer, default=0, nullable=False)  # current position in rotation

    last_completed_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    household = db.relationship("Household", backref=db.backref("chores", lazy="dynamic"))
    creator = db.relationship("User", foreign_keys=[created_by], backref=db.backref("created_chores", lazy="dynamic"))
    assignee = db.relationship("User", foreign_keys=[assigned_to], backref=db.backref("assigned_chores", lazy="dynamic"))
    completions = db.relationship("ChoreCompletion", back_populates="chore", cascade="all, delete-orphan",
                                   order_by="ChoreCompletion.completed_at.desc()")

    FREQUENCIES = [
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("biweekly", "Every 2 weeks"),
        ("monthly", "Monthly"),
        ("custom", "Custom interval"),
    ]

    @property
    def interval_days(self):
        if self.frequency == "custom":
            return self.custom_interval_days or 7
        return FREQUENCY_DAYS.get(self.frequency, 7)

    @property
    def next_due_date(self):
        base = self.last_completed_at.date() if self.last_completed_at else self.created_at.date()
        return base + timedelta(days=self.interval_days)

    @property
    def is_overdue(self):
        return self.next_due_date < date.today()

    @property
    def is_due_today(self):
        return self.next_due_date == date.today()

    @property
    def days_until_due(self):
        delta = (self.next_due_date - date.today()).days
        return delta

    def get_current_assignee(self, members):
        """Return the User who should do this chore right now."""
        if not self.rotation_mode:
            return self.assignee
        if not members:
            return None
        idx = self.rotation_index % len(members)
        return members[idx]

    def advance_rotation(self, members):
        """Move rotation forward one step after completion."""
        if self.rotation_mode and members:
            self.rotation_index = (self.rotation_index + 1) % len(members)

    def get_frequency_label(self):
        for key, label in self.FREQUENCIES:
            if key == self.frequency:
                if self.frequency == 'custom' and self.custom_interval_days:
                    return f'Every {self.custom_interval_days} days'
                return label
        return self.frequency.capitalize()

    def __repr__(self):
        return f"<Chore #{self.id} '{self.title}'>"


class ChoreCompletion(db.Model):
    __tablename__ = "chore_completions"

    id = db.Column(db.Integer, primary_key=True)
    chore_id = db.Column(db.Integer, db.ForeignKey("chores.id"), nullable=False, index=True)
    completed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)
    note = db.Column(db.String(255), nullable=True)

    chore = db.relationship("Chore", back_populates="completions")
    user = db.relationship("User", backref=db.backref("chore_completions", lazy="dynamic"))

    def __repr__(self):
        return f"<ChoreCompletion chore={self.chore_id} by={self.completed_by}>"