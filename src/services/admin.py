import re
from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

import src.db as db
import src.enums as enums
import src.models as models
import src.repo as db_repo
import src.utils as utils
from src.config import CONFIG
from src.strings import t

from ..storage import (
    count_no_shows,
    count_overstays,
    get_reservation_lock,
    set_reservation_lock,
)


def _resolve_user(db, identifier: str) -> Optional[db.User]:
    if not identifier:
        return None
    ident = identifier.strip()
    if not ident:
        return None
    if ident.startswith("@"):
        handle = ident[1:].lower()
        stmt = select(User).where(func.lower(User.username) == handle)
        return db.execute(stmt).scalars().first()
    try:
        tid = int(ident)
    except ValueError:
        return get_user_by_roll_number(db, ident)
    stmt = select(User).where(User.telegram_id == tid)
    user = db.execute(stmt).scalars().first()
    if user:
        return user
    return get_user_by_roll_number(db, ident)


def summarize(*, db_session: Session) -> str:
    active_reservations = db_repo.get_active_reservations(db_session=db_session)
    reserved_sessions = list(
        filter(
            lambda x: x.state == enums.ReservationState.RESERVED, active_reservations
        )
    )
    checked_in_sessions = list(
        filter(
            lambda x: x.state == enums.ReservationState.CHECKED_IN, active_reservations
        )
    )

    lines = [
        f"Checked-in: {len(checked_in_sessions)}",
        f"Reserved: {len(reserved_sessions)}",
    ]
    if checked_in_sessions:
        lines.append("\nActive sessions:")
        for reservation in checked_in_sessions:
            assert (
                reservation.max_checkout_time is not None
            ), "Checkout time not set for checked-in reservation"
            user = reservation.user
            duration_left = utils.humanize_duration(reservation.max_checkout_time)
            lines.append(f"- {utils.format_user(user)} - {duration_left}")

    if reserved_sessions:
        lines.append("\nReservations:")
        for reservation in reserved_sessions:
            user = reservation.user
            duration_left = utils.humanize_duration(reservation.reservation_expiry_time)
            lines.append(f"- {utils.format_user(user)} - {duration_left}")

    lock_state = db_repo.get_reservation_lock_state(db_session=db_session)
    if lock_state.is_locked:
        lines.append("\nReservations locked: {lock_state.reason}")

    return "\n".join(lines)


def lock_reservations(*, db_session: Session, reason: str) -> str:
    with SessionLocal() as db:
        state = set_reservation_lock(
            db,
            locked=True,
            reason=reason or "Reservations temporarily unavailable.",
            locked_by=admin_id,
            timestamp=datetime.utcnow(),
        )
        return f"Reservations locked. Reason: {_reservation_locked_message(state)}"


def add_admin(identifier: str) -> tuple[bool, str]:
    """Grant admin role to an existing user (or numeric telegram id)."""
    with SessionLocal() as db:
        user = _resolve_user(db, str(identifier))
        if not user:
            return False, t("errors.invalid_identifier")
        if user.telegram_id in (CONFIG.super_users or []):
            return True, "User is already a super-admin."
        user.is_admin = True
        db.add(user)
        db.commit()
        return True, f"{_format_user(user)} promoted to admin."


def remove_admin(identifier: str) -> tuple[bool, str]:
    with SessionLocal() as db:
        user = _resolve_user(db, str(identifier))
        if not user:
            return False, "User not found."
        if user.telegram_id in (CONFIG.super_users or []):
            return False, "Cannot revoke a configured super-admin."
        user.is_admin = False
        db.add(user)
        db.commit()
        return True, f"{_format_user(user)} admin access revoked."


def list_admins() -> list[str]:
    out: list[str] = []
    for su in CONFIG.super_users or []:
        out.append(f"super:{su}")
    with SessionLocal() as db:
        stmt = select(User).where(User.is_admin == True)
        rows = db.execute(stmt).scalars().all()
        for u in rows:
            out.append(f"{u.telegram_id}:{u.username or u.full_name or ''}")
    return out


