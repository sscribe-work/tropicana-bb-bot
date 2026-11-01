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

    # Telegram ID администратора — сюда приходят уведомления о новых записях
    # и отменах (0 — отключить уведомления).
    admin_chat_id: int = 0

    # Услуги салона. По умолчанию две («Услуга 1», «Услуга 2») — далее по аналогии:
    # "Услуга 1|60;Услуга 2|90", где после | длительность в минутах, разделитель — ;
    services: str = "Услуга 1|30;Услуга 2|30"

    # За сколько часов до визита отправлять напоминание клиенту
    reminder_hours_before: int = 3

    def service_list(self) -> list[tuple[str, int]]:
        """Разбирает SERVICES в [(название, длительность_в_минутах), ...]."""
        result: list[tuple[str, int]] = []
        for part in self.services.split(";"):
            part = part.strip()
            if not part:
                continue
            name, _, dur = part.partition("|")
            try:
                minutes = int(dur) if dur else self.slot_minutes
            except ValueError:
                minutes = self.slot_minutes
            result.append((name.strip(), minutes))
        return result


@lru_cache
def get_settings() -> Settings:
    return Settings()
