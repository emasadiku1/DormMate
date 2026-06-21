from collections import defaultdict
from decimal import Decimal

from flask import Blueprint, render_template, redirect, url_for, flash, g

from models import db, Membership, User, Expense, UserBadge, Badge
from models.chore import ChoreCompletion
from utils import login_required

stats_bp = Blueprint("stats", __name__)


@stats_bp.route("/household/<int:household_id>/stats")
@login_required
def leaderboard(household_id):
    membership = Membership.query.filter_by(
        user_id=g.user.id, household_id=household_id
    ).first()
    if not membership:
        flash("You're not a member of that household.", "error")
        return redirect(url_for("household.choose"))

    household = membership.household
    members = household.members

    # ── Total paid per member ─────────────────────────────────────────────────
    paid_by: dict[int, Decimal] = defaultdict(Decimal)
    for expense in Expense.query.filter_by(household_id=household_id).all():
        paid_by[expense.payer_id] += expense.amount

    # ── Chores completed per member ───────────────────────────────────────────
    from models.chore import Chore
    household_chore_ids = [
        c.id for c in Chore.query.filter_by(household_id=household_id).all()
    ]
    chores_done: dict[int, int] = defaultdict(int)
    if household_chore_ids:
        completions = (
            ChoreCompletion.query
            .filter(ChoreCompletion.chore_id.in_(household_chore_ids))
            .all()
        )
        for comp in completions:
            chores_done[comp.completed_by] += 1

    # ── Badges per member ─────────────────────────────────────────────────────
    badges_by_user: dict[int, list] = defaultdict(list)
    for member in members:
        ubs = (
            UserBadge.query
            .filter_by(user_id=member.id)
            .join(Badge)
            .all()
        )
        badges_by_user[member.id] = [ub.badge for ub in ubs]

    # ── Build sorted leaderboard rows ─────────────────────────────────────────
    rows = []
    for member in members:
        rows.append({
            "user": member,
            "total_paid": paid_by.get(member.id, Decimal("0")),
            "chores_done": chores_done.get(member.id, 0),
            "badges": badges_by_user.get(member.id, []),
            "badge_count": len(badges_by_user.get(member.id, [])),
        })

    # Sort by total paid descending
    rows.sort(key=lambda r: r["total_paid"], reverse=True)

    return render_template(
        "stats/leaderboard.html",
        household=household,
        membership=membership,
        rows=rows,
    )
