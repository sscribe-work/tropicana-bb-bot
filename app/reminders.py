"""Напоминания о визите — простой asyncio-цикл (без APScheduler).

Каждые CHECK_INTERVAL_MINUTES смотрим в CSV записи, которые начинаются
в ближайшие REMINDER_HOURS_BEFORE часов, и шлём клиенту напоминание.
Флаг reminder_sent в файле защищает от повторной отправки.
"""
import asyncio
import logging

from app import config, csv_db

logger = logging.getLogger(__name__)

CHECK_INTERVAL_MINUTES = 10


async def send_due_reminders(bot):
    """Отправляет напоминания всем 'созревшим' записям."""
    due = csv_db.bookings_due_for_reminder()
    for row in due:
        text = (
            "⏰ <b>Напоминание о визите!</b>\n\n"
            "📅 %s в <b>%s</b>\n"
            "💇‍♀️ %s\n"
            "👤 %s\n\n"
            "Ждём вас в салоне Tropicana SPB ✨\n"
            "Если планы изменились — отмените запись в «📋 Мои записи»."
            % (row["date"], row["time"], row["service"], row["name"])
        )
        try:
            await bot.send_message(int(row["chat_id"]), text)
        except Exception as exc:  # пользователь заблокировал бота и т.п.
            logger.warning("Напоминание id=%s не доставлено: %s", row["id"], exc)
        finally:
            # помечаем отправленным в любом случае, чтобы не слать повторно
            csv_db.mark_reminder_sent(row["id"])
    if due:
        logger.info("Отправлено напоминаний: %s", len(due))


async def reminders_loop(bot):
    """Фоновый цикл: раз в 10 минут проверяем напоминания."""
    while True:
        try:
            await send_due_reminders(bot)
        except Exception:
            logger.exception("Ошибка в цикле напоминаний")
        await asyncio.sleep(CHECK_INTERVAL_MINUTES * 60)
