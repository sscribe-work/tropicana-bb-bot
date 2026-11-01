"""Инициализация асинхронного движка БД."""
from __future__ import annotations

import os
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.models import Base

settings = get_settings()

# Для SQLite нужно создать каталог под файл базы
if settings.database_url.startswith("sqlite"):
    path = settings.database_url.split(":///")[-1]
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
SessionMaker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Простая миграция «на месте» для SQLite: добавляем недостающие колонки
        # (появились в новых версиях схемы). Для PostgreSQL аналогично.
        if settings.database_url.startswith("sqlite"):
            res = await conn.exec_driver_sql("PRAGMA table_info(bookings)")
            columns = {row[1] for row in res.fetchall()}
            if "reminder_sent" not in columns:
                await conn.exec_driver_sql(
                    "ALTER TABLE bookings ADD COLUMN reminder_sent BOOLEAN NOT NULL DEFAULT 0"
                )


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionMaker() as session:
        yield session
