**Project Overview**

- **Name:** Gim Gym Bot
- **Purpose:** A Telegram bot for managing gym access: join requests, reservations, check-ins, and admin controls.
- **Repository Root:** project is rooted at the repository containing `src/` and `config.yaml`.

**Outline**

- **Overview:** Short description and primary responsibilities
- **Architecture:** Components, data flow, and integrations
- **Key Files:** Where to look in the codebase
- **Core Flows:** Join, Reservation lifecycle, Admin actions
- **Data Model:** Database tables and important fields
- **Scheduler & Background Jobs:** Rationale and behavior
- **Technologies & Libraries:** All major dependencies and why chosen
- **Design & Decision Points:** Tradeoffs and reasoning for important choices
- **Security & Operational Concerns:** Environment variables, permissions, scaling
- **How to run & test locally:** Quick commands
- **Next steps / Recommendations:** Improvements and monitoring

**Architecture**

- **Bot layer (Telegram interaction):** Handled using `aiogram` (see [src/main.py](src/main.py) and router modules). `main.py` bootstraps the bot, initializes the DB and scheduler and starts polling.
- **Routing & Handlers:** High-level routers are implemented in `src/router/` and `src/handlers.py`. The router composes sub-routers for user, admin and form flows.
- **Service layer:** Business logic lives in `src/services/` (e.g., `user.py`, `admin.py`). These functions implement reservation logic, validation, and compose repository calls.
- **Repository (DB access):** `src/repo.py` contains all SQLAlchemy queries and updates. This isolates SQL logic from services.
- **Database models:** `src/db.py` defines SQLAlchemy ORM models and `init_db()` that creates tables.
- **Scheduler:** `src/scheduler.py` runs periodic cleanup jobs (expire reservations/overdue checkins) using `apscheduler`.
- **Utilities & strings:** `src/utils.py` contains helper functions (time handling, formatting, permission checks). `src/strings.py` loads localized strings from `strings.yaml`.
- **Logging:** `src/logger.py` configures `loguru` for structured console output.

**Key Files (entry points & responsibilities)**

- **[src/main.py](src/main.py):** App bootstrap. Calls `init_db()`, starts scheduler, and `Dispatcher` polling.
- **[src/router/user.py](src/router/user.py)** and **[src/router/admin.py](src/router/admin.py):** Command handlers and decorators enforcing chat rules and auth.
- **[src/forms/join.py](src/forms/join.py):** FSM-driven join request flow and admin approval callbacks.
- **[src/services/user.py](src/services/user.py):** Reservation and session business rules (create, checkin, checkout, cancel, status).
- **[src/repo.py](src/repo.py):** All DB queries/updates (select/insert/update), occupancy calculations and lock-state storage.
- **[src/db.py](src/db.py):** SQLAlchemy models: `User`, `Reservations`, `BotSetting`, `JoinRequest` and `init_db()`.
- **[src/scheduler.py](src/scheduler.py):** Background tasks: `expire_reservations()` and `expire_overdue_checkins()`.
- **[config.yaml](config.yaml)** and **[src/config.py](src/config.py):** Central configuration loader using `pydantic` and environment variables.

**Core flows**

1. **Join Flow (user -> admin -> invite)**
   - User issues `/join` (private chat). FSM in `src/forms/join.py` collects name, roll, phone.
   - A `JoinRequest` is created via `repo.create_join_request`.
   - A message with approve/decline inline buttons is posted to the configured admin chat. Admins click callback which triggers processing and optionally creates a `User` via `repo.create_invited_user`.
   - If approved, bot creates a one-time invite link for the gym group and sends to the user.

2. **Reservation Lifecycle**
   - `create_reservation()` in `src/services/user.py` checks global lock state and capacity via `repo.get_occupancy_stats`, then inserts a `Reservations` row with `RESERVED` state.
   - `checkin_reservation()` moves `RESERVED` -> `CHECKED_IN`, sets `max_checkout_time` (session duration) and notifies group.
   - `checkout_reservation()` sets state to `CHECKED_OUT`.
   - `cancel_reservation()` or scheduler expiry sets state to `EXPIRED` and may mark `is_no_show` or `did_overstay`.

3. **Admin operations**
   - Admins can `lock_reservations`, `unlock_reservations`, `promote_user`, `demote_user`, `summarize` active sessions. These are implemented in `src/services/admin.py` and cause updates via `src/repo.py`.

**Data model summary**

- `users` (id, telegram_id, roll_number, full_name, phone_number, is_admin, block_until)
- `reservations` (id, user_id, state, reservation_time, reservation_expiry_time, checkin_time, checkout_time, max_checkout_time, is_no_show, did_overstay)
- `bot_settings` (key, value) — used to store global JSON-encoded settings (e.g., reservation lock state)
- `join_requests` (id, user_id, full_name, roll_number, phone_number, status, approver_id, admin_chat_id, admin_message_id)

Database is created via SQLAlchemy models in `src/db.py`. The code uses `create_engine(CONFIG.database_path)` and `sessionmaker(expire_on_commit=False)`.

