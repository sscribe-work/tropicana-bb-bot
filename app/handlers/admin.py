"""Панель администратора: просмотр записей на день."""
from __future__ import annotations

from datetime import date, timedelta

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select

from app.config import get_settings
from app.db.models import Booking, BookingStatus
from app.handlers.booking import day_label

admin_router = Router()
settings = get_settings()


@admin_router.message(Command("bookings"))
async def cmd_bookings(message: Message) -> None:
    """/bookings <секретный код> — записи на сегодня и неделю вперёд (только для администраторов)."""
    if not settings.admin_secret:
        await message.answer("Задайте ADMIN_SECRET в переменных окружения, чтобы использовать /bookings.")
        return
    parts = (message.text or "").split(maxsplit=1)
    secret = parts[1].strip() if len(parts) > 1 else ""
    if secret != settings.admin_secret:
        await message.answer("⛔ Недостаточно прав. Используйте: /bookings <ADMIN_SECRET>")
        return

    from app.db.session import SessionMaker

    today = date.today()
    until = today + timedelta(days=7)

    async with SessionMaker() as session:
        rows = (
            await session.scalars(
                select(Booking)
                .where(
                    Booking.booking_date >= today,
                    Booking.booking_date <= until,
                    Booking.status == BookingStatus.ACTIVE,
                )
                .order_by(Booking.booking_date, Booking.booking_time)
            )
        ).all()

    if not rows:
        await message.answer("📭 На ближайшую неделю записей нет.")
        return

    lines = [f"🗓 <b>Tropicana SPB — записи на 7 дней ({len(rows)}):</b>\n"]
    current_day = None
    for b in rows:
        if b.booking_date != current_day:
            current_day = b.booking_date
            lines.append(f"\n<b>{day_label(b.booking_date)}</b>")
        lines.append(
            f"• {b.booking_time.strftime('%H:%M')} — {b.client_name}, {b.service}, 📱 {b.client_phone}"
        )

    await message.answer("\n".join(lines))
