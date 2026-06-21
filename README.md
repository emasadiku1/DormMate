# DormMate

A shared source of truth for a household: who owes who, what chore is due, and what's on the shopping list — instead of three different group chats and a mental tally nobody agrees on.

DormMate is a full-stack Flask app for roommates and shared apartments. It tracks shared expenses with automatic bill-splitting, a debt-settlement calculator, chore rotations, a shopping list, household notifications, and a few gamified extras (badges, stats) on top.

## Features

**Core**
- Authentication (signup/login with hashed passwords, session-based auth)
- Household creation and joining via invite code, multi-household support
- Expense logging with equal, percentage, or custom splits
- Real-time balances and a debt-simplification "settle up" calculator
- Chore management with assignment/rotation and overdue tracking
- Shared shopping list, optionally linked to a logged expense
- In-app notification feed (new expenses, payments, chores due/overdue, new members)

**Extra**
- Monthly expense reports by category and by person
- House rules page
- Maintenance/issue tracker
- Achievement badges and household stats
- Apartment calendar

## Tech stack

- **Backend:** Python, Flask, Flask-SQLAlchemy
- **Database:** SQLite (via SQLAlchemy, so swapping to MySQL/Postgres later just means changing the connection string)
- **Frontend:** Server-rendered Jinja2 templates, vanilla HTML/CSS/JS (no build step, no frontend framework)

## Project structure

```
dormmate/
├── app.py                  # Flask entry point
├── config.py                # app config (secret key, database URI)
├── seed.py                  # populates the database with realistic demo data
├── requirements.txt
├── models/                  # SQLAlchemy models (User, Household, Expense, Chore, ...)
├── routes/                  # Flask blueprints (auth, household, expenses, chores, ...)
├── services/                 # business logic (debt calculator, notifications, badges)
├── templates/                 # Jinja2 templates, organized by feature
├── static/                   # CSS, JS, images
└── instance/
    └── dormmate.db            # local SQLite database (created automatically)
```

## Running it locally

**1. Clone the repo**
```bash
git clone https://github.com/emasadiku1/DormMate.git
cd DormMate
```

**2. Create and activate a virtual environment**
```bash
python -m venv venv

# macOS/Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Run the app**
```bash
python app.py
```
This creates `instance/dormmate.db` automatically on first run (empty, just the schema — no users yet).

**5. Open it in your browser**
```
http://127.0.0.1:5000
```
From there, sign up for a new account directly through the app.

### Optional: load demo data

If you'd rather explore the app with realistic pre-filled households instead of starting from a blank account, run the seed script **as a plain script** (not through `flask run`):

```bash
python seed.py
```

This creates two demo households with chores, expenses, splits, notifications, and badge history already in place. Demo login credentials (password is the same for all of them):

| Email | Password | Household |
|---|---|---|
| andi.krasniqi@example.com | dormmate123 | TourLingo Tirana |
| elona.hoxha@example.com | dormmate123 | TourLingo Tirana |
| driton.berisha@example.com | dormmate123 | Shtëpia e Studentëve (admin) |
| sara.marku@example.com | dormmate123 | Shtëpia e Studentëve |
| gentian.cela@example.com | dormmate123 | Shtëpia e Studentëve |

The script is safe to re-run — it checks for existing data and won't duplicate it.

## Notes for anyone picking this up

- The database file is committed to this repo for convenience, so cloning it gives you a working set of accounts immediately without needing to run `seed.py`.
- If you want a totally clean slate instead, just delete `instance/dormmate.db` before running `python app.py` — a fresh empty database will be created automatically.
