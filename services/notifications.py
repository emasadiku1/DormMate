"""
services/notifications.py
--------------------------
Central place that creates Notification rows and "sends" emails
(printed to stdout — swap for Flask-Mail when ready).
"""

from __future__ import annotations

import sys
from datetime import datetime, date
from typing import TYPE_CHECKING

from models import db
from models.notification import Notification

if TYPE_CHECKING:
    from models import User, Household, Expense, Chore


# ── Email simulation ──────────────────────────────────────────────────────────

def _send_email(to_email: str, subject: str, body: str) -> None:
    """
    Simulated email sender.
    Replace the body with Flask-Mail calls when you have SMTP configured.
    """
    divider = "─" * 60
    print(f"\n{divider}", file=sys.stdout)
    print(f"📧  SIMULATED EMAIL", file=sys.stdout)
    print(f"  To:      {to_email}", file=sys.stdout)
    print(f"  Subject: {subject}", file=sys.stdout)
    print(f"  Body:\n{body}", file=sys.stdout)
    print(divider, file=sys.stdout)


# ── Internal helper ───────────────────────────────────────────────────────────

def _notify(
    user: "User",
    notif_type: str,
    title: str,
    body: str | None = None,
    link_url: str | None = None,
    household_id: int | None = None,
    send_email: bool = True,
) -> Notification:
    n = Notification(
        user_id=user.id,
        household_id=household_id,
        notif_type=notif_type,
        title=title,
        body=body,
        link_url=link_url,
    )
    db.session.add(n)
    # email is best-effort — don't let it break a transaction
    if send_email:
        try:
            _send_email(
                to_email=user.email,
                subject=f"[DormMate] {title}",
                body=body or title,
            )
        except Exception:
            pass
    return n


# ── Public notification builders ──────────────────────────────────────────────

def notify_expense_added(expense: "Expense", actor: "User") -> None:
    """
    Notify every household member (except the payer) that a new expense was logged.
    """
    from flask import url_for
    household = expense.household
    members = household.members

    for member in members:
        if member.id == actor.id:
            continue  # don't notify the person who added it

        link = None
        try:
            link = url_for("expenses.expense_detail", expense_id=expense.id)
        except RuntimeError:
            pass

        _notify(
            user=member,
            notif_type="expense_added",
            title=f"{actor.name} logged a ${expense.amount:.2f} expense",
            body=(
                f"{actor.name} added a {expense.category} expense of "
                f"${expense.amount:.2f} in '{household.name}'."
                + (f"\nNote: {expense.note}" if expense.note else "")
            ),
            link_url=link,
            household_id=household.id,
        )


def notify_expense_updated(expense: "Expense", actor: "User", changes: list[str] | None = None) -> None:
    """
    Notify every household member (except the editor) that an expense
    they're involved in was edited — amount, payer, category, etc.
    """
    from flask import url_for
    household = expense.household
    members = household.members

    change_summary = f" ({', '.join(changes)})" if changes else ""

    for member in members:
        if member.id == actor.id:
            continue  # don't notify the person who made the edit

        link = None
        try:
            link = url_for("expenses.expense_detail", expense_id=expense.id)
        except RuntimeError:
            pass

        _notify(
            user=member,
            notif_type="expense_updated",
            title=f"{actor.name} edited a ${expense.amount:.2f} expense",
            body=(
                f"{actor.name} updated the {expense.category} expense in "
                f"'{household.name}'{change_summary}."
                + (f"\nNote: {expense.note}" if expense.note else "")
            ),
            link_url=link,
            household_id=household.id,
        )


def notify_expense_deleted(household: "Household", actor: "User", amount, category: str) -> None:
    """
    Notify every household member (except the actor) that an expense was
    removed, since it changes what everyone owes.
    """
    from flask import url_for
    members = household.members

    link = None
    try:
        link = url_for("expenses.list_expenses", household_id=household.id)
    except RuntimeError:
        pass

    for member in members:
        if member.id == actor.id:
            continue

        _notify(
            user=member,
            notif_type="expense_deleted",
            title=f"{actor.name} deleted a ${amount:.2f} expense",
            body=(
                f"{actor.name} removed a {category} expense of ${amount:.2f} "
                f"from '{household.name}'. Balances have been updated."
            ),
            link_url=link,
            household_id=household.id,
        )


