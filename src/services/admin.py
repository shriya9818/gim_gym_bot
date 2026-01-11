from sqlalchemy.orm import Session

import src.db as db
import src.enums as enums
import src.models as models
import src.repo as db_repo
import src.utils as utils
from src.config import CONFIG
from src.strings import t


def summarize(*, db_session: Session) -> models.CommandResult:
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
        lines.append(f"\nReservations locked: {lock_state.reason}")

    return models.CommandResult(success=True, message="\n".join(lines))


def lock_reservations(
    *, db_session: Session, name: str, reason: str
) -> models.CommandResult:
    current_reservation_state = db_repo.get_reservation_lock_state(
        db_session=db_session
    )
    if current_reservation_state.is_locked:
        return models.CommandResult(
            success=False,
            message=t(
                "lock.already_locked",
                locked_by=current_reservation_state.locked_by,
                reason=current_reservation_state.reason,
            ),
        )

    if len(reason) < 5:
        return models.CommandResult(
            success=False, message=t("lock.reason_short", reason=reason)
        )

    reservation_state = models.ReservationLockState(
        is_locked=True, reason=reason, locked_by=name
    )

    db_repo.add_reservation_lock(db_session=db_session, lock_state=reservation_state)
    return models.CommandResult(
        success=True, message=t("lock.lock_success", reason=reason, locked_by=name)
    )


def unlock_reservations(*, db_session: Session) -> models.CommandResult:
    current_reservation_state = db_repo.get_reservation_lock_state(
        db_session=db_session
    )
    if not current_reservation_state.is_locked:
        return models.CommandResult(success=False, message=t("lock.not_locked"))

    db_repo.remove_reservation_lock(db_session=db_session)
    return models.CommandResult(success=True, message=t("lock.unlock_success"))


def _get_user_by_identifier(db_session: Session, identifier: str) -> db.User | None:
    user_by_roll_number = db_repo.get_user(
        db_session=db_session, roll_number=identifier
    )
    if user_by_roll_number:
        return user_by_roll_number

    user_by_phone_number = db_repo.get_user(
        db_session=db_session, phone_number=identifier
    )
    if user_by_phone_number:
        return user_by_phone_number

    return None


def promote_user(*, db_session: Session, identifier: str) -> models.CommandResult:
    """Grant admin role to an existing user"""
    if len(identifier.strip()) < 5:
        return models.CommandResult(
            success=False, message=t("errors.too_short_identifier")
        )

    db_user = _get_user_by_identifier(db_session, identifier)
    if not db_user:
        return models.CommandResult(
            success=False, message=t("errors.invalid_identifier")
        )

    if db_user.is_admin:
        return models.CommandResult(success=False, message=t("promote.already_admin"))

    db_repo.promote_user(db_session=db_session, user_id=db_user.id)
    return models.CommandResult(success=True, message=t("promote.promote_success"))


def demote_user(*, db_session: Session, identifier: str) -> models.CommandResult:
    """Revoke admin role from an existing user"""
    if len(identifier.strip()) < 5:
        return models.CommandResult(
            success=False, message=t("errors.too_short_identifier")
        )

    db_user = _get_user_by_identifier(db_session, identifier)
    if not db_user:
        return models.CommandResult(
            success=False, message=t("errors.invalid_identifier")
        )

    if not db_user.is_admin:
        return models.CommandResult(success=False, message=t("promote.not_an_admin"))

    db_repo.demote_user(db_session=db_session, user_id=db_user.id)
    return models.CommandResult(success=True, message=t("promote.demote_success"))


def list_admins(*, db_session: Session) -> models.CommandResult:
    out: list[str] = ["List of super admins:"]
    for su_id in CONFIG.super_users:
        su_db_user = db_repo.get_user(db_session=db_session, telegram_id=su_id)
        if su_db_user:
            out.append(f"{su_db_user.telegram_id}: {su_db_user.full_name}")
        else:
            out.append(f"{su_id}: Not registered")

    out.append("")  # Blank line between super admins and admins
    out.append("List of admins:")

    admins = db_repo.get_admin_users(db_session=db_session)
    for admin in admins:
        if utils.is_super_user(admin.telegram_id):
            continue  # Skip super admins already listed

        out.append(f"{admin.telegram_id}: {admin.full_name}")

    return models.CommandResult(success=True, message="\n".join(out))


def user_info(*, db_session: Session, identifier: str) -> models.CommandResult:
    db_user = _get_user_by_identifier(db_session, identifier)
    if not db_user:
        return models.CommandResult(
            success=False, message=t("errors.invalid_identifier")
        )

    # Current active reservation (if any)
    active = db_repo.get_user_reservation(db_session=db_session, user_id=db_user.id)
    status = active.state.value if active else "No active reservation"

    # Total historical sessions
    all_reservations = db_repo.get_reservations_stats(
        db_session=db_session, user_id=db_user.id
    )

    lines = (
        f"User: {utils.format_user(db_user)}",
        f"No-shows: {all_reservations.no_shows}",
        f"Overstays: {all_reservations.overstays}",
        f"Total reservations: {all_reservations.total_reservations}",
        f"Current Status: {status}",
    )

    return models.CommandResult(success=True, message="\n".join(lines))
