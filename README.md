# Nestly

Shared source of truth for a household: who owes who, what chore is due, and what's on the shopping list — instead of three group chats and a mental tally nobody agrees on.

## Project structure

```
nestly/
├── app.py                  # Flask entry point — run this
├── requirements.txt
├── static/
│   ├── css/style.css       # all styling, palette lives in :root variables
│   ├── js/main.js          # nav toggle + scroll reveal
│   └── images/
│       └── logo-placeholder.svg   # swap this for your real logo
├── templates/
│   └── index.html          # landing page
├── models/                 # SQLAlchemy models go here (empty for now)
├── routes/                 # Blueprints (auth, households, expenses...) go here (empty for now)
└── instance/                # local SQLite db lives here once you add one (gitignored)
```

## Opening it in PyCharm

1. Unzip and open the `nestly` folder in PyCharm as a project (File → Open → select the folder).
2. Create a virtual environment when prompted, or manually:
   ```
   python -m venv venv
   ```
3. Activate it and install dependencies:
   ```
   # macOS/Linux
   source venv/bin/activate
   # Windows
   venv\Scripts\activate

   pip install -r requirements.txt
   ```
4. Right-click `app.py` → Run, or use a terminal:
   ```
   python app.py
   ```
5. Visit `http://127.0.0.1:5000` to see the landing page.

## Swapping in your real logo

Drop your logo file into `static/images/` (e.g. `logo.png`), then in `templates/index.html` replace the two references to `logo-placeholder.svg` with your filename.

## Where to build next

Per the feature breakdown: auth → household creation/invites → expense logging with splits → the debt-settlement calculator. That's the spine. Chores, the shopping list, and the calendar follow the same CRUD pattern once that's solid. Reports, badges, and stats are the polish layer at the end.
