import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import db
from config import BOT_TOKEN
from handlers import admin, channel, payments, user
from scheduler import subscription_checker


async def main():
    logging.basicConfig(level=logging.INFO)
    db.init_db()

    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    # Порядок важливий: спочатку адмінські хендлери, потім оплати, потім звичайні
    dp.include_routers(admin.router, channel.router, payments.router, user.router)

    # Фонова перевірка підписок працює паралельно з ботом
    checker = asyncio.create_task(subscription_checker(bot))
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        checker.cancel()


if __name__ == "__main__":
    asyncio.run(main())
