"""Оплата через Telegram Stars (вбудована оплата Telegram)."""
from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery

import db
from config import ADMIN_ID, DATE_FORMAT, TARIFFS
from services import grant_access, user_label

router = Router()


@router.callback_query(F.data.startswith("pay_stars:"))
async def pay_stars(callback: CallbackQuery):
    key = callback.data.split(":")[1]
    t = TARIFFS[key]
    # Для Telegram Stars валюта завжди XTR, провайдер оплати не потрібен
    await callback.message.answer_invoice(
        title=f"Підписка: {t['title']}",
        description=f"Доступ до закритого каналу на {t['days']} днів",
        payload=f"sub:{key}",
        currency="XTR",
        prices=[LabeledPrice(label=t["title"], amount=t["stars"])],
    )
    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    # Telegram питає: «Можна проводити оплату?» — перевіряємо, що тариф існує
    key = query.invoice_payload.split(":")[-1]
    if key in TARIFFS:
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="Тариф не знайдено. Спробуй ще раз.")


@router.message(F.successful_payment)
async def successful_payment(message: Message, bot: Bot):
    payment = message.successful_payment
    key = payment.invoice_payload.split(":")[-1]
    t = TARIFFS[key]

    payment_id = db.create_payment(
        user_id=message.from_user.id, tariff_key=key, method="stars",
        status="approved", stars=payment.total_amount,
        charge_id=payment.telegram_payment_charge_id,
    )
    expires = await grant_access(bot, message.from_user.id, t["days"], "🎉 Оплату отримано, дякуємо!")

    until = expires.strftime(DATE_FORMAT) if expires else "—"
    await bot.send_message(
        ADMIN_ID,
        f"⭐ <b>Нова оплата Stars #{payment_id}</b>\n\n"
        f"Від: {user_label(message.from_user.id)}\n"
        f"Тариф: {t['title']} — {payment.total_amount} ⭐\n"
        f"Підписка до: {until}",
    )
