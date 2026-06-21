from flask import Blueprint, render_template, request, redirect, url_for, flash, g

from models import db, ShoppingItem, Expense, Membership
from utils import login_required

shopping_bp = Blueprint("shopping", __name__)


def _get_membership(household_id):
    m = Membership.query.filter_by(user_id=g.user.id, household_id=household_id).first()
    if not m:
        flash("You're not a member of that household.", "error")
    return m


@shopping_bp.route("/household/<int:household_id>/shopping")
@login_required
def shopping_list(household_id):
    membership = _get_membership(household_id)
    if not membership:
        return redirect(url_for("household.choose"))

    household = membership.household

    pending = (
        ShoppingItem.query
        .filter_by(household_id=household_id, is_purchased=False)
        .order_by(ShoppingItem.created_at.asc())
        .all()
    )
    purchased = (
        ShoppingItem.query
        .filter_by(household_id=household_id, is_purchased=True)
        .order_by(ShoppingItem.purchased_at.desc())
        .limit(20)
        .all()
    )

    # Expenses available to link (most recent 20)
    linkable_expenses = (
        Expense.query
        .filter_by(household_id=household_id)
        .order_by(Expense.date.desc())
        .limit(20)
        .all()
    )

    return render_template(
        "shopping/list.html",
        household=household,
        membership=membership,
        pending=pending,
        purchased=purchased,
        linkable_expenses=linkable_expenses,
    )


@shopping_bp.route("/household/<int:household_id>/shopping/add", methods=["POST"])
@login_required
def add_item(household_id):
    membership = _get_membership(household_id)
    if not membership:
        return redirect(url_for("household.choose"))

    title = request.form.get("title", "").strip()
    if not title:
        flash("Item needs a name.", "error")
        return redirect(url_for("shopping.shopping_list", household_id=household_id))

    try:
        quantity = max(1, int(request.form.get("quantity", 1)))
    except (ValueError, TypeError):
        quantity = 1

    note = request.form.get("note", "").strip() or None

    item = ShoppingItem(
        household_id=household_id,
        added_by=g.user.id,
        title=title,
        quantity=quantity,
        note=note,
    )
    db.session.add(item)
    db.session.commit()

    flash(f"'{title}' added to the list.", "success")
    return redirect(url_for("shopping.shopping_list", household_id=household_id))


@shopping_bp.route("/household/<int:household_id>/shopping/<int:item_id>/purchase", methods=["POST"])
@login_required
def mark_purchased(household_id, item_id):
    membership = _get_membership(household_id)
    if not membership:
        return redirect(url_for("household.choose"))

    item = ShoppingItem.query.filter_by(id=item_id, household_id=household_id).first_or_404()

    if item.is_purchased:
        item.unmark_purchased()
        db.session.commit()
        flash(f"'{item.title}' moved back to the list.", "success")
    else:
        item.mark_purchased(g.user.id)

        # Optionally link to an expense
        expense_id = request.form.get("expense_id", type=int)
        if expense_id:
            expense = Expense.query.filter_by(id=expense_id, household_id=household_id).first()
            if expense:
                item.expense_id = expense.id

        db.session.commit()
        flash(f"'{item.title}' marked as purchased.", "success")

    return redirect(url_for("shopping.shopping_list", household_id=household_id))


@shopping_bp.route("/household/<int:household_id>/shopping/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_item(household_id, item_id):
    membership = _get_membership(household_id)
    if not membership:
        return redirect(url_for("household.choose"))

    item = ShoppingItem.query.filter_by(id=item_id, household_id=household_id).first_or_404()
    db.session.delete(item)
    db.session.commit()

    flash(f"'{item.title}' removed.", "success")
    return redirect(url_for("shopping.shopping_list", household_id=household_id))


@shopping_bp.route("/household/<int:household_id>/shopping/clear-purchased", methods=["POST"])
@login_required
def clear_purchased(household_id):
    membership = _get_membership(household_id)
    if not membership:
        return redirect(url_for("household.choose"))

    ShoppingItem.query.filter_by(
        household_id=household_id, is_purchased=True
    ).delete()
    db.session.commit()

    flash("Purchased items cleared.", "success")
    return redirect(url_for("shopping.shopping_list", household_id=household_id))