def notify_payment_received(split, debtor: "User", creditor: "User", confirmed_by: "User") -> None:
    """
    Tell both sides of a settled split what happened.

    debtor: the person who owed the money (split.user)
    creditor: the person who was owed the money (split.expense.payer)
    confirmed_by: whoever actually clicked "mark paid" — may be either
                  the debtor (confirming they paid) or the creditor
                  (confirming they received payment in cash, etc).
    """
    from flask import url_for
    household_id = split.expense.household_id

    link = None
    try:
        link = url_for("balances.balances", household_id=household_id)
    except RuntimeError:
        pass

    # Notify the creditor (the one owed money) — skip if they're the one
    # who triggered this, since they already know.
    if confirmed_by.id != creditor.id:
        _notify(
            user=creditor,
            notif_type="payment_received",
            title=f"{debtor.name} paid you ${split.amount_owed:.2f}",
            body=(
                f"{debtor.name} marked a payment of ${split.amount_owed:.2f} as settled.\n"
                f"Check your balances page for the full picture."
            ),
            link_url=link,
            household_id=household_id,
        )

    # Notify the debtor (the one who owed money) — skip if they're the one
    # who triggered this.
    if confirmed_by.id != debtor.id:
        _notify(
            user=debtor,
            notif_type="payment_sent",
            title=f"{creditor.name} marked your payment as received",
            body=(
                f"{creditor.name} confirmed your payment of ${split.amount_owed:.2f} "
                f"has been settled."
            ),
            link_url=link,
            household_id=household_id,
            send_email=False,
        )

    # Confirmation for whoever actually clicked the button.
    _notify(
        user=confirmed_by,
        notif_type="payment_sent" if confirmed_by.id == debtor.id else "payment_received",
        title=(
            f"You paid {creditor.name} ${split.amount_owed:.2f}"
            if confirmed_by.id == debtor.id
            else f"You confirmed {debtor.name}'s ${split.amount_owed:.2f} payment"
        ),
        body=(
            f"Your payment of ${split.amount_owed:.2f} to {creditor.name} has been recorded."
            if confirmed_by.id == debtor.id
            else f"You marked {debtor.name}'s payment of ${split.amount_owed:.2f} as received."
        ),
        link_url=link,
        household_id=household_id,
        send_email=False,  # no email for self-confirmation
    )


def notify_chore_due(chore: "Chore", assignee: "User") -> None:
    """Remind the assigned person that a chore is due today."""
    from flask import url_for
    link = None
    try:
        link = url_for("chores.chore_detail",
                       household_id=chore.household_id, chore_id=chore.id)
    except RuntimeError:
        pass

    _notify(
        user=assignee,
        notif_type="chore_due",
        title=f"'{chore.title}' is due today",
        body=(
            f"Don't forget: '{chore.title}' is scheduled for today "
            f"in '{chore.household.name}'."
        ),
        link_url=link,
        household_id=chore.household_id,
    )


def notify_chore_overdue(chore: "Chore", assignee: "User") -> None:
    """Remind the assigned person that a chore is overdue."""
    from flask import url_for
    link = None
    try:
        link = url_for("chores.chore_detail",
                       household_id=chore.household_id, chore_id=chore.id)
    except RuntimeError:
        pass

    _notify(
        user=assignee,
        notif_type="chore_overdue",
        title=f"'{chore.title}' is overdue!",
        body=(
            f"'{chore.title}' was due on {chore.next_due_date.strftime('%b %d')} "
            f"in '{chore.household.name}' and hasn't been completed yet."
        ),
        link_url=link,
        household_id=chore.household_id,
    )


def notify_chore_completed(chore: "Chore", completer: "User") -> None:
    """Notify household members (except the completer) that a chore was done."""
    from flask import url_for
    members = chore.household.members

    link = None
    try:
        link = url_for("chores.list_chores", household_id=chore.household_id)
    except RuntimeError:
        pass

    for member in members:
        if member.id == completer.id:
            continue
        _notify(
            user=member,
            notif_type="chore_completed",
            title=f"{completer.name} completed '{chore.title}'",
            body=f"{completer.name} just marked '{chore.title}' as done.",
            link_url=link,
            household_id=chore.household_id,
            send_email=False,  # chore completions are in-app only
        )


def notify_member_joined(household: "Household", new_member: "User") -> None:
    """Tell existing members that someone new joined."""
    from flask import url_for
    members = household.members

    link = None
    try:
        link = url_for("household.dashboard", household_id=household.id)
    except RuntimeError:
        pass

    for member in members:
        if member.id == new_member.id:
            continue
        _notify(
            user=member,
            notif_type="member_joined",
            title=f"{new_member.name} joined '{household.name}'",
            body=f"{new_member.name} is now a member of your household.",
            link_url=link,
            household_id=household.id,
            send_email=False,
        )