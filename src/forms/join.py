import re
import typing
from datetime import timedelta

from aiogram import Bot, F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import src.db as db
import src.enums as enums
import src.models as models
import src.repo as db_repo
import src.utils as utils
from src.config import CONFIG
from src.logger import logger
from src.strings import t

router = Router()


class JoinForm(StatesGroup):
    waiting_name = State()
    waiting_roll = State()
    waiting_phone = State()


async def ensure_join_private_chat(message: types.Message) -> bool:
    if message.chat.type == "private":
        return True

    await message.reply(t("join.dm_required"))
    return False


@router.message(Command("join"))
async def cmd_join(message: types.Message, state: FSMContext):
    if not await ensure_join_private_chat(message):
        return

    user = utils.assert_user_id(message.from_user)
    with db.SessionLocal() as db_session:
        latest = db_repo.get_latest_join_request(
            db_session=db_session, telegram_id=user.id
        )
        if latest is None or latest.status == enums.JoinRequestStatus.REJECTED:
            await state.update_data(user_id=user.id, username=user.username)
            await state.set_state(JoinForm.waiting_name)
            await message.reply(t("join.ask_name"))
            return

        if latest.status == enums.JoinRequestStatus.APPROVED:
            await message.reply(t("join.already_approved"))
        else:
            await message.reply(t("join.already_pending"))


@router.message(JoinForm.waiting_name)
async def join_collect_name(message: types.Message, state: FSMContext):
    if not await ensure_join_private_chat(message):
        return

    name = (message.text or "").strip()
    if len(name) < 5:
        await message.reply(t("join.invalid_name"))
        return

    await state.update_data(full_name=name)
    await state.set_state(JoinForm.waiting_roll)
    await message.reply(t("join.ask_roll"))


@router.message(JoinForm.waiting_roll)
async def join_collect_roll(message: types.Message, state: FSMContext):
    if not await ensure_join_private_chat(message):
        return

    roll = (message.text or "").strip()
    if not re.fullmatch(r"[A-Z][0-9]{3,12}", roll):
        await message.reply(t("join.invalid_roll"))
        return

    with db.SessionLocal() as db_session:
        existing = db_repo.get_user(
            db_session=db_session, telegram_id=None, roll_number=roll
        )
        if existing:
            await message.reply(t("join.roll_exists"))
            return

    await state.update_data(roll_number=roll)
    await state.set_state(JoinForm.waiting_phone)
    await message.reply(t("join.ask_phone"))


def sanitize_form_data(data: dict[str, typing.Any]) -> models.JoinFormRequest:
    user_id = data.get("user_id")
    full_name = data.get("full_name", "").strip()
    roll_number = data.get("roll_number", "").strip().upper()
    phone_number = data.get("phone_number", "").strip()
    username = data.get("username", None)

    return models.JoinFormRequest(
        user_id=typing.cast(int, user_id),
        username=username,
        roll_number=roll_number,
        full_name=full_name,
        phone_number=phone_number,
    )


async def send_admin_approval_request(
    message: types.Message, join_request_id: int, form_data: models.JoinFormRequest
) -> None:
    admin_text = t(
        "join.admin_message",
        name=form_data.full_name,
        roll=form_data.roll_number,
        phone=form_data.phone_number,
        username=form_data.username or "N/A",
        user_id=form_data.user_id,
    )
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=t("join.admin_button_approve"),
                    callback_data=f"join:approve:{join_request_id}",
                ),
                types.InlineKeyboardButton(
                    text=t("join.admin_button_decline"),
                    callback_data=f"join:decline:{join_request_id}",
                ),
            ]
        ]
    )
    assert message.bot is not None, "Bot instance is None in message"
    admin_message = await message.bot.send_message(
        CONFIG.admin_group_id, admin_text, reply_markup=keyboard
    )
    with db.SessionLocal() as db_session:
        db_repo.update_join_request(
            db_session=db_session,
            join_request_id=join_request_id,
            admin_message_id=admin_message.message_id,
            admin_chat_id=admin_message.chat.id,
        )
        db_session.commit()

    await message.reply(t("join.submitted"))


