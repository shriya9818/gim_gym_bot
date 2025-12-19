from aiogram import Router, types
from aiogram.filters import Command

import src.db as db
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


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    # Ignore non-private chats for /start
    if message.chat.type != "private":
        return

    user = utils.assert_user_id(message.from_user)
    logger.debug("Start command for user: {user_id} with username: {username}")

    with db.SessionLocal() as db_session:
        db_user = db_repo.does_user_exist(db_session=db_session, telegram_id=user.id)
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
