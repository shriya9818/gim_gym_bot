from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.orm import mapped_column, relationship, sessionmaker
from sqlalchemy.sql import func

import src.enums as enums
from src.config import CONFIG


class Base(DeclarativeBase):
    pass


engine = create_engine(
    CONFIG.database_path,
    future=True,
    connect_args=(
        {"check_same_thread": False}
        if CONFIG.database_path.startswith("sqlite")
        else {}
    ),
)

SessionLocal = sessionmaker(bind=engine, class_=OrmSession, expire_on_commit=False)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)

    roll_number: Mapped[str] = mapped_column(String, unique=True)
    username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    full_name: Mapped[str] = mapped_column(String)
    phone_number: Mapped[str] = mapped_column(String)

    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    block_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    sessions: Mapped[List["Reservations"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Reservations(Base, TimestampMixin):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    state: Mapped[enums.ReservationState] = mapped_column(
        Enum(enums.ReservationState, name="reservation_state", native_enum=False)
    )
    reservation_time: Mapped[datetime] = mapped_column(DateTime)
    reservation_expiry_time: Mapped[datetime] = mapped_column(DateTime)

    checkin_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    checkout_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    max_checkout_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    is_no_show: Mapped[bool] = mapped_column(Boolean, default=False)
    did_overstay: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship(back_populates="sessions")


# TODO: Make it a enum for the key fields
class BotSetting(Base, TimestampMixin):
    __tablename__ = "bot_settings"

    key: Mapped[enums.GlobalSettingKey] = mapped_column(
        Enum(enums.GlobalSettingKey, name="global_setting_key", native_enum=False),
        primary_key=True,
    )
    value: Mapped[str] = mapped_column(Text)


class JoinRequest(Base, TimestampMixin):
    __tablename__ = "join_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    roll_number: Mapped[str] = mapped_column(String, nullable=False)
    phone_number: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[enums.JoinRequestStatus] = mapped_column(
        Enum(enums.JoinRequestStatus, name="join_request_status", native_enum=False),
        default=enums.JoinRequestStatus.PENDING,
    )
    approver_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    admin_chat_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    admin_message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


__all__ = [
    "engine",
    "SessionLocal",
    "Base",
    "User",
    "Reservations",
    "BotSetting",
    "JoinRequest",
    "init_db",
]
