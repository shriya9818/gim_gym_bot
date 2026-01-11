from sqlalchemy.orm import Session

import src.db as db
import src.enums as enums
import src.models as models
import src.repo as db_repo
import src.utils as utils
from src.config import CONFIG
from src.strings import t

USER_TIMEZONE = CONFIG.timezone


def _reservation_locked_message(lock_state: models.ReservationLockState) -> str:
    assert lock_state.is_locked, "Lock state must indicate locked"
    return f"Reservations are locked. Reason: {lock_state.reason or 'N/A'}"


def create_reservation(
    *, db_session: Session, db_user: db.User
) -> models.CommandResult:
    lock_state = db_repo.get_reservation_lock_state(db_session=db_session)
    if lock_state.is_locked:
        return models.CommandResult(
            success=False, message=_reservation_locked_message(lock_state)
        )

    now = utils.utc_now()
    if db_user.block_until and db_user.block_until > now:
        duration = utils.humanize_time(db_user.block_until)
        return models.CommandResult(
            success=False, message=t("reserve.blocked", duration=duration)
        )

    active_reservation = db_repo.get_user_reservation(
        db_session=db_session, user_id=db_user.id
    )
    if active_reservation:
        return models.CommandResult(
            success=False,
            message=t(
                "reserve.active_exists",
                state=active_reservation.state.value.capitalize(),
            ),
        )

    checked_in, reserved = db_repo.get_occupancy_stats(db_session=db_session)
    if checked_in + reserved >= CONFIG.capacity:
        return models.CommandResult(success=False, message=t("reserve.capacity_full"))

    db_repo.create_reservation(db_session=db_session, user=db_user)
    msg = t("reserve.success", minutes=CONFIG.reserve_window_minutes)
    return models.CommandResult(success=True, message=msg)


def checkin_reservation(
    *, db_session: Session, db_user: db.User
) -> models.CommandResult:
    lock_state = db_repo.get_reservation_lock_state(db_session=db_session)
    if lock_state.is_locked:
        return models.CommandResult(
            success=False, message=_reservation_locked_message(lock_state)
        )

    now = utils.utc_now()
    if db_user.block_until and db_user.block_until > now:
        duration = utils.humanize_time(db_user.block_until)
        return models.CommandResult(
            success=False, message=t("reserve.blocked", duration=duration)
        )

    active_reservation = db_repo.get_user_reservation(
        db_session=db_session, user_id=db_user.id
    )
    if not active_reservation:
        return models.CommandResult(success=False, message=t("checkin.no_reservation"))

    if active_reservation.state != enums.ReservationState.RESERVED:
        return models.CommandResult(success=False, message=t("checkin.no_active"))

    if active_reservation.reservation_expiry_time < now:
        return models.CommandResult(success=False, message=t("checkin.expired"))

    checked_in, reserved = db_repo.get_occupancy_stats(db_session=db_session)
    if checked_in + reserved >= CONFIG.capacity:
        return models.CommandResult(success=False, message=t("reserve.capacity_full"))

    db_repo.checkin_reservation(
        db_session=db_session, reservation_id=active_reservation.id
    )
    msg = t("checkin.success", minutes=CONFIG.session_duration_minutes)
    return models.CommandResult(success=True, message=msg)


def checkout_reservation(
    *, db_session: Session, db_user: db.User
) -> models.CommandResult:
    # Checkout shouldn't check the global lock state
    active_reservation = db_repo.get_user_reservation(
        db_session=db_session, user_id=db_user.id
    )
    if not active_reservation:
        return models.CommandResult(success=False, message=t("checkout.no_reservation"))

    if active_reservation.state != enums.ReservationState.CHECKED_IN:
        return models.CommandResult(success=False, message=t("checkout.not_checked_in"))

    db_repo.checkout_reservation(
        db_session=db_session, reservation_id=active_reservation.id
    )
    return models.CommandResult(success=True, message=t("checkout.success"))


def cancel_reservation(
    *, db_session: Session, db_user: db.User
) -> models.CommandResult:
    # Cancel shouldn't check the global lock state
    active_reservation = db_repo.get_user_reservation(
        db_session=db_session, user_id=db_user.id
    )
    if not active_reservation:
        return models.CommandResult(success=False, message=t("cancel.no_reservation"))

    if active_reservation.state != enums.ReservationState.RESERVED:
        return models.CommandResult(success=False, message=t("cancel.no_active"))

    db_repo.cancel_reservation(
        db_session=db_session, reservation_id=active_reservation.id
    )
    return models.CommandResult(success=True, message=t("cancel.success"))


def user_status(*, db_session: Session, db_user: db.User) -> models.CommandResult:
    locked_state = db_repo.get_reservation_lock_state(db_session=db_session)
    if locked_state.is_locked:
        msg = t("status.locked_prefix", reason=locked_state.reason) + "\n"
    else:
        msg = ""

    (checked_in, reserved) = db_repo.get_occupancy_stats(db_session=db_session)
    total_count = checked_in + reserved
    msg = f"Occupancy: {total_count} out of {CONFIG.capacity}\nChecked In: {checked_in}\nReservations: {reserved}\n"

    active_reservation = db_repo.get_user_reservation(
        db_session=db_session, user_id=db_user.id
    )
    if active_reservation:
        msg += f"Your Status: {active_reservation.state}"

        if active_reservation.state == enums.ReservationState.RESERVED:
            expiry_time = utils.humanize_time(
                active_reservation.reservation_expiry_time
            )
            msg += f"\nReservation expires in {expiry_time}."
        elif active_reservation.state == enums.ReservationState.CHECKED_IN:
            assert active_reservation.max_checkout_time is not None
            auto_checkout_time = utils.humanize_time(
                active_reservation.max_checkout_time
            )
            msg += f"\nAuto-checkout in {auto_checkout_time}."

    if db_user.block_until and db_user.block_until > utils.utc_now():
        msg += "\n" + t(
            "status.blocked", duration=utils.humanize_time(db_user.block_until)
        )

    return models.CommandResult(success=True, message=msg)


def expiring_sessions(*, db_session: Session, db_user: db.User) -> models.CommandResult:
    active_reservations = db_repo.get_active_reservations(db_session=db_session)
    reserved_sessions = list(
        filter(
            lambda x: x.state == enums.ReservationState.RESERVED, active_reservations
        )
    )[:5]
    checked_in_sessions = list(
        filter(
            lambda x: x.state == enums.ReservationState.CHECKED_IN, active_reservations
        )
    )[:5]

    lines = []

    if checked_in_sessions:
        lines.append("Expiring Checkins:")
        for reservation in checked_in_sessions:
            assert (
                reservation.max_checkout_time is not None
            ), "Checkout time not set for checked-in reservation"
            user = reservation.user
            duration_left = utils.humanize_duration(reservation.max_checkout_time)
            lines.append(f"- {utils.format_user(user)} - {duration_left}")

    if reserved_sessions:
        lines.append("Expiring Reservations:")
        for reservation in reserved_sessions:
            user = reservation.user
            duration_left = utils.humanize_duration(reservation.reservation_expiry_time)
            lines.append(f"- {utils.format_user(user)} - {duration_left}")

    if not lines:
        msg = "No active sessions"
    else:
        msg = "\n".join(lines)

    return models.CommandResult(success=True, message=msg)
