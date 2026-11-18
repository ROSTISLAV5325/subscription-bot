"""Коли бота додають адміном у канал — він надсилає адміну ID цього каналу."""
import html

from aiogram import Bot, Router
from aiogram.types import ChatMemberUpdated

from config import ADMIN_ID, CHANNEL_ID

router = Router()


@router.my_chat_member()
async def bot_added_to_channel(event: ChatMemberUpdated, bot: Bot):
    if event.chat.type != "channel" or event.new_chat_member.status != "administrator":
        return

    text = (
        f"✅ Мене додали адміністратором у канал «{html.escape(event.chat.title)}».\n\n"
        f"ID каналу: <code>{event.chat.id}</code>\n\n"
    )
    if event.chat.id != CHANNEL_ID:
        text += "Скопіюй цей ID у файл <b>.env</b> (рядок CHANNEL_ID=...) і перезапусти бота."
    else:
        text += "Цей канал уже вказано в .env — все готово 👌"
    await bot.send_message(ADMIN_ID, text)
