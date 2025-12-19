from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from .config import CONFIG
from .db import SessionLocal
from .enums import ReservationState
from .logger import logger
from .storage import find_expired_reservations, find_overdue_checkins

sched = BackgroundScheduler(timezone=CONFIG.timezone)


def _expire_reservations():
    now = datetime.utcnow()
    with SessionLocal() as db:
        expired = find_expired_reservations(db, now)
        logger.debug("expire_reservations job running", found=len(expired), time=now)
        for s in expired:
            logger.debug("expiring reservation", session_id=s.id, user_id=s.user_id)
            s.state = ReservationState.EXPIRED
            s.is_no_show = True
            db.add(s)
        db.commit()


def _auto_checkout():
    now = datetime.utcnow()
    with SessionLocal() as db:
        overdue = find_overdue_checkins(db, now)
        logger.debug("auto_checkout job running", found=len(overdue), time=now)
        for s in overdue:
            logger.debug("auto-checkout session", session_id=s.id, user_id=s.user_id)
            s.state = ReservationState.CHECKED_OUT
            s.did_overstay = True
            s.checkout_time = now
            db.add(s)
        db.commit()


def start():
    sched.add_job(_expire_reservations, "interval", minutes=1, id="expire_reservations")
    sched.add_job(_auto_checkout, "interval", minutes=1, id="auto_checkout")
    sched.start()
