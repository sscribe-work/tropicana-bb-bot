"""Настройки бота. Всё читается из переменных окружения (файл .env)."""
import os

from dotenv import load_dotenv

load_dotenv()


def _get_int(name, default):
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return int(default)


BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CSV_FILE = os.getenv("CSV_FILE", "./data/bookings.csv")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")

# Рабочие часы и тайм-слоты
WORK_START_HOUR = _get_int("WORK_START_HOUR", 10)
WORK_END_HOUR = _get_int("WORK_END_HOUR", 22)
SLOT_MINUTES = _get_int("SLOT_MINUTES", 30)

# На сколько дней вперёд можно записаться
BOOKING_HORIZON_DAYS = _get_int("BOOKING_HORIZON_DAYS", 7)

# Админ
ADMIN_SECRET = os.getenv("ADMIN_SECRET", "")
ADMIN_CHAT_ID = _get_int("ADMIN_CHAT_ID", 0)

# За сколько часов до визита слать напоминание
REMINDER_HOURS_BEFORE = _get_int("REMINDER_HOURS_BEFORE", 3)

# Услуги салона: "Услуга 1|30;Услуга 2|60" (название|длительность в минутах).
# Добавляйте новые услуги по аналогии через точку с запятой.
SERVICES_RAW = os.getenv("SERVICES", "Услуга 1|30;Услуга 2|30")


def get_services():
    """Возвращает список услуг: [(название, длительность_в_минутах), ...]"""
    result = []
    for part in SERVICES_RAW.split(";"):
        part = part.strip()
        if not part:
            continue
        name, _, dur = part.partition("|")
        try:
            minutes = int(dur)
        except ValueError:
            minutes = SLOT_MINUTES
        result.append((name.strip(), minutes))
    return result
