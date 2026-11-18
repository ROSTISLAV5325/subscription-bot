import os

from dotenv import load_dotenv

# Завантажуємо змінні з файлу .env
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
# ID закритого каналу (виглядає як -100...). Бот сам надішле його адміну
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
# Номер картки для оплати переказом
CARD_NUMBER = os.getenv("CARD_NUMBER", "0000 0000 0000 0000")
CARD_OWNER = os.getenv("CARD_OWNER", "Власник картки")

CHANNEL_NAME = "Закритий клуб"
CHANNEL_DESCRIPTION = (
    "🔒 <b>Закритий клуб</b> — приватний канал з корисним контентом.\n\n"
    "• щотижневі матеріали та розбори\n"
    "• доступ до архіву всіх публікацій\n"
    "• спільнота однодумців\n\n"
    "Обирай тариф у розділі «💎 Тарифи»."
)

# Тарифи: ключ -> назва, кількість днів, ціна в гривнях і в Telegram Stars
TARIFFS = {
    "m1": {"title": "1 місяць", "days": 30, "price_uah": 150, "stars": 100},
    "m3": {"title": "3 місяці", "days": 90, "price_uah": 400, "stars": 250},
    "m12": {"title": "12 місяців", "days": 365, "price_uah": 1200, "stars": 750},
}

# Як часто (у секундах) бот перевіряє, у кого закінчується підписка
CHECK_INTERVAL = 60

# Формат дати для повідомлень
DATE_FORMAT = "%d.%m.%Y %H:%M"
