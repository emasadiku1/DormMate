"""
services/badge_checker.py

Call check_and_award(user, trigger) after key actions to award badges.
Triggers: 'expense_logged', 'split_settled', 'chore_completed'
"""

from models import db, Badge, UserBadge
from models.expense import Expense
from models.expense_split import ExpenseSplit
from models.chore import ChoreCompletion


def _already_earned(user, badge):
    return UserBadge.query.filter_by(user_id=user.id, badge_id=badge.id).first() is not None


def _award(user, badge):
    if not _already_earned(user, badge):
        ub = UserBadge(user_id=user.id, badge_id=badge.id)
        db.session.add(ub)


def _ensure_badge(code, label, description, icon):
    """Get or create a badge by code."""
    badge = Badge.query.filter_by(code=code).first()
    if not badge:
        badge = Badge(code=code, label=label, description=description, icon=icon)
        db.session.add(badge)
        db.session.flush()
    return badge


# Each entry: (code, label, description, icon, condition_fn(user))
BADGE_DEFINITIONS = [
    (
        "first_expense",
        "First Round",
        "Logged your very first expense.",
        "🧾",
        lambda user: Expense.query.filter_by(payer_id=user.id).count() >= 1,
    ),
    (
        "big_spender",
        "Big Spender",
        "Logged 10 or more expenses.",
        "💸",
        lambda user: Expense.query.filter_by(payer_id=user.id).count() >= 10,
    ),
    (
        "first_settle",
        "Square Up",
        "Settled your first debt.",
        "🤝",
        lambda user: ExpenseSplit.query.filter_by(user_id=user.id, is_settled=True).count() >= 1,
    ),
    (
        "on_time_streak_5",
        "On The Ball",
        "Settled 5 splits on time.",
        "⚡",
        lambda user: ExpenseSplit.query.filter_by(user_id=user.id, is_settled=True).count() >= 5,
    ),
    (
        "chore_first",
        "Pitching In",
        "Completed your first chore.",
        "🧹",
        lambda user: ChoreCompletion.query.filter_by(completed_by=user.id).count() >= 1,
    ),
    (
        "chore_streak_10",
        "Clean Machine",
        "Completed 10 chores.",
        "✨",
        lambda user: ChoreCompletion.query.filter_by(completed_by=user.id).count() >= 10,
    ),
]

TRIGGER_BADGES = {
    "expense_logged": ["first_expense", "big_spender"],
    "split_settled":  ["first_settle", "on_time_streak_5"],
    "chore_completed": ["chore_first", "chore_streak_10"],
}


def check_and_award(user, trigger: str):
    """
    Check badge conditions for the given trigger and award any newly earned badges.
    Call this after db.session.flush() so counts are up to date; commit after.
    """
    relevant_codes = TRIGGER_BADGES.get(trigger, [])
    for code, label, description, icon, condition_fn in BADGE_DEFINITIONS:
        if code not in relevant_codes:
            continue
        badge = _ensure_badge(code, label, description, icon)
        if condition_fn(user):
            _award(user, badge)
