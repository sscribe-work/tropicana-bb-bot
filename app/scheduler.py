"""Фоновые напоминания о визите (APScheduler).

Каждые REMINDER_CHECK_MINUTES проверяются активные записи, которые начинаются
в окне [now + reminder_hours_before - check_interval, now + reminder_hours_before),
и клиенту отправляется напоминание. Флаг reminder_sent защищает от повторной отправки.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.db.models import get_bookings_between, mark_reminder_sent
from app.db.session import SessionMaker

settings = get_settings()
tz = ZoneInfo(settings.timezone)
logger = logging.getLogger(__name__)

CHECK_INTERVAL_MINUTES = 10


async def send_due_reminders(bot: Bot) -> None:
    """Отправляет напоминания всем «созревшим» записям."""
    now = datetime.now(tz)
    window_end = now + timedelta(hours=settings.reminder_hours_before)
    window_start = window_end - timedelta(minutes=CHECK_INTERVAL_MINUTES)

    async with SessionMaker() as session:
        due = await get_bookings_between(session, window_start, window_end)
        for b in due:
            try:
                await bot.send_message(
                    b.chat_id,
                    "⏰ <b>Напоминание о визите!</b>\n\n"
                    f"📅 {b.booking_date.strftime('%d.%m.%Y')} в <b>{b.booking_time.strftime('%H:%M')}</b>\n"
                    f"💇‍♀️ {b.service}\n"
                    f"👤 {b.client_name}\n\n"
                    "Ждём вас в салоне Tropicana SPB ✨\n"
                    "Если планы изменились — отмените запись в «📋 Мои записи».",
                )
            except Exception as exc:  # пользователь заблокировал бота и т.п.
                logger.warning("Напоминание id=%s не доставлено: %s", b.id, exc)
            finally:
                # помечаем отправленным в любом случае, чтобы не слать повторно
                await mark_reminder_sent(session, b.id)
        if due:
            logger.info("Отправлено напоминаний: %s", len(due))


def create_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=tz)
    scheduler.add_job(
        send_due_reminders,
        trigger="interval",
        minutes=CHECK_INTERVAL_MINUTES,
        kwargs={"bot": bot},
        id="reminders",
        max_instances=1,
        coalesce=True,
    )
    return scheduler