@router.message(JoinForm.waiting_phone)
async def join_collect_phone(message: types.Message, state: FSMContext):
    if not await ensure_join_private_chat(message):
        return

    phone = re.sub(r"\D", "", message.text or "")
    if len(phone) != 10:
        await message.reply(t("join.invalid_phone"))
        return

    await state.update_data(phone_number=phone)
    form_data = sanitize_form_data(await state.get_data())
    with db.SessionLocal() as db_session:
        pending_request = db_repo.get_latest_join_request(
            db_session=db_session, telegram_id=form_data.user_id
        )
        # Use may have submitted while filling the another form
        if (
            pending_request
            and pending_request.status == enums.JoinRequestStatus.PENDING
        ):
            await state.clear()
            await message.reply(t("join.already_pending"))
            return

        inserted_id = db_repo.create_join_request(
            db_session=db_session, form_data=form_data
        )

    # Clear state once the request is created
    await state.clear()
    await send_admin_approval_request(message, inserted_id, form_data)


@router.callback_query(F.data.startswith("join:"))
async def join_decision(callback: types.CallbackQuery):
    assert callback.message is not None, "Callback message is None"
    assert isinstance(
        callback.message, types.Message
    ), "Callback message is not of type Message"
    assert callback.message.text is not None, "Callback message text is None"
    assert callback.bot is not None, "Callback bot is None"

    if callback.message.chat.id != CONFIG.admin_group_id:
        await callback.answer()
        return

    assert callback.data is not None, "Callback data is None"
    parts = callback.data.split(":")
    # Expecting join:approve:<id> or join:decline:<id>
    if len(parts) != 3:
        await callback.answer()
        return

    action, request_id = parts[1], int(parts[2])
    user = utils.assert_user_id(callback.from_user)
    with db.SessionLocal() as db_session:
        db_user = db_repo.get_user(
            db_session=db_session, telegram_id=user.id, roll_number=None
        )
        if not db_user:
            await callback.answer(t("messages.unauthorized"))
            return

        if not db_user.is_admin:
            await callback.answer(t("messages.admin_permission"), show_alert=True)
            return

        req = db_repo.get_join_request(
            db_session=db_session, join_request_id=request_id
        )
        # If the request does not exist, we cannot proceed
        if not req:
            await callback.answer(t("join.invalid_request"), show_alert=True)
            return

        # If the request is already processed, inform the admin
        if req.status != enums.JoinRequestStatus.PENDING:
            await callback.answer(t("join.already_processed"), show_alert=True)
            return

        if req.created_at < utils.utc_now() - timedelta(hours=24):
            # Notify user about expiration
            await callback.answer(t("join.decision_user_expired"), show_alert=True)
            await callback.message.edit_text(
                callback.message.text
                + "\n\n"
                + t(
                    "join.decision_admin_text",
                    status="Expired automatically",
                    actor=callback.from_user.full_name,
                )
            )
            db_repo.update_join_request(
                db_session=db_session,
                join_request_id=req.id,
                status=enums.JoinRequestStatus.EXPIRED,
            )
            db_session.commit()
            return

        if action == "approve":
            status = enums.JoinRequestStatus.APPROVED
            user_req = models.UserCreateRequest(
                telegram_id=req.user_id,
                roll_number=req.roll_number,
                username=None,
                full_name=req.full_name,
                phone_number=req.phone_number,
            )
            db_repo.create_invited_user(db_session=db_session, req=user_req)
        else:
            status = enums.JoinRequestStatus.REJECTED

        db_repo.update_join_request(
            db_session=db_session, join_request_id=req.id, status=status
        )
        db_session.commit()

    await callback.message.edit_text(
        callback.message.text
        + "\n\n"
        + t(
            "join.decision_admin_text",
            status=status.capitalize(),
            actor=callback.from_user.full_name,
        )
    )
    if action == "approve":
        await callback.bot.send_message(
            req.user_id,
            t("join.decision_user_approved"),
        )
        await send_invite_link(callback.bot, req.user_id)
    else:
        await callback.bot.send_message(req.user_id, t("join.decision_user_declined"))
    await callback.answer()


async def send_invite_link(bot: Bot, user_id: int) -> bool:
    try:
        expire = utils.utc_now() + timedelta(hours=24)
        invite = await bot.create_chat_invite_link(
            CONFIG.gym_group_id,
            expire_date=int(expire.timestamp()),
            member_limit=1,
        )
        await bot.send_message(
            user_id,
            t("join.invite_link_message", link=invite.invite_link),
        )
        return True
    except Exception as e:
        logger.error("Failed to create/send invite link: {reason}", reason=str(e))
        await bot.send_message(user_id, t("join.missing_link_permission"))
        return False
