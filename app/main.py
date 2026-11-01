"""Точка входа Telegram-бота салона красоты Tropicana SPB."""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from app import config, csv_db
from app.handlers import routers
from app.reminders import reminders_loop, send_due_reminders

logger = logging.getLogger(__name__)


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if not config.BOT_TOKEN:
        raise RuntimeError("Не задан BOT_TOKEN. Скопируйте .env.example в .env и укажите токен от @BotFather.")

    # создаём CSV-файл, если его ещё нет
    csv_db._ensure_file()

    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    for router in routers:
        dp.include_router(router)

    await bot.set_my_commands([
        BotCommand(command="/start", description="Начать запись"),
        BotCommand(command="/help", description="Как записаться"),
        BotCommand(command="/skip", description="Пропустить ввод телефона"),
    ])

    # фоновая задача с напоминаниями
    reminder_task = asyncio.create_task(reminders_loop(bot))
    # сразу проверим, нет ли 'созревших' напоминаний после рестарта
    try:
        await send_due_reminders(bot)
    except Exception:
        logger.exception("Ошибка при стартовой проверке напоминаний")

    try:
        await dp.start_polling(bot)
    finally:
        reminder_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
