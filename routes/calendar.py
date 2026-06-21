import calendar
from datetime import date, datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, g

from models import db, Membership, Event
from models.chore import Chore
from models.expense import Expense
from utils import login_required

calendar_bp = Blueprint("calendar", __name__)


@calendar_bp.route("/household/<int:household_id>/calendar")
@login_required
def view(household_id):
    membership = Membership.query.filter_by(
        user_id=g.user.id, household_id=household_id
    ).first()
    if not membership:
        flash("You're not a member of that household.", "error")
        return redirect(url_for("household.choose"))

    household = membership.household

    # Which month to show
    today = date.today()
    year = request.args.get("year", today.year, type=int)
    month = request.args.get("month", today.month, type=int)
    if month < 1: month, year = 12, year - 1
    if month > 12: month, year = 1, year + 1

    # Build calendar grid
    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdatescalendar(year, month)

    # ── Gather events for this month ─────────────────────────────────────────
    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])

    # Custom events
    custom_events = (
        Event.query
        .filter_by(household_id=household_id)
        .filter(Event.date.between(first_day, last_day))
        .all()
    )

    # Chores due this month (next_due_date falls in range)
    active_chores = (
        Chore.query
        .filter_by(household_id=household_id, is_active=True)
        .all()
    )
    chore_events = []
    for chore in active_chores:
        due = chore.next_due_date
        if first_day <= due <= last_day:
            chore_events.append({
                "date": due,
                "title": chore.title,
                "type": "chore",
                "id": chore.id,
            })

    # Rent-due events from custom events table (type=rent_due)
    # Already included in custom_events above.

    # Build a dict: date -> list of event dicts
    events_by_date: dict[date, list] = {}

    for ev in custom_events:
        events_by_date.setdefault(ev.date, []).append({
            "title": ev.title,
            "type": ev.type,
            "id": ev.id,
            "obj": ev,
        })

    for ce in chore_events:
        events_by_date.setdefault(ce["date"], []).append(ce)

    # Month navigation
    prev_month = month - 1 or 12
    prev_year = year - 1 if month == 1 else year
    next_month = month % 12 + 1
    next_year = year + 1 if month == 12 else year

    return render_template(
        "calendar/view.html",
        household=household,
        membership=membership,
        weeks=weeks,
        year=year,
        month=month,
        month_name=date(year, month, 1).strftime("%B %Y"),
        today=today,
        events_by_date=events_by_date,
        prev_month=prev_month,
        prev_year=prev_year,
        next_month=next_month,
        next_year=next_year,
    )


@calendar_bp.route("/household/<int:household_id>/calendar/new", methods=["GET", "POST"])
@login_required
def new_event(household_id):
    membership = Membership.query.filter_by(
        user_id=g.user.id, household_id=household_id
    ).first()
    if not membership:
        flash("You're not a member of that household.", "error")
        return redirect(url_for("household.choose"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        event_type = request.form.get("type", "custom")
        try:
            event_date = date.fromisoformat(request.form.get("date", ""))
        except ValueError:
            flash("Invalid date.", "error")
            return redirect(request.url)

        if not title:
            flash("Title is required.", "error")
            return redirect(request.url)

        event = Event(
            household_id=household_id,
            title=title,
            date=event_date,
            type=event_type if event_type in [t[0] for t in Event.TYPES] else "custom",
            created_by_id=g.user.id,
        )
        db.session.add(event)
        db.session.commit()
        flash("Event added.", "success")
        return redirect(url_for("calendar.view", household_id=household_id,
                                year=event_date.year, month=event_date.month))

    return render_template(
        "calendar/new_event.html",
        household=membership.household,
        membership=membership,
        today=date.today().isoformat(),
        event_types=Event.TYPES,
    )


@calendar_bp.route("/household/<int:household_id>/calendar/<int:event_id>/delete", methods=["POST"])
@login_required
def delete_event(household_id, event_id):
    event = Event.query.get_or_404(event_id)
    if event.household_id != household_id:
        flash("Not found.", "error")
        return redirect(url_for("calendar.view", household_id=household_id))
    membership = Membership.query.filter_by(user_id=g.user.id, household_id=household_id).first()
    if not membership:
        flash("Not a member.", "error")
        return redirect(url_for("household.choose"))
    db.session.delete(event)
    db.session.commit()
    flash("Event deleted.", "success")
    return redirect(url_for("calendar.view", household_id=household_id))
