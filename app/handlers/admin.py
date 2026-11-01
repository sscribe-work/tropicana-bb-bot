"""Панель администратора: просмотр записей на неделю."""
from datetime import date

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app import config, csv_db
from app.handlers.booking import day_label

admin_router = Router()


@admin_router.message(Command("bookings"))
async def cmd_bookings(message):
    """/bookings <секретный код> — все актуальные записи на неделю (только для админа)."""
    if not config.ADMIN_SECRET:
        await message.answer("Задайте ADMIN_SECRET в переменных окружения, чтобы использовать /bookings.")
        return
    parts = (message.text or "").split(maxsplit=1)
    secret = parts[1].strip() if len(parts) > 1 else ""
    if secret != config.ADMIN_SECRET:
        await message.answer("⛔ Недостаточно прав. Используйте: /bookings <ADMIN_SECRET>")
        return

    rows = csv_db.list_bookings()
    if not rows:
        await message.answer("📭 На ближайшую неделю записей нет.")
        return

    lines = ["🗓 <b>Tropicana SPB — записи (%s):</b>\n" % len(rows)]
    current_day = None
    for row in rows:
        day = date.fromisoformat(row["date"])
        if day != current_day:
            current_day = day
            lines.append("\n<b>%s</b>" % day_label(day))
        lines.append("• %s — %s, %s, 📱 %s" % (row["time"], row["name"], row["service"], row["phone"]))

    await message.answer("\n".join(lines))
