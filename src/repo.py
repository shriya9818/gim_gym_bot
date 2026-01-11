import datetime

import sqlalchemy
from sqlalchemy import insert, select
from sqlalchemy.orm import Session, joinedload

import src.db as db
import src.enums as enums
import src.models as models
import src.utils as utils
from src.config import CONFIG
from src.logger import logger


def does_user_exist(*, db_session: Session, telegram_id: int) -> db.User | None:
    """Return True if a user with the given telegram ID exists"""
    stmt = select(db.User).where(db.User.telegram_id == telegram_id)
    result = db_session.execute(stmt).scalar_one_or_none()
    return result


def get_user(
    *,
    db_session: Session,
    telegram_id: int | None = None,
    roll_number: str | None = None,
    phone_number: str | None = None,
) -> db.User | None:
    """Return the user with the given telegram ID or roll number"""
    filters = []
    if telegram_id:
        filters.append(db.User.telegram_id == telegram_id)
    if roll_number:
        filters.append(db.User.roll_number == roll_number)
    if phone_number:
        filters.append(db.User.phone_number == phone_number)

    stmt = select(db.User).where(*filters)
    result = db_session.execute(stmt).scalar_one_or_none()
    return result


def get_admin_users(*, db_session: Session) -> list[db.User]:
    """Return a list of all admin users"""
    stmt = select(db.User).where(db.User.is_admin.is_(True))
    results = db_session.execute(stmt).scalars().all()
    return list(results)


def create_invited_user(
    *,
    db_session: Session,
    req: models.UserCreateRequest,
) -> int:
    stmt = (
        insert(db.User)
        .values(
            telegram_id=req.telegram_id,
            roll_number=req.roll_number,
            username=req.username,
            full_name=req.full_name,
            phone_number=req.phone_number,
            is_admin=False,
        )
        .returning(db.User.id)
    )
    inserted_id = db_session.execute(stmt).scalar_one()
    return inserted_id


def is_user_pending_join(*, db_session: Session, telegram_id: int) -> bool:
    """Return True if the user has a pending join request"""
    stmt = (
        select(db.JoinRequest)
        .where(
            db.JoinRequest.user_id == telegram_id,
            db.JoinRequest.status == enums.JoinRequestStatus.PENDING,
        )
        .order_by(db.JoinRequest.created_at.desc())
        .limit(1)
    )
    result = db_session.execute(stmt).scalar_one_or_none()
    return result is not None


def get_latest_join_request(
    *, db_session: Session, telegram_id: int
) -> db.JoinRequest | None:
    """Return the latest join request for the given telegram ID"""
    stmt = (
        select(db.JoinRequest)
        .where(db.JoinRequest.user_id == telegram_id)
        .order_by(db.JoinRequest.created_at.desc())
        .limit(1)
    )
    result = db_session.execute(stmt).scalar_one_or_none()
    return result


def get_join_request(
    *, db_session: Session, join_request_id: int
) -> db.JoinRequest | None:
    stmt = (
        select(db.JoinRequest)
        .where(db.JoinRequest.id == join_request_id)
        .order_by(db.JoinRequest.created_at.desc())
        .limit(1)
    )
    result = db_session.execute(stmt).scalar_one_or_none()
    return result


def create_join_request(
    *, db_session: Session, form_data: models.JoinFormRequest
) -> int:
    stmt = (
        insert(db.JoinRequest)
        .values(
            user_id=form_data.user_id,
            full_name=form_data.full_name,
            roll_number=form_data.roll_number,
            phone_number=form_data.phone_number,
            status=enums.JoinRequestStatus.PENDING,
        )
        .returning(db.JoinRequest.id)
    )

    inserted_id = db_session.execute(stmt).scalar_one()
    db_session.commit()

    return inserted_id


