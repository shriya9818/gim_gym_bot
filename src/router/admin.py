import typing
from functools import wraps

from aiogram import Router, types
from aiogram.filters import Command

import src.db as db
import src.enums as enums
import src.repo as db_repo
import src.services.admin as admin_services
import src.utils as utils
from src.logger import logger
from src.strings import t

router = Router()


HandlerFunc = typing.Callable[..., typing.Awaitable[typing.Any]]
HandlerFuncNoArgs = typing.Callable[
    [db.User, types.Message], typing.Awaitable[typing.Any]
]
HandlerFuncWithArgs = typing.Callable[
    [db.User, types.Message, str], typing.Awaitable[typing.Any]
]


def _extract_args(message: types.Message) -> str:
    text = message.text or ""
    parts = text.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


@typing.overload
def admin_chat_handler(
    command_name: str, parse_args: typing.Literal[False] = False
) -> typing.Callable[[HandlerFuncNoArgs], HandlerFuncNoArgs]: ...


@typing.overload
def admin_chat_handler(
    command_name: str, parse_args: typing.Literal[True]
) -> typing.Callable[[HandlerFuncWithArgs], HandlerFuncWithArgs]: ...


def admin_chat_handler(
    command_name: str,
    parse_args: bool = False,
) -> typing.Callable[[HandlerFunc], HandlerFunc]:
    """Decorator to log, enforce chat access, and ensure the user is whitelisted.

    Args:
        command_name: The name of the command for logging purposes.
        parse_args: If True, extracts command arguments from the message text and passes them to the handler as a string parameter.
    """

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

            # Extract args if parse_args is True
            extracted_args = _extract_args(message) if parse_args else ""
            with db.SessionLocal() as db_session:
                db_user = db_repo.does_user_exist(
                    db_session=db_session, telegram_id=user.id
                )

            if not db_user:
                await message.reply(t("messages.unauthorized"))
                return

            if not db_user.is_admin and not utils.is_super_user(db_user.telegram_id):
                await message.reply(t("messages.admin_permission"))
                return

            if parse_args:
                return await func(db_user, message, extracted_args, *args, **kwargs)

            return await func(db_user, message, *args, **kwargs)

        return wrapper

    return decorator


def _log_command_result(command: enums.AdminCommands, user_id: int, ok: bool):
    logger.debug(
        "[Result for cmd: {command}, user: {user_id}] is {ok}",
        command=command,
        user_id=user_id,
        ok=ok,
    )


@router.message(Command(enums.AdminCommands.ADMIN_HELP))
@admin_chat_handler(enums.AdminCommands.ADMIN_HELP)
async def cmd_admin_help(db_user: db.User, message: types.Message):
    await message.reply(t("messages.admin_help"))


@router.message(Command(enums.AdminCommands.SUMMARY))
@admin_chat_handler(enums.AdminCommands.SUMMARY)
async def cmd_summary(db_user: db.User, message: types.Message):
    with db.SessionLocal() as db_session:
        ok, txt = admin_services.summarize(db_session=db_session)

    _log_command_result(enums.AdminCommands.SUMMARY, db_user.telegram_id, ok)
    await message.reply(txt)


@router.message(Command(enums.AdminCommands.LOCK))
@admin_chat_handler(enums.AdminCommands.LOCK, parse_args=True)
async def cmd_lock_reservations(db_user: db.User, message: types.Message, reason: str):
    requestor_name = db_user.full_name
    with db.SessionLocal() as db_session:
        ok, txt = admin_services.lock_reservations(
            db_session=db_session,
            name=requestor_name,
            reason=reason,
        )
        db_session.commit()

    _log_command_result(enums.AdminCommands.LOCK, db_user.telegram_id, ok)
    await message.reply(txt)


@router.message(Command(enums.AdminCommands.UNLOCK))
@admin_chat_handler(enums.AdminCommands.UNLOCK)
async def cmd_unlock_reservations(db_user: db.User, message: types.Message):
    with db.SessionLocal() as db_session:
        ok, txt = admin_services.unlock_reservations(db_session=db_session)
        db_session.commit()

    _log_command_result(enums.AdminCommands.UNLOCK, db_user.telegram_id, ok)
    await message.reply(txt)


@router.message(Command(enums.AdminCommands.PROMOTE))
@admin_chat_handler(enums.AdminCommands.PROMOTE, parse_args=True)
async def cmd_promote_admin(db_user: db.User, message: types.Message, identifier: str):
    with db.SessionLocal() as db_session:
        ok, txt = admin_services.promote_user(
            db_session=db_session, identifier=identifier
        )
        db_session.commit()

    _log_command_result(enums.AdminCommands.PROMOTE, db_user.telegram_id, ok)
    await message.reply(txt)


@router.message(Command(enums.AdminCommands.DEMOTE))
@admin_chat_handler(enums.AdminCommands.DEMOTE, parse_args=True)
async def cmd_demote_admin(db_user: db.User, message: types.Message, identifier: str):
    with db.SessionLocal() as db_session:
        ok, txt = admin_services.demote_user(
            db_session=db_session, identifier=identifier
        )
        db_session.commit()

    _log_command_result(enums.AdminCommands.DEMOTE, db_user.telegram_id, ok)
    await message.reply(txt)


@router.message(Command(enums.AdminCommands.ADMINS))
@admin_chat_handler(enums.AdminCommands.ADMINS)
async def cmd_list_admins(db_user: db.User, message: types.Message):
    with db.SessionLocal() as db_session:
        ok, txt = admin_services.list_admins(db_session=db_session)

    _log_command_result(enums.AdminCommands.ADMINS, db_user.telegram_id, ok)
    await message.reply(txt)


@router.message(Command(enums.AdminCommands.USER))
@admin_chat_handler(enums.AdminCommands.USER, parse_args=True)
async def cmd_user_info(db_user: db.User, message: types.Message, identifier: str):
    with db.SessionLocal() as db_session:
        ok, txt = admin_services.user_info(db_session=db_session, identifier=identifier)

    _log_command_result(enums.AdminCommands.USER, db_user.telegram_id, ok)
    await message.reply(txt)
