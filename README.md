# Telegram Gym Bot — Minimal Starter

This repository contains a minimal Telegram bot implementation for managing walk-in gym reservations and sessions (capacity 18). It follows the design in `proposal.md` and the checklist.

Quick setup

1. Create and activate a Python virtual environment (recommended):

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and fill values (BOT_TOKEN, ADMIN_GROUP_ID, GYM_GROUP_ID).

4. Run the bot:

```bash
python -m bot.main
```

Notes
- This is a minimal, local implementation using SQLite. For production, run under a process manager and use a persistent DB.
- Scheduler jobs run in-process using APScheduler.
- Students can request access directly via `/join`, which collects their name, roll number, and phone before alerting admins for approval.

## Database migrations (Alembic)

This project uses Alembic for schema migrations. The configuration lives in `alembic.ini` with scripts under `migrations/`.

Typical workflow:

```bash
# set DATABASE_URL if you are not using the default sqlite database
export DATABASE_URL=sqlite:///./gym_bot.db

# create a new migration based on model changes
alembic revision --autogenerate -m "describe change"

# apply migrations
alembic upgrade head
```

Alembic autogenerate inspects the SQLAlchemy metadata defined in `src/db.py`. Make sure any new models are imported into that module before generating migrations.

## Onboarding & Access Control

Students must be invited by an admin before they can talk to the bot:

1. Collect applicant details via the Google Form.
2. In the admin group, run `/invite <ROLL_NUMBER>` while mentioning the approved student in the same message. The mention lets the bot capture their Telegram account automatically.
3. Each user record stores `roll_number` (unique, required), optional `full_name`, and the Telegram ID. Usernames are stored only when available but are never required.
4. When the student messages the bot, their Telegram account is already linked to the invited record. Anyone not in the allow-list is prompted to contact the Health Club GIM team for access.
