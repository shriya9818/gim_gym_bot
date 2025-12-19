import typing
from functools import wraps

from aiogram import Router, types
from aiogram.filters import Command

import src.db as db
import src.enums as enums
import src.repo as db_repo
import src.services.user as user_services
import src.utils as utils
from src.logger import logger
from src.strings import t

HandlerFunc = typing.Callable[..., typing.Awaitable[typing.Any]]


router = Router()


def user_chat_handler(
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
            if not await utils.ensure_official_chat(message):
                return

            with db.SessionLocal() as db_session:
                db_user = db_repo.does_user_exist(
                    db_session=db_session, telegram_id=user.id
                )

            if not db_user:
                await message.reply(t("messages.unauthorized"))
                return

            return await func(db_user, message, *args, **kwargs)

        return wrapper

    return decorator


def _log_command_result(
    command: enums.UserCommands, user_id: int, ok: bool, message: str
):
    logger.debug(
        "[Result for cmd: {command}, user: {user_id}] is {ok} with message: {message}",
        command=command,
        user_id=user_id,
        ok=ok,
        message=message,
    )


@router.message(Command("help"))
@user_chat_handler("help")
async def cmd_help(db_user: db.User, message: types.Message):
    await message.reply(t("messages.help"))


@router.message(Command(enums.UserCommands.RESERVE))
@user_chat_handler(enums.UserCommands.RESERVE)
async def cmd_reserve(db_user: db.User, message: types.Message):
    with db.SessionLocal() as db_session:
        ok, txt = user_services.create_reservation(
            db_session=db_session, db_user=db_user
        )
        db_session.commit()

    _log_command_result(enums.UserCommands.RESERVE, db_user.telegram_id, ok, txt)
    await message.reply(txt)


@router.message(Command(enums.UserCommands.CHECKIN))
@user_chat_handler(enums.UserCommands.CHECKIN)
async def cmd_checkin(db_user: db.User, message: types.Message):
    with db.SessionLocal() as db_session:
        ok, txt = user_services.checkin_reservation(
            db_session=db_session, db_user=db_user
        )
        db_session.commit()

    _log_command_result(enums.UserCommands.CHECKIN, db_user.telegram_id, ok, txt)
    await message.reply(txt)


@router.message(Command(enums.UserCommands.CHECKOUT))
@user_chat_handler(enums.UserCommands.CHECKOUT)
async def cmd_checkout(db_user: db.User, message: types.Message):
    with db.SessionLocal() as db_session:
        ok, txt = user_services.checkout_reservation(
            db_session=db_session, db_user=db_user
        )
        db_session.commit()

    _log_command_result(enums.UserCommands.CHECKOUT, db_user.telegram_id, ok, txt)
    await message.reply(txt)


@router.message(Command(enums.UserCommands.CANCEL))
@user_chat_handler(enums.UserCommands.CANCEL)
async def cmd_cancel(db_user: db.User, message: types.Message):
    with db.SessionLocal() as db_session:
        ok, txt = user_services.cancel_reservation(
            db_session=db_session, db_user=db_user
        )
        db_session.commit()

    _log_command_result(enums.UserCommands.CANCEL, db_user.telegram_id, ok, txt)
    await message.reply(txt)


@router.message(Command(enums.UserCommands.STATUS))
@user_chat_handler(enums.UserCommands.STATUS)
async def cmd_status(db_user: db.User, message: types.Message):
    with db.SessionLocal() as db_session:
        txt = user_services.user_status(db_session=db_session, db_user=db_user)

    _log_command_result(
        enums.UserCommands.STATUS, db_user.telegram_id, True, "Generated"
    )
    await message.reply(txt)


@router.message(Command(enums.UserCommands.EXPIRING))
@user_chat_handler(enums.UserCommands.EXPIRING)
async def cmd_expiring(db_user: db.User, message: types.Message):
    with db.SessionLocal() as db_session:
        txt = user_services.expiring_sessions(db_session=db_session, db_user=db_user)

    _log_command_result(
        enums.UserCommands.STATUS, db_user.telegram_id, True, "Generated"
    )
    await message.reply(txt)
