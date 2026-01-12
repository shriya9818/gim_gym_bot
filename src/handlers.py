from aiogram import Router, types
from aiogram.filters import Command, CommandObject, CommandStart

import src.db as db
import src.enums as enums
import src.forms.join as forms_join
import src.repo as db_repo
import src.router.admin as admin_router
import src.router.user as user_router
import src.utils as utils
from src.logger import logger

from .strings import t

router = Router()

router.include_router(forms_join.router)
router.include_router(user_router.router)
router.include_router(admin_router.router)


@router.message(Command(enums.UserCommands.HELP))
async def cmd_help(message: types.Message):
    reply = t("messages.help")
    if message.chat.type == "private":
        reply = "Below commands can only be used in group chats.\n\n" + reply

    await message.reply(reply)


@router.message(CommandStart())
async def cmd_start(message: types.Message, command: CommandObject):
    # Ignore non-private chats for /start
    if message.chat.type != "private":
        return message.reply(t("errors.private_only"))

    user = utils.assert_user_id(message.from_user)
    print("hello")
    logger.debug(f"Start command for user: {user.id} with username: {user.username}")

    args = command.args
    action: enums.QRCodeActions | None = None
    try:
        action = enums.QRCodeActions(args) if args else None
    except ValueError:
        logger.warning("Invalid deep link argument: {args}", args=args)
        pass

    with db.SessionLocal() as db_session:
        db_user = db_repo.does_user_exist(db_session=db_session, telegram_id=user.id)

        # Handle deep link arguments for existing users
        if db_user is not None and action is not None:
            # User exists and has provided a deep link argument -> checkin, checkout or reserve
            reply = await user_router.handle_qr_code(
                db_session=db_session, db_user=db_user, message=message, action=action
            )
            db_session.commit()
            return await message.reply(reply)

        # If the user does not exist -> we should check for pending join requests
        user_pending_join = (
            db_repo.is_user_pending_join(db_session=db_session, telegram_id=user.id)
            if db_user is None
            else False
        )

        if db_user is not None:
            status_text = t(
                "messages.start_registered",
                name=db_user.full_name or "Unknown",
                roll=db_user.roll_number,
            )
        elif user_pending_join:
            status_text = t("messages.start_pending")
        else:
            status_text = t("messages.start_not_registered")

    intro = t("messages.start_intro")
    await message.reply(f"{intro}\n\n{status_text}")
