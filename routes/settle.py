from decimal import Decimal

from flask import Blueprint, render_template, redirect, url_for, flash, request, g

from models import db, ExpenseSplit, Membership, User
from utils import login_required

settle_bp = Blueprint("settle", __name__)


def _get_membership_or_redirect(household_id):
    membership = Membership.query.filter_by(
        user_id=g.user.id, household_id=household_id
    ).first()
    if not membership:
        flash("You're not a member of that household.", "error")
        return None, redirect(url_for("household.choose"))
    return membership, None


@settle_bp.route("/household/<int:household_id>/settle")
@login_required
def settle(household_id):
    membership, err = _get_membership_or_redirect(household_id)
    if err:
        return err

    household = membership.household

    unsettled_splits = (
        ExpenseSplit.query
        .join(ExpenseSplit.expense)
        .filter_by(household_id=household_id)
        .filter(ExpenseSplit.is_settled == False)
        .all()
    )

    # Net balance per *other person*, from the current user's point of view
    # only. Positive = that person owes the current user; negative = the
    # current user owes that person. This never routes a debt through a
    # third party — only direct splits between the viewer and someone else
    # count, so what you see is exactly what you owe or are owed.
    net_with: dict[int, Decimal] = {}

    for split in unsettled_splits:
        payer_id = split.expense.payer_id
        ower_id = split.user_id
        amount = Decimal(str(split.amount_owed))

        if payer_id == ower_id:
            continue  # paid your own share — nothing to settle

        if payer_id == g.user.id:
            # Someone else owes the current user.
            net_with[ower_id] = net_with.get(ower_id, Decimal("0")) + amount
        elif ower_id == g.user.id:
            # The current user owes someone else.
            net_with[payer_id] = net_with.get(payer_id, Decimal("0")) - amount

    EPSILON = Decimal("0.01")
    member_ids = {m.user_id for m in household.memberships}
    users_by_id: dict[int, User] = {
        u.id: u for u in User.query.filter(User.id.in_(member_ids)).all()
    }

    rich_transactions = []
    for other_id, balance in net_with.items():
        if abs(balance) < EPSILON or other_id not in users_by_id:
            continue
        other = users_by_id[other_id]
        if balance > 0:
            # They owe the current user.
            rich_transactions.append({
                "debtor": other,
                "creditor": g.user,
                "amount": balance.quantize(Decimal("0.01")),
            })
        else:
            # The current user owes them.
            rich_transactions.append({
                "debtor": g.user,
                "creditor": other,
                "amount": (-balance).quantize(Decimal("0.01")),
            })

    rich_transactions.sort(key=lambda t: t["amount"], reverse=True)

    return render_template(
        "balances/settle.html",
        household=household,
        membership=membership,
        transactions=rich_transactions,
        all_settled=(len(rich_transactions) == 0),
    )


@settle_bp.route("/splits/<int:split_id>/mark-paid", methods=["POST"])
@login_required
def mark_paid(split_id):
    split = ExpenseSplit.query.get_or_404(split_id)
    household_id = split.expense.household_id

    # Verify membership
    membership = Membership.query.filter_by(
        user_id=g.user.id, household_id=household_id
    ).first()
    if not membership:
        flash("You're not a member of that household.", "error")
        return redirect(url_for("household.choose"))

    # Only the person who owes this split (the debtor) or the person who's
    # owed it (the creditor/payer) may mark it as settled — not just any
    # member of the household.
    creditor_id = split.expense.payer_id
    debtor_id = split.user_id
    if g.user.id not in (creditor_id, debtor_id):
        flash("Only the people involved in this split can mark it as paid.", "error")
        next_url = request.form.get("next") or url_for("settle.settle", household_id=household_id)
        return redirect(next_url)

    if split.is_settled:
        flash("That split is already marked as paid.", "error")
    else:
        creditor = split.expense.payer
        debtor = split.user
        split.mark_paid()
        db.session.commit()
        if creditor.id != debtor.id:
            # Only notify when this is a real payment between two different
            # people — settling your own share isn't a payment to anyone.
            from services.notifications import notify_payment_received
            notify_payment_received(split, debtor=debtor, creditor=creditor, confirmed_by=g.user)
        from services.badge_checker import check_and_award
        check_and_award(debtor, "split_settled")
        db.session.commit()
        flash(f"Payment of ${split.amount_owed} marked as settled.", "success")
    # Return to wherever the user came from (settle page or expense detail)
    next_url = request.form.get("next") or url_for("settle.settle", household_id=household_id)
    return redirect(next_url)

@settle_bp.route("/household/<int:household_id>/settle/mark-all-paid", methods=["POST"])
@login_required
def mark_all_paid(household_id):
    membership, err = _get_membership_or_redirect(household_id)
    if err:
        return err

    unsettled = (
        ExpenseSplit.query
        .join(ExpenseSplit.expense)
        .filter_by(household_id=household_id)
        .filter(ExpenseSplit.is_settled == False)
        .all()
    )

    # Only settle splits where the current user is the debtor or the
    # creditor — not other people's unrelated debts.
    my_unsettled = [
        s for s in unsettled
        if g.user.id in (s.user_id, s.expense.payer_id)
    ]

    for split in my_unsettled:
        split.mark_paid()

    db.session.commit()

    from services.badge_checker import check_and_award
    debtors = {split.user_id: split.user for split in my_unsettled}
    for debtor in debtors.values():
        check_and_award(debtor, "split_settled")
    db.session.commit()

    flash(f"Marked {len(my_unsettled)} split(s) as settled.", "success")
    return redirect(url_for("settle.settle", household_id=household_id))