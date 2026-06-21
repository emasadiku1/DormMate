from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, g

from models import db, Membership
from models.house_rule import HouseRule
from utils import login_required

house_rules_bp = Blueprint("house_rules", __name__)


@house_rules_bp.route("/household/<int:household_id>/rules")
@login_required
def view(household_id):
    membership = Membership.query.filter_by(
        user_id=g.user.id, household_id=household_id
    ).first()
    if not membership:
        flash("You're not a member of that household.", "error")
        return redirect(url_for("household.choose"))

    household = membership.household
    rule = HouseRule.query.filter_by(household_id=household_id).first()

    return render_template(
        "house_rules/view.html",
        household=household,
        membership=membership,
        rule=rule,
    )


@house_rules_bp.route("/household/<int:household_id>/rules/edit", methods=["GET", "POST"])
@login_required
def edit(household_id):
    membership = Membership.query.filter_by(
        user_id=g.user.id, household_id=household_id
    ).first()
    if not membership:
        flash("You're not a member of that household.", "error")
        return redirect(url_for("household.choose"))

    if not membership.is_admin:
        flash("Only admins can edit house rules.", "error")
        return redirect(url_for("house_rules.view", household_id=household_id))

    household = membership.household
    rule = HouseRule.query.filter_by(household_id=household_id).first()

    if request.method == "POST":
        content = request.form.get("content", "").strip()
        if rule is None:
            rule = HouseRule(household_id=household_id)
            db.session.add(rule)
        rule.content = content
        rule.updated_by_id = g.user.id
        rule.updated_at = datetime.utcnow()
        db.session.commit()
        flash("House rules updated.", "success")
        return redirect(url_for("house_rules.view", household_id=household_id))

    return render_template(
        "house_rules/edit.html",
        household=household,
        membership=membership,
        rule=rule,
    )
