import typing

import pydantic


class JoinFormRequest(pydantic.BaseModel):
    user_id: int
    username: str | None
    roll_number: str
    full_name: str
    phone_number: str


class UserCreateRequest(pydantic.BaseModel):
    telegram_id: int
    roll_number: str
    username: str | None
    full_name: str
    phone_number: str


class ReservationLockState(pydantic.BaseModel):
    is_locked: bool
    locked_by: str
    reason: str


class CommandResult(typing.NamedTuple):
    success: bool
    message: str


class UserReservationsStats(typing.NamedTuple):
    user_id: int
    total_reservations: int
    no_shows: int
    overstays: int
