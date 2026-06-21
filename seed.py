# -*- coding: utf-8 -*-
"""
seed.py — populates DormMate with realistic demo data.

Keeps the existing real account (Ema / "TourLingo Tirana") intact and:
  1. Adds 2 roommates to that household (3 members total).
  2. Creates a second, fully separate household with 3 fresh members.
  3. Fills both households with ~2-3 weeks of chores, expenses, splits,
     shopping items, issues, calendar events, house rules, notifications,
     and badges.

Safe to re-run: it checks for existing seed markers and skips households
it already created (it will NOT duplicate data on a second run).

Usage:
    python seed.py
"""

from datetime import datetime, date, timedelta
from decimal import Decimal

from app import create_app
from models import (
    db, User, Household, Membership, Chore, ChoreCompletion,
    Expense, ExpenseSplit, ShoppingItem, Issue, Comment, Event,
    HouseRule, Notification, Badge, UserBadge,
)
from services.badge_checker import check_and_award

app = create_app()

DEMO_PASSWORD = "dormmate123"
TODAY = date.today()


def days_ago(n):
    return TODAY - timedelta(days=n)


def dt_days_ago(n, hour=12, minute=0):
    return datetime.combine(days_ago(n), datetime.min.time()) + timedelta(hours=hour, minutes=minute)


def get_or_create_user(name, email, room_number=None):
    user = User.query.filter_by(email=email).first()
    if user:
        return user, False
    user = User(name=name, email=email, room_number=room_number)
    user.set_password(DEMO_PASSWORD)
    db.session.add(user)
    db.session.flush()
    return user, True


def add_notification(user, household, notif_type, title, body, is_read, created_at, link_url=None):
    n = Notification(
        user_id=user.id,
        household_id=household.id,
        notif_type=notif_type,
        title=title,
        body=body,
        link_url=link_url,
        is_read=is_read,
        created_at=created_at,
    )
    db.session.add(n)
    return n


def seed_chores(household, members, chore_specs):
    """
    chore_specs: list of dicts describing each chore + completion history.
    Returns list of created Chore objects.
    """
    created = []
    for spec in chore_specs:
        chore = Chore(
            household_id=household.id,
            created_by=spec["created_by"].id,
            title=spec["title"],
            description=spec.get("description"),
            frequency=spec["frequency"],
            custom_interval_days=spec.get("custom_interval_days"),
            rotation_mode=spec["rotation_mode"],
            assigned_to=spec.get("assigned_to").id if spec.get("assigned_to") else None,
            rotation_index=spec.get("rotation_index", 0),
            created_at=spec["created_at"],
        )
        db.session.add(chore)
        db.session.flush()

        last_completed = None
        for comp in spec.get("completions", []):
            completion = ChoreCompletion(
                chore_id=chore.id,
                completed_by=comp["user"].id,
                completed_at=comp["completed_at"],
                note=comp.get("note"),
            )
            db.session.add(completion)
            last_completed = comp["completed_at"]
            chore.advance_rotation(members)

        if last_completed:
            chore.last_completed_at = last_completed

        created.append(chore)

        for comp in spec.get("completions", []):
            db.session.flush()
            for member in members:
                if member.id == comp["user"].id:
                    continue
                add_notification(
                    member, household, "chore_completed",
                    f"{comp['user'].name} completed '{chore.title}'",
                    f"{comp['user'].name} just marked '{chore.title}' as done.",
                    is_read=True,
                    created_at=comp["completed_at"],
                )
            check_and_award(comp["user"], "chore_completed")

    return created


