"""Точка входа Telegram-бота салона красоты."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from app.config import get_settings
from app.db.session import init_db
from app.handlers import routers
from app.scheduler import create_scheduler

settings = get_settings()


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if not settings.bot_token:
        raise RuntimeError("Не задан BOT_TOKEN. Скопируйте .env.example в .env и укажите токен от @BotFather.")

    await init_db()

    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    for router in routers:
        dp.include_router(router)

    await bot.set_my_commands(
        [
            BotCommand(command="/start", description="Начать запись"),
            BotCommand(command="/help", description="Как записаться"),
            BotCommand(command="/skip", description="Пропустить ввод телефона"),
        ]
    )

    scheduler = create_scheduler(bot)
    scheduler.start()
    # Сразу проверим, нет ли «созревших» напоминаний после рестарта контейнера
    await send_due_reminders_soon(bot)

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)


async def send_due_reminders_soon(bot: Bot) -> None:
    from app.scheduler import send_due_reminders

    try:
        await send_due_reminders(bot)
    except Exception:
        logging.getLogger(__name__).exception("Ошибка при стартовой проверке напоминаний")


if __name__ == "__main__":
    asyncio.run(main())
