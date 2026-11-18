"""Спільні дії: видача доступу до каналу та його відкликання."""
import html
import logging
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

import db
from config import ADMIN_ID, CHANNEL_ID, DATE_FORMAT
from keyboards import join_kb


async def create_invite_link(bot: Bot, user_id: int) -> str:
    """Одноразове посилання: діє 24 години і лише для 1 людини."""
    # Якщо людину раніше видалили з каналу — знімаємо блокування
    try:
        await bot.unban_chat_member(CHANNEL_ID, user_id, only_if_banned=True)
    except TelegramBadRequest:
        pass

    link = await bot.create_chat_invite_link(
        chat_id=CHANNEL_ID,
        name=f"user {user_id}",
        member_limit=1,
        expire_date=int((datetime.now() + timedelta(days=1)).timestamp()),
    )
    return link.invite_link


async def grant_access(bot: Bot, user_id: int, days: int, title: str) -> datetime | None:
    """Активує/продовжує підписку і надсилає користувачу посилання в канал."""
    expires = db.activate_subscription(user_id, days)
    try:
        link = await create_invite_link(bot, user_id)
    except TelegramBadRequest as e:
        logging.error("Не вдалося створити посилання: %s", e)
        await bot.send_message(
            ADMIN_ID,
            "⚠️ Не вдалося створити посилання в канал. Перевір, що бот є адміном "
            "каналу з правом «Додавання учасників» і що CHANNEL_ID у .env правильний.",
        )
        link = None

    text = (
        f"{title}\n\n"
        f"✅ Підписка активна до <b>{expires.strftime(DATE_FORMAT)}</b>\n\n"
    )
    try:
        if link:
            text += "Натисни кнопку нижче, щоб увійти в канал.\n" \
                    "⚠️ Посилання одноразове і діє 24 години."
            await bot.send_message(user_id, text, reply_markup=join_kb(link))
        else:
            text += "Посилання в канал надішлемо найближчим часом."
            await bot.send_message(user_id, text)
    except (TelegramForbiddenError, TelegramBadRequest):
        # Користувач ще не запускав бота або заблокував його
        return None
    return expires


async def revoke_access(bot: Bot, user_id: int):
    """Видаляє користувача з каналу (без вічного бану) і вимикає підписку."""
    db.deactivate_subscription(user_id)
    try:
        await bot.ban_chat_member(CHANNEL_ID, user_id)
        await bot.unban_chat_member(CHANNEL_ID, user_id, only_if_banned=True)
    except TelegramBadRequest as e:
        # Наприклад, користувач сам вийшов з каналу або це власник каналу
        logging.warning("Не вдалося видалити %s з каналу: %s", user_id, e)


def user_label(user_id: int) -> str:
    """Ім'я користувача для повідомлень адміну."""
    user = db.get_user(user_id)
    if not user:
        return f"<code>{user_id}</code>"
    username = f" (@{user['username']})" if user["username"] else ""
    return f"{html.escape(user['full_name'])}{username}, ID <code>{user_id}</code>"