def seed_expense(household, members, payer, amount, category, exp_date, note,
                  split_type, splits, settled_user_ids=None, created_at=None):
    """splits: dict {user: Decimal owed}. settled_user_ids: set of user ids already settled."""
    settled_user_ids = settled_user_ids or set()
    expense = Expense(
        household_id=household.id,
        payer_id=payer.id,
        amount=Decimal(str(amount)),
        category=category,
        date=exp_date,
        note=note,
        split_type=split_type,
        created_at=created_at or datetime.combine(exp_date, datetime.min.time()),
    )
    db.session.add(expense)
    db.session.flush()

    for user, owed in splits.items():
        split = ExpenseSplit(
            expense_id=expense.id,
            user_id=user.id,
            amount_owed=Decimal(str(owed)),
            is_settled=user.id in settled_user_ids or user.id == payer.id,
        )
        if user.id in settled_user_ids or user.id == payer.id:
            split.settled_at = expense.created_at + timedelta(days=2)
        db.session.add(split)

    db.session.flush()

    # Notifications for everyone except the payer
    for member in members:
        if member.id == payer.id:
            continue
        add_notification(
            member, household, "expense_added",
            f"{payer.name} logged a ${amount:.2f} expense",
            f"{payer.name} added a {category} expense of ${amount:.2f} in '{household.name}'."
            + (f"\nNote: {note}" if note else ""),
            is_read=True,
            created_at=expense.created_at,
        )

    # Settlement notifications for whoever already paid up
    for user_id in settled_user_ids:
        if user_id == payer.id:
            continue
        settler = next(m for m in members if m.id == user_id)
        owed = splits[settler]
        settled_dt = expense.created_at + timedelta(days=2)
        add_notification(
            payer, household, "payment_received",
            f"{settler.name} paid you ${owed:.2f}",
            f"{settler.name} marked a payment of ${owed:.2f} as settled.",
            is_read=True,
            created_at=settled_dt,
        )
        add_notification(
            settler, household, "payment_sent",
            f"You paid {payer.name} ${owed:.2f}",
            f"Your payment of ${owed:.2f} to {payer.name} has been recorded.",
            is_read=True,
            created_at=settled_dt,
        )
        check_and_award(settler, "split_settled")

    check_and_award(payer, "expense_logged")
    return expense


