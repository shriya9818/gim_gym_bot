from enum import StrEnum


class ReservationState(StrEnum):
    RESERVED = "reserved"
    CHECKED_IN = "checked_in"
    CHECKED_OUT = "checked_out"
    EXPIRED = "expired"


class JoinRequestStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class GlobalSettingKey(StrEnum):
    RESERVATION_LOCK = "reservation_lock"


class UserCommands(StrEnum):
    HELP = "help"
    START = "start"
    INVITE = "invite"
    RESERVE = "reserve"
    CHECKIN = "checkin"
    CHECKOUT = "checkout"
    CANCEL = "cancel"
    STATUS = "status"
    EXPIRING = "expiring"


class AdminCommands(StrEnum):
    SUMMARY = "summary"
    LOCK = "lock"
    UNLOCK = "unlock"