**Scheduler & background jobs**

- `apscheduler.schedulers.background.BackgroundScheduler` is used.
- Two periodic jobs run every 1 minute: `expire_reservations()` and `expire_overdue_checkins()`.
- Rationale: short interval keeps the bot state consistent and expiry times accurate; background scheduler avoids separate worker processes.
- Tradeoff: running DB queries every minute is simple but may not scale for large datasets; for scale, a message queue or more selective scheduling could be used.

**Technologies & libraries used**

- Python 3.10+ (typing features like `|` union used)
- aiogram — Telegram bot framework used for handlers, routers, FSM.
- SQLAlchemy ORM — data modeling and DB access.
- pydantic — config validation (`src/config.py`) and request models in `src/models.py`.
- apscheduler — background scheduled jobs.
- loguru — structured logging.
- yaml & python-dotenv — configuration via `config.yaml` and env vars (BOT_TOKEN, DATABASE_URL optional).
- arrow — human-friendly time formatting.

**Design & decision points (explicit reasoning)**

- **Service / Repo separation:** Business logic is in `src/services/*`, while SQL lives in `src/repo.py`. This isolates SQL complexity and makes unit testing services easier.
- **Using `bot_settings` JSON for global state:** A single `BotSetting` row stores serialized JSON for `RESERVATION_LOCK`. Simpler than a separate table per state but trades off type safety for flexibility.
- **SQLite by default (configurable):** `CONFIG.database_path` may point to SQLite (check_same_thread handling present). The code includes connect args for SQLite. This is convenient for dev and small deployments.
- **Short scheduler interval (1 minute):** Ensures timely expiration but increases DB load; chosen for simplicity.
- **No external message queue / worker:** Background jobs run in-process; simpler deployment but limits horizontal scaling.
- **Use of `expire_on_commit=False` in `SessionLocal`:** Sessions keep objects usable after commit. Easier for passing ORM objects between layers but requires attention to memory and state management.
- **Strings externalized to `strings.yaml`:** Makes localisation or text changes simple and keeps code cleaner.

**Security & operational notes**

- `BOT_TOKEN` must be provided via environment variable. `src/config.py` will raise if missing.
- Admin actions rely on configured chat IDs (`admin_group_id`, `gym_group_id`) in `config.yaml` to authorize message-based approvals.
- Super users are listed in config (`super_users`) and bypass some admin checks.
- Invite link creation requires the bot to have permission to create invite links in the gym group.
- Considerations: avoid storing bot token in repo; use secret manager in production.

**How to run locally (quick)**

- Create a virtualenv and install requirements:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

- Ensure environment variables and config are set (copy `config.yaml` and set `BOT_TOKEN` and optional `DATABASE_URL`).
- Run the bot:

```bash
python -m src.main
```

**Testing**

- There is at least one test in `tests/test_storage.py`. Run tests with `pytest` after installing dev deps.

**Observability & logging**

- Logging is configured with `loguru` to stdout. Consider adding structured sinks (file, cloud) or integration with monitoring when deploying.

**Limitations & recommended improvements**

- For scale, move scheduler tasks to a dedicated worker (Celery/RQ) or use DB-side triggers.
- Replace JSON-serialized `BotSetting` value with explicit typed columns for critical flags to simplify queries.
- Add rate-limiting / retries for Telegram API calls.
- Add integration/system tests that mimic typical flows (join -> admin approve -> reserve -> expire).
- Consider migrating from polling to webhooks for large-scale deployments.

**Where to look first for questions**

- Architecture and bootstrap: [src/main.py](src/main.py)
- Business logic and rules: [src/services/](src/services/)
- DB access and schema: [src/repo.py](src/repo.py) and [src/db.py](src/db.py)
- Background jobs: [src/scheduler.py](src/scheduler.py)
- Config and secrets: [src/config.py](src/config.py) and `config.yaml`

**Appendix — Frequently Asked Technical Questions (and short answers)**

- Q: Why is `expire_on_commit=False` used?  
  A: Keeps ORM instances usable after commit; simplifies passing objects between scopes but requires care with stale data.

- Q: How is capacity enforced?  
  A: `repo.get_occupancy_stats()` computes checked-in + reserved and `services.create_reservation()` checks against `CONFIG.capacity` before creating.

- Q: How does locking reservations work?  
  A: A `ReservationLockState` JSON object is stored in `bot_settings` under `RESERVATION_LOCK`. Services check `get_reservation_lock_state()` to refuse operations.

- Q: Is there explicit concurrency control for simultaneous reservations?  
  A: The code relies on DB transactions via session scope. For high contention, additional DB-level locking or serializable transactions would be recommended.

- Q: How are admin approvals secured?  
  A: Approval callbacks are only effective when posted in the configured admin chat and further validated against `is_admin` or `is_super_user` checks.

---

If you want, I can:

- add a diagram (ASCII or mermaid) for the request/response flows,
- generate a short slides-ready summary for management,
- or run unit tests locally and report results.