def invite_user(
    roll_number: str,
    *,
    full_name: Optional[str] = None,
    telegram_id: Optional[int] = None,
    username: Optional[str] = None,
) -> tuple[bool, str]:
    roll = roll_number.strip()
    if not roll:
        return False, t("admin.invite_roll_required")
    with SessionLocal() as db:
        existing = get_user_by_roll_number(db, roll)
        if existing:
            return False, t("admin.invite_exists")
        create_invited_user(
            db,
            roll_number=roll,
            username=username,
            full_name=full_name,
            telegram_id=telegram_id,
        )
        display_name = full_name or username or roll
        return True, t("admin.invite_success", name=display_name, roll_number=roll)


def user_report(identifier: str) -> Tuple[bool, str]:
    with SessionLocal() as db:
        user = _resolve_user(db, identifier)
        if not user:
            return False, "User not found or has never interacted with the bot."
        active = get_active_session(db, user)
        checked_in = "None"
        if active:
            if active.state == ReservationState.CHECKED_IN:
                checked_in = (
                    f"checked in; auto-checkout {_humanize(active.auto_checkout_at)}"
                )
            elif active.state == ReservationState.RESERVED:
                checked_in = f"reserved; expires {_humanize(active.reserve_expires_at)}"
            else:
                checked_in = active.state.value.lower()
        block = (
            f"blocked {_humanize(user.block_until)}"
            if user.block_until and user.block_until > datetime.utcnow()
            else "active"
        )
        stmt = (
            select(func.count())
            .select_from(SessionModel)
            .where(SessionModel.user_id == user.id)
        )
        total_sessions = db.execute(stmt).scalar_one()
        msg = (
            f"User: {_format_user(user)}\n"
            f"Status: {block}\n"
            f"No-shows: {count_no_shows(db, user)}, Overstays: {count_overstays(db, user)}\n"
            f"Total records: {total_sessions}\n"
            f"Current session: {checked_in}"
        )
        return True, msg


def force_checkout_user(identifier: str) -> Tuple[bool, str]:
    now = datetime.utcnow()
    with SessionLocal() as db:
        user = _resolve_user(db, identifier)
        if not user:
            return False, t("errors.invalid_identifier")
        active = get_active_session(db, user)
        if not active:
            return False, "User has no active reservation or session."
        if active.state == ReservationState.RESERVED:
            active.state = ReservationState.EXPIRED
            active.reserve_expires_at = now
            db.add(active)
            db.commit()
            return True, f"Reservation for {_format_user(user)} has been cancelled."
        checkout_session(db, active, now)
        return True, f"{_format_user(user)} has been checked out."


def block_user(identifier: str, duration_text: str) -> Tuple[bool, str]:
    duration = _parse_duration(duration_text)
    if not duration:
        return False, t("errors.invalid_duration")
    with SessionLocal() as db:
        user = _resolve_user(db, identifier)
        if not user:
            return False, t("errors.invalid_identifier")
        until = datetime.utcnow() + duration
        user.block_until = until
        db.add(user)
        db.commit()
        return True, f"{_format_user(user)} blocked {_humanize(until)}."


def unblock_user(identifier: str) -> Tuple[bool, str]:
    with SessionLocal() as db:
        user = _resolve_user(db, identifier)
        if not user:
            return False, t("errors.invalid_identifier")
        user.block_until = None
        db.add(user)
        db.commit()
        return True, f"{_format_user(user)} is now unblocked."


def kick_everyone_out() -> str:
    now = datetime.utcnow()
    with SessionLocal() as db:
        checked_in_sessions = (
            db.execute(
                select(SessionModel).where(
                    SessionModel.state == ReservationState.CHECKED_IN
                )
            )
            .scalars()
            .all()
        )
        reserved_sessions = (
            db.execute(
                select(SessionModel).where(
                    SessionModel.state == ReservationState.RESERVED
                )
            )
            .scalars()
            .all()
        )
        for sess in checked_in_sessions:
            sess.state = ReservationState.CHECKED_OUT
            sess.checkout_time = now
            db.add(sess)
        for sess in reserved_sessions:
            sess.state = ReservationState.EXPIRED
            sess.reserve_expires_at = now
            db.add(sess)
        db.commit()
        return (
            f"Force checkout complete. {len(checked_in_sessions)} sessions closed, "
            f"{len(reserved_sessions)} reservations cancelled."
        )
