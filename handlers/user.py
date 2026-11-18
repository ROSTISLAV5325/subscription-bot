import math
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import db
from config import (ADMIN_ID, CARD_NUMBER, CARD_OWNER, CHANNEL_DESCRIPTION,
                    DATE_FORMAT, TARIFFS)
from keyboards import (BTN_ABOUT, BTN_MY_SUB, BTN_TARIFFS, cancel_payment_kb,
                       join_kb, main_kb, my_sub_kb, pay_method_kb, review_kb,
                       tariffs_kb)
from services import create_invite_link, user_label

router = Router()


class CardPayment(StatesGroup):
    receipt = State()  # чекаємо фото/PDF квитанції


TARIFFS_TEXT = "💎 <b>Обери тариф:</b>\n\nОплатити можна через Telegram Stars або переказом на картку."


# ---------- Головне меню ----------

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user = message.from_user
    db.add_user(user.id, user.username, user.full_name)

    text = (
        f"Привіт, {user.first_name}! 👋\n\n"
        "Тут можна оформити підписку на наш <b>закритий канал</b>.\n"
        "Після оплати бот автоматично надішле тобі посилання для входу."
    )
    if user.id == ADMIN_ID:
        text += "\n\n🔧 Ти адміністратор. Панель керування — команда /admin"
    await message.answer(text, reply_markup=main_kb())


@router.message(F.text == BTN_ABOUT)
async def about(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(CHANNEL_DESCRIPTION)


@router.message(F.text == BTN_TARIFFS)
async def show_tariffs(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(TARIFFS_TEXT, reply_markup=tariffs_kb())


@router.callback_query(F.data == "show_tariffs")
async def show_tariffs_cb(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer(TARIFFS_TEXT, reply_markup=tariffs_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("tariff:"))
async def choose_tariff(callback: CallbackQuery):
    key = callback.data.split(":")[1]
    t = TARIFFS[key]
    await callback.message.edit_text(
        f"Тариф: <b>{t['title']}</b>\n"
        f"Ціна: <b>{t['price_uah']} грн</b> або <b>{t['stars']} ⭐</b>\n\n"
        "Обери спосіб оплати:",
        reply_markup=pay_method_kb(key),
    )
    await callback.answer()


# ---------- Моя підписка ----------

@router.message(F.text == BTN_MY_SUB)
async def my_subscription(message: Message, state: FSMContext):
    await state.clear()
    sub = db.get_subscription(message.from_user.id)
    active = db.is_active(message.from_user.id)

    if active:
        expires = datetime.fromisoformat(sub["expires_at"])
        days_left = math.ceil((expires - datetime.now()).total_seconds() / 86400)
        text = (
            "👤 <b>Твоя підписка</b>\n\n"
            "Статус: ✅ активна\n"
            f"Діє до: <b>{expires.strftime(DATE_FORMAT)}</b>\n"
            f"Залишилось днів: <b>{days_left}</b>"
        )
    elif sub:
        text = "👤 <b>Твоя підписка</b>\n\nСтатус: ❌ закінчилась\n\nПродовж її, щоб повернутися в канал."
    else:
        text = "👤 <b>Твоя підписка</b>\n\nУ тебе ще немає підписки."
    await message.answer(text, reply_markup=my_sub_kb(active))


@router.callback_query(F.data == "get_link")
async def get_link(callback: CallbackQuery, bot: Bot):
    if not db.is_active(callback.from_user.id):
        await callback.answer("Підписка неактивна", show_alert=True)
        return
    try:
        link = await create_invite_link(bot, callback.from_user.id)
    except TelegramBadRequest:
        await callback.answer("Не вдалося створити посилання. Спробуй пізніше.", show_alert=True)
        return
    await callback.message.answer(
        "🔗 Твоє нове посилання в канал.\n⚠️ Одноразове, діє 24 години.",
        reply_markup=join_kb(link),
    )
    await callback.answer()


# ---------- Оплата переказом на картку ----------

@router.callback_query(F.data.startswith("pay_card:"))
async def pay_card(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split(":")[1]
    t = TARIFFS[key]
    await state.set_state(CardPayment.receipt)
    await state.update_data(tariff_key=key)
    await callback.message.edit_text(
        f"💳 <b>Оплата переказом</b>\n\n"
        f"Тариф: <b>{t['title']}</b>\n"
        f"Сума: <b>{t['price_uah']} грн</b>\n\n"
        f"Номер картки: <code>{CARD_NUMBER}</code>\n"
        f"Отримувач: {CARD_OWNER}\n\n"
        "Після оплати надішли сюди <b>фото або PDF квитанції</b>.\n"
        "Адміністратор перевірить оплату, і бот надішле посилання в канал.",
        reply_markup=cancel_payment_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "cancel_pay")
async def cancel_payment(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Оплату скасовано.")
    await callback.answer()


@router.message(CardPayment.receipt, F.photo | F.document)
async def receive_receipt(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    key = data["tariff_key"]
    t = TARIFFS[key]
    file_id = message.photo[-1].file_id if message.photo else message.document.file_id

    payment_id = db.create_payment(
        user_id=message.from_user.id, tariff_key=key, method="card",
        status="pending", amount_uah=t["price_uah"], receipt_file_id=file_id,
    )
    await state.clear()

    await message.answer(
        "✅ Квитанцію отримано!\n\n"
        "Адміністратор перевірить оплату найближчим часом — "
        "щойно це станеться, бот надішле тобі посилання в канал."
    )

    # Надсилаємо квитанцію адміну на перевірку
    caption = (
        f"🧾 <b>Нова оплата #{payment_id}</b>\n\n"
        f"Від: {user_label(message.from_user.id)}\n"
        f"Тариф: {t['title']}\n"
        f"Сума: {t['price_uah']} грн"
    )
    if message.photo:
        await bot.send_photo(ADMIN_ID, file_id, caption=caption, reply_markup=review_kb(payment_id))
    else:
        await bot.send_document(ADMIN_ID, file_id, caption=caption, reply_markup=review_kb(payment_id))


@router.message(CardPayment.receipt)
async def receipt_wrong_type(message: Message):
    await message.answer(
        "Надішли, будь ласка, <b>фото або PDF</b> квитанції.",
        reply_markup=cancel_payment_kb(),
    )
