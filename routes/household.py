from decimal import Decimal
from datetime import date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, g

from models import db, Household, Membership, Expense, ExpenseSplit, Chore, ShoppingItem
from models.event import Event
from models.issue import Issue
from models.user_badge import UserBadge
from services.debt_calculator import compute_net_balances, simplify_debts
from utils import login_required, CATEGORY_ICONS

household_bp = Blueprint("household", __name__, url_prefix="/household")


@household_bp.route("/")
@login_required
def dashboard_redirect():
    memberships = g.user.memberships
    if not memberships:
        return redirect(url_for("household.choose"))
    return redirect(url_for("household.dashboard", household_id=memberships[0].household_id))


@household_bp.route("/choose")
@login_required
def choose():
    return render_template("household/choose.html")


@household_bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Give the household a name.", "error")
            return render_template("household/create.html")

        household = Household(name=name, invite_code=Household.generate_invite_code())
        db.session.add(household)
        db.session.flush()

        membership = Membership(user_id=g.user.id, household_id=household.id, role="admin")
        db.session.add(membership)
        db.session.commit()

        flash(f"{household.name} is set up. Invite code: {household.invite_code}", "success")
        return redirect(url_for("household.dashboard", household_id=household.id))

    return render_template("household/create.html")


@household_bp.route("/join", methods=["GET", "POST"])
@login_required
def join():
    if request.method == "POST":
        code = request.form.get("invite_code", "").strip().upper()
        household = Household.query.filter_by(invite_code=code).first()

        if household is None:
            flash("That invite code doesn't match a household.", "error")
            return render_template("household/join.html", invite_code=code)

        existing = Membership.query.filter_by(
            user_id=g.user.id, household_id=household.id
        ).first()
        if existing:
            flash(f"You're already in {household.name}.", "error")
            return redirect(url_for("household.dashboard", household_id=household.id))

        membership = Membership(user_id=g.user.id, household_id=household.id, role="member")
        db.session.add(membership)
        db.session.commit()

        from services.notifications import notify_member_joined
        notify_member_joined(household, new_member=g.user)
        db.session.commit()

        flash(f"You're in. Welcome to {household.name}.", "success")
        return redirect(url_for("household.dashboard", household_id=household.id))

    return render_template("household/join.html")


@household_bp.route("/<int:household_id>")
@login_required
def dashboard(household_id):
    membership = Membership.query.filter_by(
        user_id=g.user.id, household_id=household_id
    ).first()
    if membership is None:
        flash("You're not a member of that household.", "error")
        return redirect(url_for("household.choose"))

    household = membership.household

    # ── Recent expenses ─────────────────────────────────────────────────────
    recent_expenses = (
        Expense.query
        .filter_by(household_id=household_id)
        .order_by(Expense.date.desc(), Expense.created_at.desc())
        .limit(5)
        .all()
    )
    total_expenses = (
        db.session.query(db.func.sum(Expense.amount))
        .filter(Expense.household_id == household_id)
        .scalar() or Decimal("0")
    )

    # ── Category breakdown ───────────────────────────────────────────────────
    cat_rows = (
        db.session.query(Expense.category, db.func.sum(Expense.amount))
        .filter(Expense.household_id == household_id)
        .group_by(Expense.category)
        .order_by(db.func.sum(Expense.amount).desc())
        .all()
    )
    cat_total = sum(float(v) for _, v in cat_rows) or 1
    category_data = [
        {
            "name": cat.capitalize(),
            "amount": float(amt),
            "pct": round(float(amt) / cat_total * 100),
            "icon": CATEGORY_ICONS.get(cat, "📦"),
        }
        for cat, amt in cat_rows[:5]
    ]

    # ── Balances ─────────────────────────────────────────────────────────────
    unsettled_splits = (
        ExpenseSplit.query
        .join(ExpenseSplit.expense)
        .filter_by(household_id=household_id)
        .filter(ExpenseSplit.is_settled == False)
        .all()
    )
    net_balances = compute_net_balances(unsettled_splits)
    my_balance = float(net_balances.get(g.user.id, Decimal("0")))

    # ── Chores summary ───────────────────────────────────────────────────────
    active_chores = (
        Chore.query
        .filter_by(household_id=household_id, is_active=True)
        .all()
    )
    overdue_count = sum(1 for c in active_chores if c.is_overdue)
    due_today_count = sum(1 for c in active_chores if c.is_due_today)

    # ── Shopping summary ─────────────────────────────────────────────────────
    pending_items_count = ShoppingItem.query.filter_by(
        household_id=household_id, is_purchased=False
    ).count()

    # ── This Week panel ──────────────────────────────────────────────────────
    today = date.today()
    week_end = today + timedelta(days=7)

    upcoming_events = (
        Event.query
        .filter_by(household_id=household_id)
        .filter(Event.date.between(today, week_end))
        .order_by(Event.date.asc())
        .all()
    )

    upcoming_chore_events = sorted(
        [c for c in active_chores if today <= c.next_due_date <= week_end],
        key=lambda c: c.next_due_date,
    )

    # ── Open issues ───────────────────────────────────────────────────────────
    open_issues_count = Issue.query.filter_by(
        household_id=household_id
    ).filter(Issue.status != "resolved").count()

    # ── My badges ─────────────────────────────────────────────────────────────
    my_badge_count = UserBadge.query.filter_by(user_id=g.user.id).count()

    return render_template(
        "household/dashboard.html",
        household=household,
        membership=membership,
        memberships=household.memberships,
        recent_expenses=recent_expenses,
        total_expenses=float(total_expenses),
        category_data=category_data,
        my_balance=my_balance,
        expense_count=len(recent_expenses),
        member_count=len(household.memberships),
        category_icons=CATEGORY_ICONS,
        overdue_count=overdue_count,
        due_today_count=due_today_count,
        chore_count=len(active_chores),
        pending_items_count=pending_items_count,
        today=today,
        upcoming_events=upcoming_events,
        upcoming_chore_events=upcoming_chore_events,
        open_issues_count=open_issues_count,
        my_badge_count=my_badge_count,
    )