def update_join_request(
    *,
    db_session: Session,
    join_request_id: int,
    status: enums.JoinRequestStatus | None = None,
    admin_message_id: int | None = None,
    admin_chat_id: int | None = None,
) -> None:
    update_args: dict[str, enums.JoinRequestStatus | int] = {}
    if status is not None:
        update_args["status"] = status
    if admin_message_id is not None:
        update_args["admin_message_id"] = admin_message_id
    if admin_chat_id is not None:
        update_args["admin_chat_id"] = admin_chat_id

    stmt = (
        sqlalchemy.update(db.JoinRequest)
        .where(db.JoinRequest.id == join_request_id)
        .values(**update_args)
    )
    db_session.execute(stmt)


def create_reservation(*, db_session: Session, user: db.User) -> int:
    """Create a new reservation for the given user"""
    reservation_time = utils.utc_now()
    reservation_expiry_time = reservation_time + datetime.timedelta(
        minutes=CONFIG.reserve_window_minutes
    )

    stmt = (
        insert(db.Reservations)
        .values(
            user_id=user.id,
            state=enums.ReservationState.RESERVED,
            reservation_time=reservation_time,
            reservation_expiry_time=reservation_expiry_time,
        )
        .returning(db.Reservations.id)
    )
    reservation_id = db_session.execute(stmt).scalar_one()
    db_session.commit()
    return reservation_id


def checkin_reservation(*, db_session: Session, reservation_id: int) -> None:
    """Check in the reservation"""
    stmt = (
        select(db.Reservations)
        .where(
            db.Reservations.id == reservation_id,
            db.Reservations.state == enums.ReservationState.RESERVED,
        )
        .limit(1)
    )
    reservation = db_session.execute(stmt).scalar_one()
    checkin_time = utils.utc_now()
    max_checkout_time = checkin_time + datetime.timedelta(
        minutes=CONFIG.session_duration_minutes
    )

    reservation.state = enums.ReservationState.CHECKED_IN
    reservation.checkin_time = checkin_time
    reservation.max_checkout_time = max_checkout_time
    db_session.add(reservation)


def checkout_reservation(*, db_session: Session, reservation_id: int) -> None:
    """Check out the reservation"""
    stmt = (
        select(db.Reservations)
        .where(
            db.Reservations.id == reservation_id,
            db.Reservations.state == enums.ReservationState.CHECKED_IN,
        )
        .limit(1)
    )
    reservation = db_session.execute(stmt).scalar_one()
    checkout_time = utils.utc_now()

    reservation.state = enums.ReservationState.CHECKED_OUT
    reservation.checkout_time = checkout_time
    db_session.add(reservation)


def cancel_reservation(*, db_session: Session, reservation_id: int) -> None:
    """Cancel the reservation"""
    stmt = (
        select(db.Reservations)
        .where(
            db.Reservations.id == reservation_id,
            db.Reservations.state.in_(
                [enums.ReservationState.RESERVED, enums.ReservationState.CHECKED_IN]
            ),
        )
        .limit(1)
    )
    reservation = db_session.execute(stmt).scalar_one()
    reservation.state = enums.ReservationState.EXPIRED
    db_session.add(reservation)


def get_user_reservation(
    *, db_session: Session, user_id: int
) -> db.Reservations | None:
    stmt = select(db.Reservations).where(
        db.Reservations.user_id == user_id,
        db.Reservations.state.in_(
            [enums.ReservationState.RESERVED, enums.ReservationState.CHECKED_IN]
        ),
    )
    return db_session.execute(stmt).scalar_one_or_none()


def get_reservations_stats(
    *,
    db_session: Session,
    user_id: int,
) -> models.UserReservationsStats:
    filters = []
    if user_id is not None:
        filters.append(db.Reservations.user_id == user_id)

    stmt = select(db.Reservations.is_no_show, db.Reservations.did_overstay).where(
        db.Reservations.user_id == user_id
    )
    results = db_session.execute(stmt).all()
    total = len(results)
    no_shows = len([r for r in results if r.is_no_show])
    overstays = len([r for r in results if r.did_overstay])

    return models.UserReservationsStats(
        user_id=user_id,
        total_reservations=total,
        no_shows=no_shows,
        overstays=overstays,
    )