def seed_household_block(label, household, members, admin):
    """Populate one household with chores/expenses/shopping/issues/events/rules."""

    # ---- House rules ----
    if not household.house_rule:
        rule = HouseRule(
            household_id=household.id,
            content=(
                "1. Respect quiet hours after 23:00.\n"
                "2. Clean shared dishes within the same day.\n"
                "3. Label your food in the fridge.\n"
                "4. Split all shared bills evenly unless agreed otherwise.\n"
                "5. Guests must be cleared with the group chat in advance."
            ),
            updated_by_id=admin.id,
            updated_at=dt_days_ago(10),
        )
        db.session.add(rule)

    # ---- Chores ----
    m0, m1, m2 = members[0], members[1], members[2]
    chore_specs = [
        {
            "title": "Pastrim kuzhine",
            "description": "Wipe counters, do dishes, take out kitchen trash.",
            "frequency": "weekly",
            "rotation_mode": True,
            "created_by": admin,
            "created_at": dt_days_ago(20),
            "rotation_index": 0,
            "completions": [
                {"user": m0, "completed_at": dt_days_ago(14, 18, 30)},
                {"user": m1, "completed_at": dt_days_ago(7, 19, 0)},
            ],
        },
        {
            "title": "Hedhja e plehrave",
            "description": "Take the trash and recycling down to the bins.",
            "frequency": "daily",
            "rotation_mode": True,
            "created_by": admin,
            "created_at": dt_days_ago(20),
            "rotation_index": 0,
            "completions": [
                {"user": m1, "completed_at": dt_days_ago(3, 21, 0)},
                {"user": m2, "completed_at": dt_days_ago(2, 21, 15)},
                {"user": m0, "completed_at": dt_days_ago(1, 20, 45)},
            ],
        },
        {
            "title": "Pastrim banjo",
            "description": "Scrub the bathroom — sink, toilet, shower.",
            "frequency": "biweekly",
            "rotation_mode": False,
            "assigned_to": m2,
            "created_by": admin,
            "created_at": dt_days_ago(20),
            "completions": [
                {"user": m2, "completed_at": dt_days_ago(13, 17, 0)},
                # no recent completion -> currently overdue, good for testing alerts
            ],
        },
        {
            "title": "Larje rrobash banje/kuzhine",
            "description": "Wash shared towels and kitchen cloths.",
            "frequency": "monthly",
            "rotation_mode": False,
            "assigned_to": m0,
            "created_by": m0,
            "created_at": dt_days_ago(18),
            "completions": [
                {"user": m0, "completed_at": dt_days_ago(12, 16, 0)},
            ],
        },
    ]
    seed_chores(household, members, chore_specs)

    # ---- Expenses + splits ----
    def equal_split(amount, payer_settled_too=False):
        share = (Decimal(str(amount)) / 3).quantize(Decimal("0.01"))
        remainder = Decimal(str(amount)) - share * 3
        return {
            m0: share + remainder,
            m1: share,
            m2: share,
        }

    # Rent — paid by admin, everyone settled (rent always gets paid)
    seed_expense(
        household, members, admin, 450.00, "rent", days_ago(15),
        "Monthly rent split", "equal",
        equal_split(450.00),
        settled_user_ids={m.id for m in members},
        created_at=dt_days_ago(15, 9, 0),
    )

    # Electricity — paid by m1, two settled, one still owing
    seed_expense(
        household, members, m1, 42.30, "utilities", days_ago(12),
        "ECC electricity bill", "equal",
        equal_split(42.30),
        settled_user_ids={admin.id},
        created_at=dt_days_ago(12, 19, 0),
    )

    # Groceries — paid by m2, custom split (m1 didn't take any)
    groceries_total = 36.80
    seed_expense(
        household, members, m2, groceries_total, "groceries", days_ago(10),
        "Big supermarket run", "custom",
        {m0: Decimal("13.40"), m1: Decimal("0.00"), m2: Decimal("23.40")},
        settled_user_ids={m0.id},
        created_at=dt_days_ago(10, 18, 0),
    )

    # Internet — paid by admin, equal, nobody settled yet (fresh)
    seed_expense(
        household, members, admin, 25.00, "utilities", days_ago(6),
        "Monthly internet", "equal",
        equal_split(25.00),
        settled_user_ids=set(),
        created_at=dt_days_ago(6, 10, 0),
    )

    # Takeout — paid by m0, equal
    seed_expense(
        household, members, m0, 19.50, "takeout", days_ago(4),
        "Friday night pizza", "equal",
        equal_split(19.50),
        settled_user_ids={m2.id},
        created_at=dt_days_ago(4, 21, 30),
    )

    # Cleaning supplies — paid by m1, equal, recent
    seed_expense(
        household, members, m1, 11.20, "cleaning", days_ago(2),
        "Detergent + sponges", "equal",
        equal_split(11.20),
        settled_user_ids=set(),
        created_at=dt_days_ago(2, 17, 0),
    )

    # ---- Shopping list ----
    shopping_specs = [
        ("Qumësht", 2, m0, True, m1, days_ago(9)),
        ("Vezë", 1, m0, True, m0, days_ago(9)),
        ("Letër higjienike", 4, m1, True, m2, days_ago(7)),
        ("Detergjent pjatash", 1, m2, False, None, None),
        ("Kafe", 1, m0, False, None, None),
        ("Fruta", 3, m1, False, None, None),
    ]
    for title, qty, adder, purchased, buyer, p_date in shopping_specs:
        item = ShoppingItem(
            household_id=household.id,
            added_by=adder.id,
            title=title,
            quantity=qty,
            is_purchased=purchased,
            purchased_by=buyer.id if purchased else None,
            purchased_at=dt_days_ago((TODAY - p_date).days) if purchased else None,
            created_at=dt_days_ago((TODAY - p_date).days + 1) if purchased else dt_days_ago(5),
        )
        db.session.add(item)

    # ---- Issues ----
    issue_specs = [
        ("Çelësi i derës së ballkonit nuk kyçet", "Balcony door lock is stuck, need a locksmith.",
         "open", m1, days_ago(5), None),
        ("Rrjedhje uji nën lavaman", "Small leak under the kitchen sink, getting worse.",
         "in_progress", m2, days_ago(8), None),
        ("Wifi-ja bie shpesh mbrëma", "Router keeps dropping connection around 9-10pm.",
         "resolved", m0, days_ago(16), days_ago(13)),
    ]
    for title, desc, status, reporter, created, resolved in issue_specs:
        issue = Issue(
            household_id=household.id,
            reported_by_id=reporter.id,
            title=title,
            description=desc,
            status=status,
            created_at=dt_days_ago((TODAY - created).days),
            resolved_at=dt_days_ago((TODAY - resolved).days) if resolved else None,
        )
        db.session.add(issue)

    # ---- Calendar events ----
    event_specs = [
        ("Pagesa e qerasë", TODAY + timedelta(days=15), "rent_due", admin),
        ("Pastrim i përgjithshëm", TODAY + timedelta(days=3), "chore", admin),
        ("Darkë shtëpie", TODAY + timedelta(days=6), "custom", m1),
        ("Mbledhje qiraxhish", TODAY + timedelta(days=1), "custom", m2),
    ]
    for title, edate, etype, creator in event_specs:
        ev = Event(
            household_id=household.id,
            title=title,
            date=edate,
            type=etype,
            created_by_id=creator.id,
            created_at=dt_days_ago(5),
        )
        db.session.add(ev)

    db.session.commit()
    print(f"  ✓ seeded chores, expenses, shopping, issues, events, rules for '{household.name}'")


