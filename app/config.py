"""Конфигурация приложения (читается из переменных окружения)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Токен бота (обязателен)
    bot_token: str = ""

    # База данных. По умолчанию — локальный SQLite-файл,
    # в Docker можно указать, например: postgresql+asyncpg://user:pass@db:5432/salon
    database_url: str = "sqlite+aiosqlite:///./data/salon.db"

    # Часовой пояс салона (используется для «сегодня», «завтра» и т.д.)
    timezone: str = "Europe/Moscow"

    # Параметры рабочих часов и слотов
    work_start_hour: int = 10
    work_end_hour: int = 22
    slot_minutes: int = 30

    # Сколько дней вперёд можно записаться
    booking_horizon_days: int = 7

    # Секретный код администратора для /bookings
    admin_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
