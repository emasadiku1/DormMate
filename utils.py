from functools import wraps

from flask import g, flash, redirect, url_for


CATEGORY_ICONS = {
    "groceries": "🛒",
    "utilities": "💡",
    "rent": "🏠",
    "cleaning": "🧹",
    "takeout": "🍕",
    "transport": "🚌",
    "entertainment": "🎬",
    "general": "📦",
}


def login_required(view):
    """Redirect to the login page if no user is loaded onto g for this request."""

    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.get("user") is None:
            flash("Log in to continue.", "error")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped_view