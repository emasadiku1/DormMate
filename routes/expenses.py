from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Blueprint, render_template, request, redirect, url_for, flash, g

from models import db, Expense, ExpenseSplit, Membership, User
from models.comment import Comment
from utils import login_required, CATEGORY_ICONS

expenses_bp = Blueprint("expenses", __name__)


def _get_household_or_403(household_id):
    """Return the membership if the current user belongs to the household, else None."""
    return Membership.query.filter_by(
        user_id=g.user.id, household_id=household_id
    ).first()


@expenses_bp.route("/household/<int:household_id>/expenses")
@login_required
def list_expenses(household_id):
    membership = _get_household_or_403(household_id)
    if not membership:
        flash("You're not a member of that household.", "error")
        return redirect(url_for("household.choose"))

    household = membership.household
    expenses = (
        Expense.query
        .filter_by(household_id=household_id)
        .order_by(Expense.date.desc(), Expense.created_at.desc())
        .all()
    )
    return render_template(
        "expenses/list.html",
        household=household,
        expenses=expenses,
        membership=membership,
        category_icons=CATEGORY_ICONS,
    )


def _calculate_splits(amount, split_type, members, form):
    """
    Shared split-calculation logic for both creating and editing an expense.
    Returns (split_amounts: dict[user_id, Decimal], errors: list[str]).
    """
    split_amounts: dict[int, Decimal] = {}
    errors: list[str] = []

    if split_type == "equal":
        share = (amount / len(members)).quantize(Decimal("0.01"))
        remainder = amount - share * len(members)
        for i, member in enumerate(members):
            split_amounts[member.id] = share + (remainder if i == 0 else Decimal("0"))

    elif split_type == "percentage":
        total_pct = Decimal("0")
        raw_pcts: dict[int, Decimal] = {}
        for member in members:
            key = f"pct_{member.id}"
            try:
                pct = Decimal(form.get(key, "0")).quantize(Decimal("0.01"))
            except InvalidOperation:
                pct = Decimal("0")
            raw_pcts[member.id] = pct
            total_pct += pct

        if abs(total_pct - Decimal("100")) > Decimal("0.5"):
            errors.append(f"Percentages must add up to 100% (got {total_pct}%).")
        else:
            for member in members:
                split_amounts[member.id] = (raw_pcts[member.id] / 100 * amount).quantize(Decimal("0.01"))
            diff = amount - sum(split_amounts.values())
            if diff:
                first_id = members[0].id
                split_amounts[first_id] += diff

    elif split_type == "custom":
        total_custom = Decimal("0")
        for member in members:
            key = f"custom_{member.id}"
            try:
                val = Decimal(form.get(key, "0")).quantize(Decimal("0.01"))
            except InvalidOperation:
                val = Decimal("0")
            split_amounts[member.id] = val
            total_custom += val

        if abs(total_custom - amount) > Decimal("0.02"):
            errors.append(f"Custom amounts must sum to ${amount} (got ${total_custom}).")

    return split_amounts, errors


