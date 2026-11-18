import asyncio
import html
from datetime import datetime, timedelta

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import db
from config import ADMIN_ID, DATE_FORMAT, TARIFFS
from keyboards import admin_cancel_kb, admin_kb, broadcast_confirm_kb, review_kb
from services import grant_access, revoke_access, user_label

router = Router()
# Усі хендлери цього файлу працюють лише для адміністратора
router.message.filter(F.from_user.id == ADMIN_ID)
router.callback_query.filter(F.from_user.id == ADMIN_ID)


class Grant(StatesGroup):
    user_id = State()
    days = State()


class Broadcast(StatesGroup):
    message = State()
    confirm = State()


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🔧 <b>Панель адміністратора</b>", reply_markup=admin_kb())


@router.callback_query(F.data == "adm:cancel")
async def admin_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Скасовано.")
    await callback.answer()


# ---------- Статистика ----------

@router.callback_query(F.data == "adm:stats")
async def stats(callback: CallbackQuery):
    s = db.get_stats()
    await callback.message.answer(
        "📊 <b>Статистика</b>\n\n"
        f"👥 Користувачів бота: <b>{s['users']}</b>\n"
        f"✅ Активних підписок: <b>{s['active']}</b>\n"
        f"🧾 Оплат на перевірці: <b>{s['pending']}</b>\n\n"
        "<b>За поточний місяць:</b>\n"
        f"• оплат: <b>{s['month_payments']}</b>\n"
        f"• на картку: <b>{s['month_uah']} грн</b>\n"
        f"• в Telegram Stars: <b>{s['month_stars']} ⭐</b>"
    )
    await callback.answer()


# ---------- Перевірка оплат ----------

@router.callback_query(F.data == "adm:pending")
async def pending(callback: CallbackQuery, bot: Bot):
    payments = db.pending_payments()
    if not payments:
        await callback.answer("Немає оплат на перевірці 👌", show_alert=True)
        return
    for p in payments:
        t = TARIFFS[p["tariff_key"]]
        caption = (
            f"🧾 <b>Оплата #{p['id']}</b>\n\n"
            f"Від: {user_label(p['user_id'])}\n"
            f"Тариф: {t['title']}\n"
            f"Сума: {p['amount_uah']} грн\n"
            f"Дата: {p['created_at']}"
        )
        try:
            await bot.send_photo(ADMIN_ID, p["receipt_file_id"], caption=caption,
                                 reply_markup=review_kb(p["id"]))
        except TelegramBadRequest:
            # Квитанція була надіслана як документ (PDF)
            await bot.send_document(ADMIN_ID, p["receipt_file_id"], caption=caption,
                                    reply_markup=review_kb(p["id"]))
    await callback.answer()


async def _mark_reviewed(callback: CallbackQuery, status_text: str):
    """Дописує статус під квитанцією і прибирає кнопки."""
    old = html.escape(callback.message.caption or "")
    try:
        await callback.message.edit_caption(caption=f"{old}\n\n{status_text}", reply_markup=None)
    except TelegramBadRequest:
        await callback.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data.startswith("approve:"))
async def approve(callback: CallbackQuery, bot: Bot):
    payment_id = int(callback.data.split(":")[1])
    p = db.get_payment(payment_id)
    if not p or p["status"] != "pending":
        await callback.answer("Цю оплату вже оброблено", show_alert=True)
        return

    db.set_payment_status(payment_id, "approved")
    t = TARIFFS[p["tariff_key"]]
    expires = await grant_access(bot, p["user_id"], t["days"], "🎉 Оплату підтверджено, дякуємо!")
    until = expires.strftime(DATE_FORMAT) if expires else "—"
    await _mark_reviewed(callback, f"✅ <b>ПІДТВЕРДЖЕНО</b> — підписка до {until}")
    await callback.answer("Підтверджено")


@router.callback_query(F.data.startswith("reject:"))
async def reject(callback: CallbackQuery, bot: Bot):
    payment_id = int(callback.data.split(":")[1])
    p = db.get_payment(payment_id)
    if not p or p["status"] != "pending":
        await callback.answer("Цю оплату вже оброблено", show_alert=True)
        return

    db.set_payment_status(payment_id, "rejected")
    try:
        await bot.send_message(
            p["user_id"],
            "❌ На жаль, оплату не підтверджено.\n\n"
            "Перевір суму та реквізити або надішли квитанцію ще раз через «💎 Тарифи».",
        )
    except (TelegramForbiddenError, TelegramBadRequest):
        pass
    await _mark_reviewed(callback, "❌ <b>ВІДХИЛЕНО</b>")
    await callback.answer("Відхилено")


# ---------- Видати підписку вручну ----------

@router.callback_query(F.data == "adm:grant")
async def grant_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Grant.user_id)
    await callback.message.answer(
        "🎁 Надішли <b>Telegram ID</b> користувача.\n"
        "ID видно в повідомленнях про оплати. Користувач має хоча б раз запустити бота.",
        reply_markup=admin_cancel_kb(),
    )
    await callback.answer()


