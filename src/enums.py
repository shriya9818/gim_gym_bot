from enum import Enum


class StrEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


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
    ADMIN_HELP = "admin-help"
    SUMMARY = "summary"
    LOCK = "lock"
    UNLOCK = "unlock"
    PROMOTE = "promote"
    DEMOTE = "demote"
    ADMINS = "admins"
    USER = "user"