@expenses_bp.route("/household/<int:household_id>/expenses/new", methods=["GET", "POST"])
@login_required
def new_expense(household_id):
    membership = _get_household_or_403(household_id)
    if not membership:
        flash("You're not a member of that household.", "error")
        return redirect(url_for("household.choose"))

    household = membership.household
    members = household.members  # list of User objects

    if request.method == "POST":
        errors = []

        # ── Core fields ──────────────────────────────────────────────────────
        try:
            amount = Decimal(request.form.get("amount", "0")).quantize(Decimal("0.01"))
            if amount <= 0:
                errors.append("Amount must be greater than zero.")
        except InvalidOperation:
            errors.append("Enter a valid amount.")
            amount = Decimal("0")

        payer_id = request.form.get("payer_id", type=int)
        if not payer_id or payer_id not in [m.id for m in members]:
            errors.append("Choose a valid payer.")

        category = request.form.get("category", "general")
        if category not in [c[0] for c in Expense.CATEGORIES]:
            category = "general"

        try:
            expense_date = date.fromisoformat(request.form.get("date", ""))
        except ValueError:
            expense_date = date.today()

        note = request.form.get("note", "").strip() or None
        split_type = request.form.get("split_type", "equal")
        if split_type not in Expense.SPLIT_TYPES:
            split_type = "equal"

        # ── Split calculation ─────────────────────────────────────────────────
        split_amounts, split_errors = _calculate_splits(amount, split_type, members, request.form)
        errors.extend(split_errors)

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template(
                "expenses/new.html",
                household=household,
                members=members,
                membership=membership,
                categories=Expense.CATEGORIES,
                today=date.today().isoformat(),
            )

        # ── Persist ───────────────────────────────────────────────────────────
        expense = Expense(
            household_id=household_id,
            payer_id=payer_id,
            amount=amount,
            category=category,
            date=expense_date,
            note=note,
            split_type=split_type,
        )
        db.session.add(expense)
        db.session.flush()  # get expense.id

        for user_id, owed in split_amounts.items():
            split = ExpenseSplit(
                expense_id=expense.id,
                user_id=user_id,
                amount_owed=owed,
            )
            if user_id == payer_id:
                # The payer already covered their own share by paying for
                # the whole expense — no need to make them click "mark paid".
                split.mark_paid()
            db.session.add(split)

        db.session.commit()
        from services.notifications import notify_expense_added
        notify_expense_added(expense, actor=g.user)
        from services.badge_checker import check_and_award
        check_and_award(g.user, "expense_logged")
        db.session.commit()
        flash(f"Expense of ${amount} logged.", "success")
        return redirect(url_for("expenses.list_expenses", household_id=household_id))

    return render_template(
        "expenses/new.html",
        household=household,
        members=members,
        membership=membership,
        categories=Expense.CATEGORIES,
        today=date.today().isoformat(),
    )


