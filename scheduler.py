"""Фонова задача: нагадування про закінчення підписки та видалення з каналу."""
import asyncio
import math
import logging
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

import db
from config import ADMIN_ID, CHECK_INTERVAL, DATE_FORMAT
from keyboards import renew_kb
from services import revoke_access, user_label


async def _notify(bot: Bot, user_id: int, text: str):
    try:
        await bot.send_message(user_id, text, reply_markup=renew_kb())
    except (TelegramForbiddenError, TelegramBadRequest):
        pass  # користувач заблокував бота


async def check_subscriptions(bot: Bot):
    now = datetime.now()
    for sub in db.active_subscriptions():
        user_id = sub["user_id"]
        expires = datetime.fromisoformat(sub["expires_at"])
        left = expires - now

        if left <= timedelta(0):
            await revoke_access(bot, user_id)
            await _notify(
                bot, user_id,
                "⌛ Твоя підписка закінчилась, доступ до каналу закрито.\n\n"
                "Продовж підписку, щоб повернутися 👇",
            )
            await bot.send_message(ADMIN_ID, f"⌛ Підписка закінчилась: {user_label(user_id)}")

        elif left <= timedelta(days=1) and not sub["reminded_1"]:
            await _notify(
                bot, user_id,
                f"⏰ Підписка закінчується <b>менш ніж за добу</b> — {expires.strftime(DATE_FORMAT)}.\n"
                "Не забудь продовжити, щоб не втратити доступ!",
            )
            db.mark_reminded(user_id, 1)
            db.mark_reminded(user_id, 3)

        elif left <= timedelta(days=3) and not sub["reminded_3"]:
            await _notify(
                bot, user_id,
                f"🔔 Нагадування: підписка діє до <b>{expires.strftime(DATE_FORMAT)}</b> "
                f"(залишилось {math.ceil(left.total_seconds() / 86400)} дн.).\n"
                "Продовж зараз, щоб не втратити доступ до каналу.",
            )
            db.mark_reminded(user_id, 3)


async def subscription_checker(bot: Bot):
    """Нескінченний цикл: перевіряє підписки кожні CHECK_INTERVAL секунд."""
    while True:
        try:
            await check_subscriptions(bot)
        except Exception:
            logging.exception("Помилка під час перевірки підписок")
        await asyncio.sleep(CHECK_INTERVAL)
