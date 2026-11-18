from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from config import TARIFFS

# Тексти кнопок головного меню (використовуються і в хендлерах)
BTN_TARIFFS = "💎 Тарифи"
BTN_MY_SUB = "👤 Моя підписка"
BTN_ABOUT = "ℹ️ Про канал"


def main_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_TARIFFS), KeyboardButton(text=BTN_MY_SUB)],
            [KeyboardButton(text=BTN_ABOUT)],
        ],
        resize_keyboard=True,
    )


def tariffs_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=f"{t['title']} — {t['price_uah']} грн / {t['stars']} ⭐",
            callback_data=f"tariff:{key}",
        )]
        for key, t in TARIFFS.items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pay_method_kb(tariff_key: str) -> InlineKeyboardMarkup:
    t = TARIFFS[tariff_key]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⭐ Telegram Stars ({t['stars']} ⭐)",
                              callback_data=f"pay_stars:{tariff_key}")],
        [InlineKeyboardButton(text=f"💳 Переказ на картку ({t['price_uah']} грн)",
                              callback_data=f"pay_card:{tariff_key}")],
        [InlineKeyboardButton(text="⬅️ Назад до тарифів", callback_data="show_tariffs")],
    ])


def cancel_payment_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_pay")],
    ])


def my_sub_kb(active: bool) -> InlineKeyboardMarkup:
    rows = []
    if active:
        rows.append([InlineKeyboardButton(text="🔗 Отримати посилання в канал",
                                          callback_data="get_link")])
        rows.append([InlineKeyboardButton(text="🔄 Продовжити підписку",
                                          callback_data="show_tariffs")])
    else:
        rows.append([InlineKeyboardButton(text="💎 Оформити підписку",
                                          callback_data="show_tariffs")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def join_kb(link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚪 Увійти в канал", url=link)],
    ])


def renew_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Продовжити підписку", callback_data="show_tariffs")],
    ])


# ---------- Адмін ----------

def admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="adm:stats")],
        [InlineKeyboardButton(text="🧾 Оплати на перевірці", callback_data="adm:pending")],
        [InlineKeyboardButton(text="🎁 Видати підписку", callback_data="adm:grant")],
        [InlineKeyboardButton(text="📢 Розсилка", callback_data="adm:broadcast")],
    ])


def review_kb(payment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Підтвердити", callback_data=f"approve:{payment_id}"),
        InlineKeyboardButton(text="❌ Відхилити", callback_data=f"reject:{payment_id}"),
    ]])


def broadcast_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Надіслати всім", callback_data="bc:send"),
        InlineKeyboardButton(text="❌ Скасувати", callback_data="bc:cancel"),
    ]])


def admin_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="adm:cancel")],
    ])
