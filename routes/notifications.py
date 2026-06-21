from flask import Blueprint, render_template, redirect, url_for, request, jsonify, g, flash

from models import db
from models.notification import Notification
from utils import login_required

notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.route("/notifications")
@login_required
def feed():
    page = request.args.get("page", 1, type=int)
    filter_type = request.args.get("type", "all")

    query = (
        Notification.query
        .filter_by(user_id=g.user.id)
        .order_by(Notification.created_at.desc())
    )

    if filter_type == "expense_added":
        # The "Expenses" tab covers all expense lifecycle events, not just
        # newly logged ones.
        query = query.filter(Notification.notif_type.in_(
            ["expense_added", "expense_updated", "expense_deleted"]
        ))
    elif filter_type != "all":
        query = query.filter_by(notif_type=filter_type)

    notifications = query.paginate(page=page, per_page=20, error_out=False)

    unread_count = (
        Notification.query
        .filter_by(user_id=g.user.id, is_read=False)
        .count()
    )

    return render_template(
        "notifications/feed.html",
        notifications=notifications,
        unread_count=unread_count,
        filter_type=filter_type,
    )


@notifications_bp.route("/notifications/<int:notif_id>/read", methods=["POST"])
@login_required
def mark_read(notif_id):
    n = Notification.query.filter_by(id=notif_id, user_id=g.user.id).first_or_404()
    n.mark_read()
    db.session.commit()

    # If it has a deep-link, redirect there; otherwise back to feed
    next_url = n.link_url or url_for("notifications.feed")
    return redirect(next_url)


@notifications_bp.route("/notifications/mark-all-read", methods=["POST"])
@login_required
def mark_all_read():
    (
        Notification.query
        .filter_by(user_id=g.user.id, is_read=False)
        .update({"is_read": True})
    )
    db.session.commit()
    flash("All notifications marked as read.", "success")
    return redirect(url_for("notifications.feed"))


@notifications_bp.route("/notifications/count")
@login_required
def unread_count():
    """JSON endpoint for the nav badge — poll this with JS."""
    count = (
        Notification.query
        .filter_by(user_id=g.user.id, is_read=False)
        .count()
    )
    return jsonify({"unread": count})
