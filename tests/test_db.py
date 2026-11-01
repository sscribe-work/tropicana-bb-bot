"""Быстрые тесты логики БД: python tests/test_db.py"""
import asyncio
import sys
from datetime import date, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402


async def main() -> None:
    from app.db.models import (
        Booking,
        BookingStatus,
        cancel_booking,
        create_booking,
        get_free_slots,
    )
    from app.db.session import SessionMaker, init_db

    await init_db()
    day = date(2026, 11, 5)

    async with SessionMaker() as s:
        slots = await get_free_slots(s, day, time(10, 0), time(22, 0), 30)
        assert len(slots) == 24, slots
        assert slots[0] == time(10, 0) and slots[-1] == time(21, 30)

        b = await create_booking(
            s, booking_date=day, booking_time=time(10, 0),
            telegram_id=1, chat_id=1, client_name="Анна",
            client_phone="+7 900 123-45-67", service="Услуга 1",
        )
        assert b is not None

        dup = await create_booking(
            s, booking_date=day, booking_time=time(10, 0),
            telegram_id=2, chat_id=2, client_name="Борис",
        )
        assert dup is None, "повторная запись на занятый слот должна блокироваться"

        rows = (
            await s.scalars(select(Booking).where(Booking.telegram_id == 1))
        ).all()
        assert len(rows) == 1 and rows[0].status == BookingStatus.ACTIVE

        slots2 = await get_free_slots(s, day, time(10, 0), time(22, 0), 30)
        assert len(slots2) == 23 and time(10, 0) not in slots2

        await cancel_booking(s, b.id)
        again = await create_booking(
            s, booking_date=day, booking_time=time(10, 0),
            telegram_id=3, chat_id=3, client_name="Вера",
        )
        assert again is not None, "после отмены слот должен освободиться"

    print("ALL TESTS PASSED")


async def reminder_tests() -> None:
    """Логика напоминаний: окно «за N часов», флаг reminder_sent."""
    from datetime import datetime, timedelta, timezone as dt_tz

    from app.db.models import (
        Booking,
        create_booking,
        get_bookings_between,
        mark_reminder_sent,
    )
    from app.db.session import SessionMaker

    tz = dt_tz.utc
    now = datetime.now(tz).replace(microsecond=0)
    # запись, которая начинается ровно через 3 часа (в окне [now+3h-10m, now+3h))
    target = now + timedelta(hours=3) - timedelta(minutes=5)
    day = target.date()
    t = target.time().replace(second=0, microsecond=0)

    async with SessionMaker() as s:
        b = await create_booking(
            s, booking_date=day, booking_time=t,
            telegram_id=9, chat_id=9, client_name="Глеб", service="Услуга 2",
        )
        assert b is not None and b.reminder_sent is False

        due = await get_bookings_between(s, now + timedelta(hours=3) - timedelta(minutes=10), now + timedelta(hours=3))
        assert any(x.id == b.id for x in due), "запись должна попасть в окно напоминаний"

        await mark_reminder_sent(s, b.id)
        due2 = await get_bookings_between(s, now + timedelta(hours=3) - timedelta(minutes=10), now + timedelta(hours=3))
        assert not any(x.id == b.id for x in due2), "после отметки reminder_sent запись не должна попадать в выборку"

    print("REMINDER TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
    asyncio.run(reminder_tests())
