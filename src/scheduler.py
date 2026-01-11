import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from loguru import logger

import src.db as db
import src.enums as enums
import src.utils as utils
from src.config import CONFIG

sched = BackgroundScheduler(timezone=CONFIG.timezone)


def expire_reservations() -> None:
    now = utils.utc_now()
    cutoff_time = now - datetime.timedelta(minutes=CONFIG.reserve_window_minutes)
    with db.SessionLocal() as db_session:
        expired_reservations = (
            db_session.query(db.Reservations)
            .filter(
                db.Reservations.state == enums.ReservationState.RESERVED,
                db.Reservations.reservation_expiry_time <= cutoff_time,
            )
            .all()
        )
        if expired_reservations:
            logger.info(
                "Found {count} reservations to expire", count=len(expired_reservations)
            )

        for reservation in expired_reservations:
            reservation.state = enums.ReservationState.EXPIRED
            reservation.is_no_show = True
            db_session.add(reservation)
            logger.debug(
                "Expiring Reservation for user: {full_name}, reserved at {reserved_at}",
                full_name=reservation.user.full_name,
                reserved_at=reservation.reservation_expiry_time,
            )

        db_session.commit()


def expire_overdue_checkins():
    now = utils.utc_now()
    cutoff_time = now - datetime.timedelta(minutes=CONFIG.session_duration_minutes)
    with db.SessionLocal() as db_session:
        overdue_checkins = (
            db_session.query(db.Reservations)
            .filter(
                db.Reservations.state == enums.ReservationState.CHECKED_IN,
                db.Reservations.max_checkout_time <= cutoff_time,
            )
            .all()
        )
        if overdue_checkins:
            logger.info("Found {count} overdue check-ins", count=len(overdue_checkins))

        for reservation in overdue_checkins:
            reservation.state = enums.ReservationState.EXPIRED
            db_session.add(reservation)
            logger.debug(
                "Overdue Reservation for user: {full_name}, checked in at {checkin_time}",
                full_name=reservation.user.full_name,
                checkin_time=reservation.checkin_time,
            )

        db_session.commit()


def start():
    sched.add_job(expire_reservations, "interval", minutes=1, id="expire_reservations")
    sched.add_job(
        expire_overdue_checkins, "interval", minutes=1, id="expire_overdue_checkins"
    )
    sched.start()
