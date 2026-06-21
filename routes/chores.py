from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, g

from models import db, Chore, ChoreCompletion, Membership
from utils import login_required

chores_bp = Blueprint("chores", __name__)


def _get_membership(household_id):
    m = Membership.query.filter_by(user_id=g.user.id, household_id=household_id).first()
    if not m:
        flash("You're not a member of that household.", "error")
    return m


@chores_bp.route("/household/<int:household_id>/chores")
@login_required
def list_chores(household_id):
    membership = _get_membership(household_id)
    if not membership:
        return redirect(url_for("household.choose"))

    household = membership.household
    members = household.members

    chores = (
        Chore.query
        .filter_by(household_id=household_id, is_active=True)
        .order_by(Chore.created_at.asc())
        .all()
    )

    # Annotate each chore with its current assignee
    for chore in chores:
        chore._current_assignee = chore.get_current_assignee(members)

    overdue = [c for c in chores if c.is_overdue]
    due_today = [c for c in chores if c.is_due_today]
    upcoming = [c for c in chores if not c.is_overdue and not c.is_due_today]

    return render_template(
        "chores/list.html",
        household=household,
        membership=membership,
        overdue=overdue,
        due_today=due_today,
        upcoming=upcoming,
        all_chores=chores,
    )


@chores_bp.route("/household/<int:household_id>/chores/new", methods=["GET", "POST"])
@login_required
def new_chore(household_id):
    membership = _get_membership(household_id)
    if not membership:
        return redirect(url_for("household.choose"))

    household = membership.household
    members = household.members

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Give the chore a title.", "error")
            return render_template("chores/new.html", household=household,
                                   members=members, membership=membership)

        description = request.form.get("description", "").strip() or None
        frequency = request.form.get("frequency", "weekly")
        if frequency not in dict(Chore.FREQUENCIES):
            frequency = "weekly"

        custom_days = None
        if frequency == "custom":
            try:
                custom_days = int(request.form.get("custom_interval_days", 7))
                if custom_days < 1:
                    custom_days = 1
            except (ValueError, TypeError):
                custom_days = 7

        rotation_mode = request.form.get("rotation_mode") == "rotate"
        assigned_to = None

        if not rotation_mode:
            try:
                assigned_to = int(request.form.get("assigned_to", 0))
                if assigned_to not in [m.id for m in members]:
                    assigned_to = g.user.id
            except (ValueError, TypeError):
                assigned_to = g.user.id

        chore = Chore(
            household_id=household_id,
            created_by=g.user.id,
            title=title,
            description=description,
            frequency=frequency,
            custom_interval_days=custom_days,
            rotation_mode=rotation_mode,
            assigned_to=assigned_to,
        )
        db.session.add(chore)
        db.session.commit()

        flash(f"'{title}' added to the chore list.", "success")
        return redirect(url_for("chores.list_chores", household_id=household_id))

    return render_template(
        "chores/new.html",
        household=household,
        members=members,
        membership=membership,
    )


@chores_bp.route("/household/<int:household_id>/chores/<int:chore_id>")
@login_required
def chore_detail(household_id, chore_id):
    membership = _get_membership(household_id)
    if not membership:
        return redirect(url_for("household.choose"))

    chore = Chore.query.filter_by(id=chore_id, household_id=household_id).first_or_404()
    members = membership.household.members
    current_assignee = chore.get_current_assignee(members)

    return render_template(
        "chores/detail.html",
        household=membership.household,
        membership=membership,
        chore=chore,
        current_assignee=current_assignee,
        members=members,
    )


@chores_bp.route("/household/<int:household_id>/chores/<int:chore_id>/complete", methods=["POST"])
@login_required
def complete_chore(household_id, chore_id):
    membership = _get_membership(household_id)
    if not membership:
        return redirect(url_for("household.choose"))

    chore = Chore.query.filter_by(id=chore_id, household_id=household_id).first_or_404()
    members = membership.household.members

    note = request.form.get("note", "").strip() or None

    completion = ChoreCompletion(
        chore_id=chore.id,
        completed_by=g.user.id,
        note=note,
    )
    db.session.add(completion)

    chore.last_completed_at = datetime.utcnow()
    chore.advance_rotation(members)
    db.session.commit()

    from services.notifications import notify_chore_completed
    notify_chore_completed(chore, completer=g.user)
    from services.badge_checker import check_and_award
    check_and_award(g.user, "chore_completed")
    db.session.commit()

    flash(f"'{chore.title}' marked as done. Next due {chore.next_due_date.strftime('%b %d')}.", "success")

    next_url = request.form.get("next") or url_for("chores.list_chores", household_id=household_id)
    return redirect(next_url)


@chores_bp.route("/household/<int:household_id>/chores/<int:chore_id>/delete", methods=["POST"])
@login_required
def delete_chore(household_id, chore_id):
    membership = _get_membership(household_id)
    if not membership:
        return redirect(url_for("household.choose"))

    chore = Chore.query.filter_by(id=chore_id, household_id=household_id).first_or_404()
    chore.is_active = False  # soft delete
    db.session.commit()

    flash(f"'{chore.title}' removed.", "success")
    return redirect(url_for("chores.list_chores", household_id=household_id))