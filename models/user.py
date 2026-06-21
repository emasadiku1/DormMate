from datetime import datetime

from werkzeug.security import generate_password_hash, check_password_hash

from . import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    avatar_url = db.Column(db.String(255), nullable=True)
    room_number = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    memberships = db.relationship(
        "Membership", back_populates="user", cascade="all, delete-orphan"
    )

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    @property
    def households(self):
        return [m.household for m in self.memberships]

    def __repr__(self):
        return f"<User {self.email}>"