@router.message(Grant.user_id)
async def grant_user_id(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("ID має складатися лише з цифр. Спробуй ще раз:")
        return
    await state.update_data(user_id=int(message.text.strip()))
    await state.set_state(Grant.days)
    await message.answer("На скільки днів видати підписку? Напиши число, наприклад <b>30</b>:")


@router.message(Grant.days)
async def grant_days(message: Message, state: FSMContext, bot: Bot):
    if not message.text or not message.text.strip().isdigit() or int(message.text) <= 0:
        await message.answer("Напиши кількість днів числом, наприклад <b>30</b>:")
        return
    days = int(message.text.strip())
    user_id = (await state.get_data())["user_id"]
    await state.clear()

    db.create_payment(user_id=user_id, tariff_key="m1", method="manual", status="approved")
    expires = await grant_access(bot, user_id, days, "🎁 Адміністратор видав тобі підписку!")
    if expires:
        await message.answer(
            f"✅ Підписку видано: {user_label(user_id)}\n"
            f"Діє до: <b>{expires.strftime(DATE_FORMAT)}</b>"
        )
    else:
        await message.answer(
            "⚠️ Підписку збережено, але повідомлення не доставлено — "
            "користувач ще не запускав бота або заблокував його."
        )


# ---------- Розсилка ----------

@router.callback_query(F.data == "adm:broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Broadcast.message)
    await callback.message.answer(
        "📢 Надішли повідомлення для розсилки — текст, фото з підписом, відео тощо.",
        reply_markup=admin_cancel_kb(),
    )
    await callback.answer()


@router.message(Broadcast.message)
async def broadcast_preview(message: Message, state: FSMContext):
    await state.update_data(chat_id=message.chat.id, message_id=message.message_id)
    await state.set_state(Broadcast.confirm)
    count = len(db.all_user_ids())
    await message.answer(
        f"Надіслати це повідомлення <b>{count}</b> користувачам?",
        reply_markup=broadcast_confirm_kb(),
    )


@router.callback_query(Broadcast.confirm, F.data == "bc:cancel")
async def broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Розсилку скасовано.")
    await callback.answer()


@router.callback_query(Broadcast.confirm, F.data == "bc:send")
async def broadcast_send(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await state.clear()
    await callback.message.edit_text("⏳ Розсилка почалась...")

    sent, failed = 0, 0
    for user_id in db.all_user_ids():
        try:
            await bot.copy_message(user_id, data["chat_id"], data["message_id"])
            sent += 1
        except (TelegramForbiddenError, TelegramBadRequest):
            failed += 1
        await asyncio.sleep(0.05)  # невелика пауза, щоб не впертися в ліміти Telegram

    await callback.message.edit_text(
        f"📢 <b>Розсилку завершено</b>\n\n✅ Доставлено: {sent}\n❌ Не доставлено: {failed}"
    )
    await callback.answer()


# ---------- Службові команди ----------

@router.message(Command("refund"))
async def cmd_refund(message: Message, command: CommandObject, bot: Bot):
    """/refund 5 — повернути Telegram Stars за оплату №5 і забрати доступ."""
    if not command.args or not command.args.strip().isdigit():
        await message.answer("Використання: <code>/refund НОМЕР_ОПЛАТИ</code>")
        return
    p = db.get_payment(int(command.args))
    if not p or p["method"] != "stars" or p["status"] != "approved":
        await message.answer("Оплату не знайдено або її не можна повернути.")
        return
    try:
        await bot.refund_star_payment(p["user_id"], p["charge_id"])
    except TelegramBadRequest as e:
        await message.answer(f"Помилка повернення: {html.escape(str(e))}")
        return
    db.set_payment_status(p["id"], "refunded")
    await revoke_access(bot, p["user_id"])
    await message.answer(f"↩️ Stars за оплату #{p['id']} повернено, доступ закрито.")


@router.message(Command("setdays"))
async def cmd_setdays(message: Message, command: CommandObject):
    """/setdays ID ДНІ — для тестів: підписка закінчиться через вказану кількість днів.
    Можна дробові: /setdays 123 0.5 (12 годин), /setdays 123 0 (закінчиться одразу)."""
    try:
        user_id_str, days_str = command.args.split()
        user_id, days = int(user_id_str), float(days_str.replace(",", "."))
    except (AttributeError, ValueError):
        await message.answer("Використання: <code>/setdays ID ДНІ</code>, наприклад <code>/setdays 123456 2</code>")
        return
    expires = datetime.now() + timedelta(days=days)
    db.set_expires(user_id, expires)
    await message.answer(
        f"🧪 Підписка {user_label(user_id)} тепер до <b>{expires.strftime(DATE_FORMAT)}</b>.\n"
        "Нагадування / видалення спрацює протягом хвилини."
    )
