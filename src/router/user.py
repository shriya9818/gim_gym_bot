import typing
from functools import wraps

from aiogram import Router, types
from aiogram.filters import Command
from sqlalchemy.orm import Session

import src.db as db
import src.enums as enums
import src.repo as db_repo
import src.services.user as user_services
import src.utils as utils
from src.config import CONFIG
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


def _log_command_result(command: enums.UserCommands, user_id: int, ok: bool):
    logger.debug(
        "[Result for cmd: {command}, user: {user_id}] is {ok}",
        command=command,
        user_id=user_id,
        ok=ok,
    )


async def handle_qr_code(
    *,
    db_session: Session,
    db_user: db.User,
    message: types.Message,
    action: enums.QRCodeActions,
) -> str:
    print(action)
    match action:
        case enums.QRCodeActions.CHECKIN:
            result = user_services.checkin_reservation(
                db_session=db_session, db_user=db_user
            )
            action_str = "checked in"
        case enums.QRCodeActions.CHECKOUT:
            result = user_services.checkout_reservation(
                db_session=db_session, db_user=db_user
            )
            action_str = "checked out"
        case enums.QRCodeActions.RESERVE:
            result = user_services.create_reservation(
                db_session=db_session, db_user=db_user
            )
            action_str = "reserved a slot"

    if result.success:
        assert message.bot is not None, "Bot instance is None in message"
        # Send a message to main group about user action
        await message.bot.send_message(
            CONFIG.gym_group_id,
            f"User {db_user.full_name} ({db_user.roll_number}) {action_str} via QR Code.",
        )

    return result.message


@router.message(Command(enums.UserCommands.RESERVE))
@user_chat_handler(enums.UserCommands.RESERVE)
async def cmd_reserve(db_user: db.User, message: types.Message):
    with db.SessionLocal() as db_session:
        ok, txt = user_services.create_reservation(
            db_session=db_session, db_user=db_user
        )
        db_session.commit()

    _log_command_result(enums.UserCommands.RESERVE, db_user.telegram_id, ok)
    await message.reply(txt)


@router.message(Command(enums.UserCommands.CHECKIN))
@user_chat_handler(enums.UserCommands.CHECKIN)
async def cmd_checkin(db_user: db.User, message: types.Message):
    with db.SessionLocal() as db_session:
        ok, txt = user_services.checkin_reservation(
            db_session=db_session, db_user=db_user
        )
        db_session.commit()

    _log_command_result(enums.UserCommands.CHECKIN, db_user.telegram_id, ok)
    await message.reply(txt)


@router.message(Command(enums.UserCommands.CHECKOUT))
@user_chat_handler(enums.UserCommands.CHECKOUT)
async def cmd_checkout(db_user: db.User, message: types.Message):
    with db.SessionLocal() as db_session:
        ok, txt = user_services.checkout_reservation(
            db_session=db_session, db_user=db_user
        )
        db_session.commit()

    _log_command_result(enums.UserCommands.CHECKOUT, db_user.telegram_id, ok)
    await message.reply(txt)


@router.message(Command(enums.UserCommands.CANCEL))
@user_chat_handler(enums.UserCommands.CANCEL)
async def cmd_cancel(db_user: db.User, message: types.Message):
    with db.SessionLocal() as db_session:
        ok, txt = user_services.cancel_reservation(
            db_session=db_session, db_user=db_user
        )
        db_session.commit()

    _log_command_result(enums.UserCommands.CANCEL, db_user.telegram_id, ok)
    await message.reply(txt)


@router.message(Command(enums.UserCommands.STATUS))
@user_chat_handler(enums.UserCommands.STATUS)
async def cmd_status(db_user: db.User, message: types.Message):
    with db.SessionLocal() as db_session:
        ok, txt = user_services.user_status(db_session=db_session, db_user=db_user)

    _log_command_result(enums.UserCommands.STATUS, db_user.telegram_id, ok)
    await message.reply(txt)


@router.message(Command(enums.UserCommands.EXPIRING))
@user_chat_handler(enums.UserCommands.EXPIRING)
async def cmd_expiring(db_user: db.User, message: types.Message):
    with db.SessionLocal() as db_session:
        ok, txt = user_services.expiring_sessions(
            db_session=db_session, db_user=db_user
        )

    _log_command_result(enums.UserCommands.STATUS, db_user.telegram_id, ok)
    await message.reply(txt)