def main():
    with app.app_context():
        print("Seeding DormMate database...\n")

        # ------------------------------------------------------------------
        # Household 1: existing "TourLingo Tirana" — add 2 roommates
        # ------------------------------------------------------------------
        household1 = Household.query.filter_by(name="TourLingo Tirana").first()
        if not household1:
            print("Household 'TourLingo Tirana' not found — creating it.")
            ema, ema_new = get_or_create_user("Ema", "emasadiku01@gmail.com")
            if ema_new:
                ema.set_password(DEMO_PASSWORD)
            household1 = Household(
                name="TourLingo Tirana",
                invite_code=Household.generate_invite_code(),
                created_at=dt_days_ago(21),
            )
            db.session.add(household1)
            db.session.flush()
            db.session.add(Membership(
                user_id=ema.id, household_id=household1.id, role="admin",
                joined_at=dt_days_ago(21),
            ))
            db.session.commit()

        ema = User.query.filter_by(email="emasadiku01@gmail.com").first()

        andi, andi_new = get_or_create_user("Andi Krasniqi", "andi.krasniqi@example.com", "204")
        elona, elona_new = get_or_create_user("Elona Hoxha", "elona.hoxha@example.com", "205")

        for user, is_new in [(andi, andi_new), (elona, elona_new)]:
            if is_new:
                db.session.flush()
                existing = Membership.query.filter_by(
                    user_id=user.id, household_id=household1.id
                ).first()
                if not existing:
                    db.session.add(Membership(
                        user_id=user.id, household_id=household1.id, role="member",
                        joined_at=dt_days_ago(19),
                    ))
                    db.session.flush()
                    # notify existing members
                    for member in household1.members:
                        if member.id == user.id:
                            continue
                        add_notification(
                            member, household1, "member_joined",
                            f"{user.name} joined '{household1.name}'",
                            f"{user.name} is now a member of your household.",
                            is_read=True,
                            created_at=dt_days_ago(19),
                        )
        db.session.commit()

        members1 = household1.members  # refresh
        print(f"Household 1: '{household1.name}' — members: {[u.name for u in members1]}")

        # Only seed activity once (skip if chores already exist)
        if not Chore.query.filter_by(household_id=household1.id).first():
            seed_household_block("H1", household1, members1, admin=ema)
        else:
            print("  (activity already seeded for this household, skipping)")

        # ------------------------------------------------------------------
        # Household 2: brand-new household with 3 fresh members
        # ------------------------------------------------------------------
        household2 = Household.query.filter_by(name="Shtëpia e Studentëve").first()
        is_new_h2 = household2 is None
        if is_new_h2:
            household2 = Household(
                name="Shtëpia e Studentëve",
                invite_code=Household.generate_invite_code(),
                created_at=dt_days_ago(20),
            )
            db.session.add(household2)
            db.session.flush()

        driton, driton_new = get_or_create_user("Driton Berisha", "driton.berisha@example.com", "101")
        sara, sara_new = get_or_create_user("Sara Marku", "sara.marku@example.com", "102")
        gentian, gentian_new = get_or_create_user("Gentian Çela", "gentian.cela@example.com", "103")

        for user, role, is_new in [
            (driton, "admin", driton_new),
            (sara, "member", sara_new),
            (gentian, "member", gentian_new),
        ]:
            existing = Membership.query.filter_by(
                user_id=user.id, household_id=household2.id
            ).first()
            if not existing:
                db.session.add(Membership(
                    user_id=user.id, household_id=household2.id, role=role,
                    joined_at=dt_days_ago(20),
                ))
        db.session.commit()

        members2 = household2.members
        print(f"\nHousehold 2: '{household2.name}' — members: {[u.name for u in members2]}")

        if not Chore.query.filter_by(household_id=household2.id).first():
            seed_household_block("H2", household2, members2, admin=driton)
        else:
            print("  (activity already seeded for this household, skipping)")

        db.session.commit()

        print("\nDone. Demo login credentials for new accounts (password for all): "
              f"'{DEMO_PASSWORD}'")
        print("  - andi.krasniqi@example.com   (Household 1: TourLingo Tirana)")
        print("  - elona.hoxha@example.com     (Household 1: TourLingo Tirana)")
        print("  - driton.berisha@example.com  (Household 2: Shtëpia e Studentëve, admin)")
        print("  - sara.marku@example.com      (Household 2)")
        print("  - gentian.cela@example.com    (Household 2)")
        print(f"\nHousehold 2 invite code: {household2.invite_code}")


if __name__ == "__main__":
    main()