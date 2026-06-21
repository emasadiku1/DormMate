from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g

from models import db, User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if g.user:
        flash(f"You're logged in as {g.user.name}. Log out first to create a new account.", "error")
        return redirect(url_for("household.dashboard_redirect"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        error = None
        if not name or not email or not password:
            error = "Fill in your name, email, and password."
        elif len(password) < 6:
            error = "Password needs to be at least 6 characters."
        elif User.query.filter_by(email=email).first():
            error = "An account with that email already exists."

        if error:
            flash(error, "error")
            return render_template("auth/signup.html", name=name, email=email)

        user = User(name=name, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        session.clear()
        session["user_id"] = user.id
        flash(f"Welcome, {user.name}.", "success")
        return redirect(url_for("household.choose"))

    return render_template("auth/signup.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        flash(f"You're already logged in as {g.user.name}.", "error")
        return redirect(url_for("household.dashboard_redirect"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if user is None or not user.check_password(password):
            flash("Wrong email or password.", "error")
            return render_template("auth/login.html", email=email)

        session.clear()
        session["user_id"] = user.id
        flash(f"Welcome back, {user.name}.", "success")
        return redirect(url_for("household.dashboard_redirect"))

    return render_template("auth/login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "success")
    return redirect(url_for("auth.login"))