@expenses_bp.route("/expenses/<int:expense_id>")
@login_required
def expense_detail(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    membership = _get_household_or_403(expense.household_id)
    if not membership:
        flash("You're not a member of that household.", "error")
        return redirect(url_for("household.choose"))

    comments = expense.comments.all()
    return render_template(
        "expenses/detail.html",
        expense=expense,
        household=expense.household,
        membership=membership,
        comments=comments,
    )

@expenses_bp.route("/household/<int:household_id>/expenses/<int:expense_id>/edit", methods=["GET", "POST"])
@login_required
def edit_expense(household_id, expense_id):
    expense = Expense.query.filter_by(id=expense_id, household_id=household_id).first_or_404()
    membership = _get_household_or_403(household_id)
    if not membership:
        flash("You're not a member of that household.", "error")
        return redirect(url_for("household.choose"))

    # Only the person who paid, or a household admin, can edit an expense.
    if g.user.id != expense.payer_id and not membership.is_admin:
        flash("Only the person who paid, or a household admin, can edit this expense.", "error")
        return redirect(url_for("expenses.expense_detail", expense_id=expense.id))

    household = membership.household
    members = household.members

    if request.method == "POST":
        errors = []

        try:
            amount = Decimal(request.form.get("amount", "0")).quantize(Decimal("0.01"))
            if amount <= 0:
                errors.append("Amount must be greater than zero.")
        except InvalidOperation:
            errors.append("Enter a valid amount.")
            amount = Decimal("0")

        payer_id = request.form.get("payer_id", type=int)
        if not payer_id or payer_id not in [m.id for m in members]:
            errors.append("Choose a valid payer.")

        category = request.form.get("category", "general")
        if category not in [c[0] for c in Expense.CATEGORIES]:
            category = "general"

        try:
            expense_date = date.fromisoformat(request.form.get("date", ""))
        except ValueError:
            expense_date = expense.date

        note = request.form.get("note", "").strip() or None
        split_type = request.form.get("split_type", "equal")
        if split_type not in Expense.SPLIT_TYPES:
            split_type = "equal"

        split_amounts, split_errors = _calculate_splits(amount, split_type, members, request.form)
        errors.extend(split_errors)

        if errors:
            for e in errors:
                flash(e, "error")
            existing_pcts = {}
            existing_customs = {}
            return render_template(
                "expenses/new.html",
                expense=expense,
                household=household,
                members=members,
                membership=membership,
                categories=Expense.CATEGORIES,
                today=date.today().isoformat(),
                existing_pcts=existing_pcts,
                existing_customs=existing_customs,
            )

        # ── Track what actually changed, for the notification ──────────────────
        changes = []
        if amount != expense.amount:
            changes.append(f"amount ${expense.amount:.2f} → ${amount:.2f}")
        if payer_id != expense.payer_id:
            old_payer = next((m for m in members if m.id == expense.payer_id), None)
            new_payer = next((m for m in members if m.id == payer_id), None)
            if old_payer and new_payer:
                changes.append(f"payer {old_payer.name} → {new_payer.name}")
        if category != expense.category:
            changes.append(f"category {expense.category} → {category}")
        if split_type != expense.split_type:
            changes.append(f"split {expense.split_type} → {split_type}")

        # ── Persist ───────────────────────────────────────────────────────────
        expense.amount = amount
        expense.payer_id = payer_id
        expense.category = category
        expense.date = expense_date
        expense.note = note
        expense.split_type = split_type

        # Recalculate splits from scratch — amounts (and who owes what) may
        # have changed, so any prior settlement on the old numbers no longer
        # applies. The payer's own share is auto-settled, same as on create.
        for split in list(expense.splits):
            db.session.delete(split)
        db.session.flush()

        for user_id, owed in split_amounts.items():
            split = ExpenseSplit(
                expense_id=expense.id,
                user_id=user_id,
                amount_owed=owed,
            )
            if user_id == payer_id:
                split.mark_paid()
            db.session.add(split)

        db.session.commit()

        if changes:
            from services.notifications import notify_expense_updated
            notify_expense_updated(expense, actor=g.user, changes=changes)
            db.session.commit()

        flash("Expense updated.", "success")
        return redirect(url_for("expenses.expense_detail", expense_id=expense.id))

    # ── GET: pre-fill percentage/custom panels from the current splits ───────
    existing_pcts = {}
    existing_customs = {}
    if expense.amount and expense.amount > 0:
        for split in expense.splits:
            existing_pcts[split.user_id] = str((split.amount_owed / expense.amount * 100).quantize(Decimal("0.01")))
            existing_customs[split.user_id] = str(split.amount_owed)

    return render_template(
        "expenses/new.html",
        expense=expense,
        household=household,
        members=members,
        membership=membership,
        categories=Expense.CATEGORIES,
        today=date.today().isoformat(),
        existing_pcts=existing_pcts,
        existing_customs=existing_customs,
    )


@expenses_bp.route("/household/<int:household_id>/expenses/<int:expense_id>/delete", methods=["POST"])
@login_required
def delete_expense(household_id, expense_id):
    expense = Expense.query.filter_by(id=expense_id, household_id=household_id).first_or_404()
    membership = _get_household_or_403(household_id)
    if not membership:
        flash("You're not a member of that household.", "error")
        return redirect(url_for("household.choose"))

    if g.user.id != expense.payer_id and not membership.is_admin:
        flash("Only the person who paid, or a household admin, can delete this expense.", "error")
        return redirect(url_for("expenses.expense_detail", expense_id=expense.id))

    household = membership.household
    amount = expense.amount
    category = expense.category

    Comment.query.filter_by(expense_id=expense.id).delete()
    db.session.delete(expense)  # cascades to splits
    db.session.commit()

    from services.notifications import notify_expense_deleted
    notify_expense_deleted(household, actor=g.user, amount=amount, category=category)
    db.session.commit()

    flash("Expense deleted.", "success")
    return redirect(url_for("expenses.list_expenses", household_id=household_id))


@expenses_bp.route("/household/<int:household_id>/expenses/<int:expense_id>/comments", methods=["POST"])
@login_required
def add_comment(household_id, expense_id):
    expense = Expense.query.get_or_404(expense_id)
    membership = _get_household_or_403(expense.household_id)
    if not membership:
        flash("You're not a member of that household.", "error")
        return redirect(url_for("household.choose"))

    body = request.form.get("body", "").strip()
    if not body:
        flash("Comment can't be empty.", "error")
    else:
        comment = Comment(expense_id=expense_id, user_id=g.user.id, body=body)
        db.session.add(comment)
        db.session.commit()

    return redirect(url_for("expenses.expense_detail", expense_id=expense_id))