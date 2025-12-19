from datetime import datetime
from pathlib import Path

import pytest

from src.db import Reservations as SessionModel
from src.db import SessionLocal, User, init_db
from src.storage import create_reservation, get_current_occupancy, get_reserved_count


def test_reservation_and_counts(tmp_path, monkeypatch):
    db_file = Path("test_gym_bot.db")
    if db_file.exists():
        db_file.unlink()
    # use a fresh in-memory sqlite DB for test
    # the project uses file DB by default; for simplicity, we just init and run basic ops
    init_db()
    db = SessionLocal()
    try:
        u = User(telegram_id=12345, username="tester", roll_number="R123")
        db.add(u)
        db.commit()
        db.refresh(u)
        now = datetime.utcnow()
        create_reservation(db, u, now)
        assert get_reserved_count(db) == 1
        assert get_current_occupancy(db) == 0
    finally:
        db.close()
