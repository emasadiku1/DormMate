from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, g

from models import db, Membership
from models.issue import Issue
from utils import login_required

issues_bp = Blueprint("issues", __name__)


@issues_bp.route("/household/<int:household_id>/issues")
@login_required
def list_issues(household_id):
    membership = Membership.query.filter_by(
        user_id=g.user.id, household_id=household_id
    ).first()
    if not membership:
        flash("You're not a member of that household.", "error")
        return redirect(url_for("household.choose"))

    household = membership.household
    status_filter = request.args.get("status", "")

    query = Issue.query.filter_by(household_id=household_id)
    if status_filter in [s[0] for s in Issue.STATUSES]:
        query = query.filter_by(status=status_filter)

    issues = query.order_by(Issue.created_at.desc()).all()

    return render_template(
        "issues/list.html",
        household=household,
        membership=membership,
        issues=issues,
        status_filter=status_filter,
        statuses=Issue.STATUSES,
    )


@issues_bp.route("/household/<int:household_id>/issues/new", methods=["GET", "POST"])
@login_required
def new_issue(household_id):
    membership = Membership.query.filter_by(
        user_id=g.user.id, household_id=household_id
    ).first()
    if not membership:
        flash("You're not a member of that household.", "error")
        return redirect(url_for("household.choose"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip() or None
        if not title:
            flash("Title is required.", "error")
            return redirect(request.url)

        issue = Issue(
            household_id=household_id,
            reported_by_id=g.user.id,
            title=title,
            description=description,
        )
        db.session.add(issue)
        db.session.commit()
        flash("Issue reported.", "success")
        return redirect(url_for("issues.list_issues", household_id=household_id))

    return render_template(
        "issues/new.html",
        household=membership.household,
        membership=membership,
    )


@issues_bp.route("/issues/<int:issue_id>/status", methods=["POST"])
@login_required
def update_status(issue_id):
    issue = Issue.query.get_or_404(issue_id)
    membership = Membership.query.filter_by(
        user_id=g.user.id, household_id=issue.household_id
    ).first()
    if not membership:
        flash("Not a member.", "error")
        return redirect(url_for("household.choose"))

    new_status = request.form.get("status", "")
    if new_status not in [s[0] for s in Issue.STATUSES]:
        flash("Invalid status.", "error")
    else:
        issue.status = new_status
        if new_status == "resolved":
            issue.resolved_at = datetime.utcnow()
        else:
            issue.resolved_at = None
        db.session.commit()
        flash(f"Issue marked as {new_status.replace('_', ' ')}.", "success")

    return redirect(url_for("issues.list_issues", household_id=issue.household_id))
