"""
DormMate — entry point.
"""

from flask import Flask, render_template, session, g

from config import Config
from models import db, User


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    @app.before_request
    def load_logged_in_user():
        user_id = session.get("user_id")
        g.user = User.query.get(user_id) if user_id else None

    @app.context_processor
    def inject_user():
        return {"current_user": g.get("user")}

    @app.route("/")
    def index():
        return render_template("index.html")

    from routes.auth import auth_bp
    from routes.household import household_bp
    from routes.expenses import expenses_bp
    from routes.balances import balances_bp
    from routes.settle import settle_bp
    from routes.chores import chores_bp
    from routes.shopping import shopping_bp
    from routes.notifications import notifications_bp
    from routes.reports import reports_bp
    from routes.calendar import calendar_bp
    from routes.stats import stats_bp
    from routes.house_rules import house_rules_bp
    from routes.issues import issues_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(household_bp)
    app.register_blueprint(expenses_bp)
    app.register_blueprint(balances_bp)
    app.register_blueprint(settle_bp)
    app.register_blueprint(chores_bp)
    app.register_blueprint(shopping_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(calendar_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(house_rules_bp)
    app.register_blueprint(issues_bp)

    @app.after_request
    def add_no_cache_headers(response):
        # Prevent the browser (and back/forward cache) from showing a stale
        # rendered page — e.g. an old expense-form error bleeding onto a
        # later visit to a different page after hitting "back".
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        return response

    @app.context_processor
    def inject_notif_count():
        from models.notification import Notification
        count = 0
        if g.get("user"):
            count = Notification.query.filter_by(
                user_id=g.user.id, is_read=False
            ).count()
        return {"notif_unread_count": count}

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)