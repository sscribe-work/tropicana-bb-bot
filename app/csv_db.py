"""Хранилище записей в CSV-файле (вместо базы данных).

Функции синхронные и защищены блокировкой — вызываем из хендлеров как есть,
для маленького салона скорости хватает. Храним записи только на неделю вперёд,
прошедшие удаляются автоматически при каждой операции с файлом.
"""
import csv
import os
import threading
from datetime import datetime, timedelta

from pytz import timezone

from app import config

TZ = timezone(config.TIMEZONE)
_lock = threading.Lock()

# Колонки в CSV-файле
FIELDS = [
    "id", "date", "time", "service", "duration",
    "name", "phone", "telegram_id", "chat_id",
    "reminder_sent", "created_at",
]


def now_local():
    """Текущее время в часовом поясе салона."""
    return datetime.now(TZ)


def _ensure_file():
    directory = os.path.dirname(config.CSV_FILE)
    if directory:
        os.makedirs(directory, exist_ok=True)
    if not os.path.exists(config.CSV_FILE):
        with open(config.CSV_FILE, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(FIELDS)


def _read_rows():
    _ensure_file()
    with open(config.CSV_FILE, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            # строки с битыми данными просто пропускаем
            if row.get("date") and row.get("time"):
                rows.append(row)
        return rows


def _write_rows(rows):
    tmp_path = config.CSV_FILE + ".tmp"
    with open(tmp_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    # перезапись через временный файл, чтобы не потерять данные при сбое
    os.replace(tmp_path, config.CSV_FILE)


def delete_past_bookings(rows):
    """Удаляет прошедшие записи (дата+время раньше «сейчас») и отменённые без времени."""
    now = now_local().replace(tzinfo=None)
    result = []
    for row in rows:
        starts = datetime.strptime(row["date"] + " " + row["time"], "%Y-%m-%d %H:%M")
        if starts >= now:
            result.append(row)
    return result


def list_bookings():
    """Все актуальные записи, отсортированные по дате и времени."""
    with _lock:
        rows = delete_past_bookings(_read_rows())
        _write_rows(rows)  # заодно чистим файл от прошлых записей
    rows.sort(key=lambda r: (r["date"], r["time"]))
    return rows


def get_free_slots(day_str):
    """Свободные тайм-слоты на день (день_str в формате ГГГГ-ММ-ДД), список 'ЧЧ:ММ'."""
    taken = set()
    for row in list_bookings():
        if row["date"] == day_str:
            taken.add(row["time"])

    slots = []
    start_dt = datetime.strptime(day_str + " %s:00" % config.WORK_START_HOUR, "%Y-%m-%d %H:%M")
    end_dt = datetime.strptime(day_str + " %s:00" % config.WORK_END_HOUR, "%Y-%m-%d %H:%M")
    now = now_local().replace(tzinfo=None)
    current = start_dt
    while current < end_dt:
        # сегодня прошедшее время не предлагаем
        if current > now and current.strftime("%H:%M") not in taken:
            slots.append(current.strftime("%H:%M"))
        current += timedelta(minutes=config.SLOT_MINUTES)
    return slots


def slot_is_free(day_str, time_str):
    """Проверяет, что слот ещё никто не занял (защита от гонки двух клиентов)."""
    for row in list_bookings():
        if row["date"] == day_str and row["time"] == time_str:
            return False
    return True


def add_booking(day_str, time_str, service, duration, name, phone, telegram_id, chat_id):
    """Добавляет запись. Возвращает dict записи или None, если слот уже занят."""
    with _lock:
        rows = delete_past_bookings(_read_rows())
        for row in rows:
            if row["date"] == day_str and row["time"] == time_str:
                return None  # слот только что заняли
        new_id = max([int(r["id"]) for r in rows], default=0) + 1
        booking = {
            "id": str(new_id),
            "date": day_str,
            "time": time_str,
            "service": service,
            "duration": str(duration),
            "name": name,
            "phone": phone,
            "telegram_id": str(telegram_id),
            "chat_id": str(chat_id),
            "reminder_sent": "0",
            "created_at": now_local().strftime("%Y-%m-%d %H:%M"),
        }
        rows.append(booking)
        _write_rows(rows)
        return booking


def find_booking(booking_id):
    for row in list_bookings():
        if row["id"] == str(booking_id):
            return row
    return None


def bookings_for_user(telegram_id):
    """Активные записи клиента."""
    return [row for row in list_bookings() if row["telegram_id"] == str(telegram_id)]


def delete_booking(booking_id):
    """Удаляет запись (отмена клиентом). Возвращает удалённую строку или None."""
    with _lock:
        rows = delete_past_bookings(_read_rows())
        deleted = None
        kept = []
        for row in rows:
            if row["id"] == str(booking_id):
                deleted = row
            else:
                kept.append(row)
        _write_rows(kept)
        return deleted


def mark_reminder_sent(booking_id):
    """Ставит в CSV флаг, что напоминание уже отправлено (чтобы не слать дважды)."""
    with _lock:
        rows = delete_past_bookings(_read_rows())
        for row in rows:
            if row["id"] == str(booking_id):
                row["reminder_sent"] = "1"
        _write_rows(rows)


def bookings_due_for_reminder():
    """Записи, которым пора отправить напоминание (начинаются в окне за N часов)."""
    now = now_local().replace(tzinfo=None)
    window_end = now + timedelta(hours=config.REMINDER_HOURS_BEFORE)
    due = []
    for row in list_bookings():
        if row["reminder_sent"] == "1":
            continue
        starts = datetime.strptime(row["date"] + " " + row["time"], "%Y-%m-%d %H:%M")
        if now <= starts < window_end:
            due.append(row)
    return due
