from decimal import Decimal

from flask import Blueprint, render_template, flash, redirect, url_for, g

from models import db, ExpenseSplit, Membership, User
from services.debt_calculator import compute_net_balances, simplify_debts
from utils import login_required

balances_bp = Blueprint("balances", __name__)


def _get_membership_or_redirect(household_id):
    membership = Membership.query.filter_by(
        user_id=g.user.id, household_id=household_id
    ).first()
    if not membership:
        flash("You're not a member of that household.", "error")
        return None, redirect(url_for("household.choose"))
    return membership, None


@balances_bp.route("/household/<int:household_id>/balances")
@login_required
def balances(household_id):
    membership, err = _get_membership_or_redirect(household_id)
    if err:
        return err

    household = membership.household

    # All unsettled splits for this household
    unsettled_splits = (
        ExpenseSplit.query
        .join(ExpenseSplit.expense)
        .filter_by(household_id=household_id)
        .filter(ExpenseSplit.is_settled == False)
        .all()
    )

    net_balances = compute_net_balances(unsettled_splits)

    # Build a human-readable pairwise balance table:
    # {(ower_id, owed_id): amount} — who owes whom how much (before simplification)
    pairwise: dict[tuple[int, int], Decimal] = {}
    for split in unsettled_splits:
        payer_id = split.expense.payer_id
        ower_id  = split.user_id
        if payer_id == ower_id:
            continue
        key = (ower_id, payer_id)
        pairwise[key] = pairwise.get(key, Decimal("0")) + Decimal(str(split.amount_owed))

    # Resolve user objects once
    member_ids = {m.user_id for m in household.memberships}
    users_by_id: dict[int, User] = {
        u.id: u for u in User.query.filter(User.id.in_(member_ids)).all()
    }

    # Net balance per member (positive = owed money, negative = owes money)
    net_display = {
        users_by_id[uid]: float(bal)
        for uid, bal in net_balances.items()
        if uid in users_by_id
    }

    return render_template(
        "balances/balances.html",
        household=household,
        membership=membership,
        net_display=net_display,
        users_by_id=users_by_id,
    )