"""Модели SQLAlchemy и доступ к данным."""
from __future__ import annotations

import enum
from datetime import date, datetime, time, timedelta

from sqlalchemy import DateTime, Index, String, Time, func, select, text
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(AsyncAttrs, DeclarativeBase):
    pass


@enum.unique
class BookingStatus(str, enum.Enum):
    """Статусы записи (значения хранятся в БД как строки)."""

    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"


class Booking(Base):
    """Запись клиента в салон."""

    __tablename__ = "bookings"
    # Частичный уникальный индекс: активная запись на слот может быть только одна.
    # (SQLite и PostgreSQL поддерживают partial indexes; на других СУБД защиту
    #  обеспечивает проверка в create_booking.)
    __table_args__ = (
        Index(
            "uq_active_slot",
            "booking_date",
            "booking_time",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
            sqlite_where=text("status = 'ACTIVE'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    booking_date: Mapped[date] = mapped_column(index=True)
    booking_time: Mapped[time] = mapped_column(index=True)

    telegram_id: Mapped[int] = mapped_column(index=True)
    chat_id: Mapped[int] = mapped_column(index=True)

    client_name: Mapped[str] = mapped_column(String(120))
    client_phone: Mapped[str] = mapped_column(String(40), default="")
    service: Mapped[str] = mapped_column(String(120), default="Услуга")

    # Храним значение enum-строки ("ACTIVE"/"CANCELLED"), совместимо с partial index
    status: Mapped[BookingStatus] = mapped_column(
        String(20),
        default=BookingStatus.ACTIVE.value,
        index=True,
    )


async def get_free_slots(session, day: date, start: time, end: time, step_minutes: int) -> list[time]:
    """Возвращает свободные тайм-слоты на указанный день."""
    taken = set(
        (
            await session.scalars(
                select(Booking.booking_time).where(
                    Booking.booking_date == day,
                    Booking.status == BookingStatus.ACTIVE,
                )
            )
        ).all()
    )

    slots: list[time] = []
    current = datetime.combine(day, start)
    last = datetime.combine(day, end)
    delta = timedelta(minutes=step_minutes)
    while current < last:
        t = current.time()
        if t not in taken:
            slots.append(t)
        current += delta
    return slots


async def create_booking(session, **kwargs) -> Booking | None:
    """Создаёт запись; возвращает None, если слот уже занят (гонка двух клиентов)."""
    existing = await session.scalar(
        select(Booking).where(
            Booking.booking_date == kwargs["booking_date"],
            Booking.booking_time == kwargs["booking_time"],
            Booking.status == BookingStatus.ACTIVE,
        )
    )
    if existing:
        return None
    booking = Booking(**kwargs)
    session.add(booking)
    await session.commit()
    return booking


async def cancel_booking(session, booking_id: int) -> Booking | None:
    booking = await session.get(Booking, booking_id)
    if booking and booking.status == BookingStatus.ACTIVE:
        booking.status = BookingStatus.CANCELLED
        await session.commit()
    return booking