def get_occupancy_stats(*, db_session: Session) -> tuple[int, int]:
    """Return the current occupancy and reserved counts"""
    stmt = select(db.Reservations.user_id, db.Reservations.state).where(
        db.Reservations.state.in_(
            [enums.ReservationState.CHECKED_IN, enums.ReservationState.RESERVED]
        )
    )

    active_reservations = db_session.execute(stmt).all()
    checked_in = [
        r for r in active_reservations if r.state == enums.ReservationState.CHECKED_IN
    ]
    reserved = [
        r for r in active_reservations if r.state == enums.ReservationState.RESERVED
    ]

    if len(checked_in) + len(reserved) > CONFIG.capacity:
        logger.warning(
            "Occupancy exceeds capacity: checked_in={checked_in}, reserved={reserved}, capacity={capacity}",
            len(checked_in),
            len(reserved),
            CONFIG.capacity,
        )

    return int(len(checked_in)), int(len(reserved))


def get_active_reservations(*, db_session: Session) -> list[db.Reservations]:
    stmt = (
        select(db.Reservations)
        .where(
            db.Reservations.state.in_(
                [enums.ReservationState.CHECKED_IN, enums.ReservationState.RESERVED]
            )
        )
        .options(joinedload(db.Reservations.user))
        .order_by(db.Reservations.reservation_time)
    )
    return list(db_session.execute(stmt).scalars().all())


def _get_global_state(
    *, db_session: Session, key: enums.GlobalSettingKey
) -> str | None:
    """Return the value of the global setting with the given key"""
    stmt = select(db.BotSetting).where(db.BotSetting.key == key)
    result = db_session.execute(stmt).scalar_one_or_none()
    return result.value if result else None


def get_reservation_lock_state(*, db_session: Session) -> models.ReservationLockState:
    """Return the reservation lock state"""
    value = _get_global_state(
        db_session=db_session, key=enums.GlobalSettingKey.RESERVATION_LOCK
    )
    if value is None:
        return models.ReservationLockState(is_locked=False, locked_by="", reason="")

    return models.ReservationLockState.model_validate_json(value)


def add_reservation_lock(
    *, db_session: Session, lock_state: models.ReservationLockState
) -> None:
    """Lock reservations with the given reason"""
    value = _get_global_state(
        db_session=db_session, key=enums.GlobalSettingKey.RESERVATION_LOCK
    )
    # Do insertion if not present, else update
    if value is None:
        stmt = insert(db.BotSetting).values(
            key=enums.GlobalSettingKey.RESERVATION_LOCK,
            value=lock_state.model_dump_json(),
        )
        db_session.execute(stmt)
    else:
        stmt = (
            sqlalchemy.update(db.BotSetting)
            .where(db.BotSetting.key == enums.GlobalSettingKey.RESERVATION_LOCK)
            .values(value=lock_state.model_dump_json())
        )
        db_session.execute(stmt)


def remove_reservation_lock(*, db_session: Session) -> None:
    """Unlock reservations"""
    empty_reservation = models.ReservationLockState(
        is_locked=False, locked_by="", reason=""
    )
    stmt = (
        sqlalchemy.update(db.BotSetting)
        .where(db.BotSetting.key == enums.GlobalSettingKey.RESERVATION_LOCK)
        .values(value=empty_reservation.model_dump_json())
    )
    db_session.execute(stmt)


def promote_user(*, db_session: Session, user_id: int) -> None:
    """Promote the user with the given ID to admin"""
    stmt = sqlalchemy.update(db.User).where(db.User.id == user_id).values(is_admin=True)
    db_session.execute(stmt)


def demote_user(*, db_session: Session, user_id: int) -> None:
    """Demote the user with the given ID from admin"""
    stmt = (
        sqlalchemy.update(db.User).where(db.User.id == user_id).values(is_admin=False)
    )
    db_session.execute(stmt)
