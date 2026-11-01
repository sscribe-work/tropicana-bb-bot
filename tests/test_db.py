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


if __name__ == "__main__":
    asyncio.run(main())
