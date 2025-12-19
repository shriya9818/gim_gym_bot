from datetime import datetime, timezone

import arrow
from aiogram import types

import src.db as db
from src.config import CONFIG
from src.logger import logger
from src.strings import t


def is_official_chat(chat_id: int) -> bool:
    """Return True if message originates from the configured gym group"""
    return chat_id == CONFIG.gym_group_id


def is_admin_chat(chat_id: int) -> bool:
    """Return True if message originates from the configured admin group"""
    return chat_id == CONFIG.admin_group_id


def is_super_user(telegram_id: int) -> bool:
    """Return True if the given telegram ID is a super user"""
    return telegram_id in CONFIG.super_users


def assert_user_id(from_user: types.User | None) -> types.User:
    if from_user is None:
        raise ValueError("Message has no from_user")

    return from_user


async def ensure_official_chat(message: types.Message) -> bool:
    if is_official_chat(message.chat.id):
        return True

    logger.debug(
        "blocked command from non-official chat: {chat_id} from user: {user_id}",
        chat_id=message.chat.id,
        user_id=getattr(message.from_user, "id", None),
    )

    await message.reply(t("messages.non_official_chat"))
    return False


async def ensure_admin_chat(message: types.Message) -> bool:
    if is_admin_chat(message.chat.id):
        return True

    logger.debug(
        "blocked command from non-admin chat: {chat_id} from user: {user_id}",
        chat_id=message.chat.id,
        user_id=getattr(message.from_user, "id", None),
    )

    await message.reply(t("messages.admin_chat_only"))
    return False


def utc_now() -> datetime:
    """Return the current UTC time"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def humanize_time(dt: datetime) -> str:
    """Return a human-readable string for the given datetime"""
    arrow_datetime = arrow.get(dt)
    return arrow_datetime.humanize(locale="en_us", only_distance=True)


def humanize_duration(dt: datetime) -> str:
    """Return a human-readable string for the given datetime"""
    arrow_datetime = arrow.get(dt)
    distance = arrow_datetime.humanize(locale="en_us", only_distance=True)
    verb = "left" if arrow.now() < arrow_datetime else "ago"
    return f"{distance} {verb}"


def format_user(user: db.User) -> str:
    return f"{user.full_name} (roll: {user.roll_number})"
