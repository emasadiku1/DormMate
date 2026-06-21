from collections import defaultdict
from decimal import Decimal

from flask import Blueprint, render_template, redirect, url_for, flash, g
from sqlalchemy import func

from models import db, Expense, ExpenseSplit, Membership, User
from utils import login_required

reports_bp = Blueprint("reports", __name__)


@reports_bp.route("/household/<int:household_id>/reports")
@login_required
def dashboard(household_id):
    membership = Membership.query.filter_by(
        user_id=g.user.id, household_id=household_id
    ).first()
    if not membership:
        flash("You're not a member of that household.", "error")
        return redirect(url_for("household.choose"))

    household = membership.household
    members = household.members

    expenses = (
        Expense.query
        .filter_by(household_id=household_id)
        .order_by(Expense.date.asc())
        .all()
    )

    # ── Group by month ────────────────────────────────────────────────────────
    # months_data: { "2025-03": { total, by_category: {cat: amount}, by_person: {user_id: amount} } }
    months_data: dict[str, dict] = {}

    for expense in expenses:
        key = expense.date.strftime("%Y-%m")
        if key not in months_data:
            months_data[key] = {
                "label": expense.date.strftime("%b %Y"),
                "total": Decimal("0"),
                "by_category": defaultdict(Decimal),
                "by_person": defaultdict(Decimal),
            }
        m = months_data[key]
        m["total"] += expense.amount
        m["by_category"][expense.category] += expense.amount
        m["by_person"][expense.payer_id] += expense.amount

    # Sort months chronologically
    sorted_months = sorted(months_data.items())

    # ── Flatten for Chart.js ──────────────────────────────────────────────────
    month_labels = [v["label"] for _, v in sorted_months]
    month_totals = [float(v["total"]) for _, v in sorted_months]

    # Category totals across all time
    category_totals: dict[str, Decimal] = defaultdict(Decimal)
    for expense in expenses:
        category_totals[expense.category] += expense.amount

    category_labels = list(category_totals.keys())
    category_amounts = [float(category_totals[c]) for c in category_labels]

    # Per-person totals
    person_totals: dict[int, Decimal] = defaultdict(Decimal)
    for expense in expenses:
        person_totals[expense.payer_id] += expense.amount

    users_by_id = {m.id: m for m in members}
    person_labels = [users_by_id[uid].name for uid in person_totals if uid in users_by_id]
    person_amounts = [float(person_totals[uid]) for uid in person_totals if uid in users_by_id]

    return render_template(
        "reports/dashboard.html",
        household=household,
        membership=membership,
        month_labels=month_labels,
        month_totals=month_totals,
        category_labels=category_labels,
        category_amounts=category_amounts,
        person_labels=person_labels,
        person_amounts=person_amounts,
        sorted_months=sorted_months,
        members=members,
        users_by_id=users_by_id,
    )
