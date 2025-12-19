import json
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import CONFIG
from .db import BotSetting, JoinRequest
from .db import Reservations as SessionModel
from .db import User
from .enums import ReservationState


@dataclass
class ReservationLockState:
    locked: bool = False
    reason: Optional[str] = None
    locked_by: Optional[int] = None
    locked_at: Optional[datetime] = None


def cancel_reservation(db: Session, session: SessionModel) -> SessionModel:
    session.state = ReservationState.EXPIRED
    session.reserve_expires_at = datetime.utcnow()
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def find_expired_reservations(db: Session, now: datetime) -> List[SessionModel]:
    stmt = select(SessionModel).where(
        SessionModel.state == ReservationState.RESERVED,
        SessionModel.reserve_expires_at <= now,
    )
    return db.execute(stmt).scalars().all()


def find_overdue_checkins(db: Session, now: datetime) -> List[SessionModel]:
    stmt = select(SessionModel).where(
        SessionModel.state == ReservationState.CHECKED_IN,
        SessionModel.auto_checkout_at <= now,
    )
    return db.execute(stmt).scalars().all()


def count_no_shows(db: Session, user: User) -> int:
    stmt = (
        select(func.count())
        .select_from(SessionModel)
        .where(SessionModel.user_id == user.id, SessionModel.is_no_show.is_(True))
    )
    return int(db.execute(stmt).scalar_one_or_none() or 0)


def count_overstays(db: Session, user: User) -> int:
    stmt = (
        select(func.count())
        .select_from(SessionModel)
        .where(SessionModel.user_id == user.id, SessionModel.did_overstay.is_(True))
    )
    return int(db.execute(stmt).scalar_one_or_none() or 0)


def _get_setting(db: Session, key: str) -> Optional[BotSetting]:
    stmt = select(BotSetting).where(BotSetting.key == key)
    return db.execute(stmt).scalars().first()


def _set_setting(db: Session, key: str, value: str) -> BotSetting:
    setting = _get_setting(db, key)
    if setting:
        setting.value = value
    else:
        setting = BotSetting(key=key, value=value)
    db.add(setting)
    db.commit()
    db.refresh(setting)
    return setting


def get_reservation_lock(db: Session) -> ReservationLockState:
    setting = _get_setting(db, "reservations_lock")
    if not setting:
        return ReservationLockState()
    try:
        data = json.loads(setting.value)
    except json.JSONDecodeError:
        return ReservationLockState()
    locked = bool(data.get("locked"))
    reason = data.get("reason")
    locked_by = data.get("locked_by")
    locked_at_raw = data.get("locked_at")
    locked_at = None
    if locked_at_raw:
        try:
            locked_at = datetime.fromisoformat(locked_at_raw)
        except ValueError:
            locked_at = None
    return ReservationLockState(
        locked=locked, reason=reason, locked_by=locked_by, locked_at=locked_at
    )


def set_reservation_lock(
    db: Session,
    *,
    locked: bool,
    reason: Optional[str] = None,
    locked_by: Optional[int] = None,
    timestamp: Optional[datetime] = None,
) -> ReservationLockState:
    payload = {
        "locked": locked,
        "reason": reason or "",
        "locked_by": locked_by,
        "locked_at": (timestamp or datetime.utcnow()).isoformat(),
    }
    _set_setting(db, "reservations_lock", json.dumps(payload))
    return ReservationLockState(
        locked=locked,
        reason=reason or None,
        locked_by=locked_by,
        locked_at=datetime.fromisoformat(payload["locked_at"]),
    )


__all__ = [
    "ReservationLockState",
    "get_active_session",
    "create_reservation",
    "checkin_session",
    "checkout_session",
    "cancel_reservation",
    "get_current_occupancy",
    "get_reserved_count",
    "find_expired_reservations",
    "find_overdue_checkins",
    "get_reservation_lock",
    "set_reservation_lock",
    "count_no_shows",
    "count_overstays",
]
