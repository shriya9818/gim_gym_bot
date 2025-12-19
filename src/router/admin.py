import typing
from functools import wraps

from aiogram import Router, types
from aiogram.filters import Command
from sqlalchemy import select

import src.db as db
import src.enums as enums
import src.repo as db_repo
import src.services.admin as admin_services
import src.utils as utils
from src.logger import logger
from src.strings import t

router = Router()


HandlerFunc = typing.Callable[..., typing.Awaitable[typing.Any]]


def admin_chat_handler(
    command_name: str,
) -> typing.Callable[[HandlerFunc], HandlerFunc]:
    """Decorator to log, enforce chat access, and ensure the user is whitelisted."""

    def decorator(func: HandlerFunc) -> HandlerFunc:
        @wraps(func)
        async def wrapper(message: types.Message, *args, **kwargs):
            user = utils.assert_user_id(message.from_user)
            logger.debug(
                "[Request for cmd: {command_name}, user: {user_id}]",
                command_name=command_name,
                user_id=user.id,
            )
            if not await utils.ensure_admin_chat(message):
                return

            with db.SessionLocal() as db_session:
                db_user = db_repo.does_user_exist(
                    db_session=db_session, telegram_id=user.id
                )

            if not db_user:
                await message.reply(t("messages.unauthorized"))
                return

            if not db_user.is_admin:
                await message.reply(t("messages.admin_permission"))
                return

            return await func(db_user, message, *args, **kwargs)

        return wrapper

    return decorator


def _extract_args(message: types.Message) -> str:
    text = message.text or ""
    parts = text.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


@router.message(Command(enums.AdminCommands.SUMMARY))
@admin_chat_handler(enums.AdminCommands.SUMMARY)
async def cmd_summary(db_user: db.User, message: types.Message):
    with db.SessionLocal() as db_session:
        report = admin_services.summarize(db_session=db_session)

    await message.reply(report)


@router.message(Command(enums.AdminCommands.LOCK))
@admin_chat_handler(enums.AdminCommands.SUMMARY)
async def cmd_lock_reservations(db_user: db.User, message: types.Message):
    args = None
    reason = _extract_args(message)
    text = lock_reservations(
        getattr(message.from_user, "id", None),
        reason or "Gym temporarily unavailable.",
    )
    await message.reply(text)


@router.message(Command("invite"))
async def cmd_invite(message: types.Message):
    if message.chat.type != "private":
        return
    with SessionLocal() as db:
        user = (
            db.execute(select(User).where(User.telegram_id == message.from_user.id))
            .scalars()
            .first()
        )
        pending = get_pending_join_request(db, message.from_user.id)
    if user:
        await message.reply(t("messages.invite_registered"))
        await send_invite_link(message.bot, message.from_user.id)
        return
    if pending:
        await message.reply(t("messages.invite_pending"))
        return
    await message.reply(t("messages.start_not_registered"))


@router.message(Command("user"))
async def cmd_user(message: types.Message):
    if not await ensure_admin_chat(message):
        return
    identifier = _extract_args(message)
    if not identifier:
        await message.reply(t("admin.user_usage"))
        return
    ok, txt = user_report(identifier)
    await message.reply(txt if ok else f"Error: {txt}")


@router.message(Command("force_checkout"))
async def cmd_force_checkout(message: types.Message):
    if not await ensure_admin_chat(message):
        return
    identifier = _extract_args(message)
    if not identifier:
        await message.reply(t("admin.force_checkout_usage"))
        return
    ok, txt = force_checkout_user(identifier)
    await message.reply(txt if ok else f"Error: {txt}")


@router.message(Command("block"))
async def cmd_block(message: types.Message):
    if not await ensure_admin_chat(message):
        return
    args = _extract_args(message)
    if not args:
        await message.reply(t("admin.block_usage"))
        return
    parts = args.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply(t("admin.block_usage"))
        return
    identifier, duration = parts
    ok, txt = block_user(identifier, duration)
    await message.reply(txt if ok else f"Error: {txt}")


@router.message(Command("unblock"))
async def cmd_unblock(message: types.Message):
    if not await ensure_admin_chat(message):
        return
    identifier = _extract_args(message)
    if not identifier:
        await message.reply(t("admin.unblock_usage"))
        return
    ok, txt = unblock_user(identifier)
    await message.reply(txt if ok else f"Error: {txt}")


@router.message(Command("unlock_reservations"))
async def cmd_unlock_reservations(message: types.Message):
    if not await ensure_admin_chat(message):
        return
    text = unlock_reservations()
    await message.reply(text)


@router.message(Command("promote_admin"))
async def cmd_promote_admin(message: types.Message):
    if not await ensure_admin_chat(message):
        return
    identifier = _extract_args(message)
    if not identifier:
        await message.reply(t("admin.promote_usage"))
        return
    ok, txt = add_admin(identifier)
    await message.reply(txt if ok else f"Error: {txt}")


@router.message(Command("revoke_admin"))
async def cmd_revoke_admin(message: types.Message):
    if not await ensure_admin_chat(message):
        return
    identifier = _extract_args(message)
    if not identifier:
        await message.reply(t("admin.revoke_usage"))
        return
    ok, txt = remove_admin(identifier)
    await message.reply(txt if ok else f"Error: {txt}")
