"""Быстрая самопроверка CSV-хранилища (запуск: python test_csv_db.py)."""
import os
from datetime import date, datetime, timedelta

os.environ["CSV_FILE"] = "./data/test_bookings.csv"
if os.path.exists("./data/test_bookings.csv"):
    os.remove("./data/test_bookings.csv")

from app import csv_db  # noqa: E402

today = csv_db.now_local().date()
tomorrow = today + timedelta(days=1)

# 1. файл создаётся с заголовком
csv_db._ensure_file()
assert os.path.exists("./data/test_bookings.csv")

# 2. свободные слоты на завтра: ровно 24 штуки 10:00..21:30
slots = csv_db.get_free_slots(tomorrow.isoformat())
assert len(slots) == 24, slots
assert slots[0] == "10:00" and slots[-1] == "21:30", slots[:2]

# 3. добавление записи и блокировка слота
b = csv_db.add_booking(tomorrow.isoformat(), "14:30", "Услуга 1", 30, "Анна", "+79001234567", 111, 111)
assert b and b["id"] == "1"
assert "14:30" not in csv_db.get_free_slots(tomorrow.isoformat())
assert csv_db.slot_is_free(tomorrow.isoformat(), "14:30") is False
assert csv_db.slot_is_free(tomorrow.isoformat(), "15:00") is True
# гонка: второй клиент на тот же слот получает None
assert csv_db.add_booking(tomorrow.isoformat(), "14:30", "Услуга 2", 30, "Борис", "+7", 222, 222) is None

# 4. отмена — слот освобождается
deleted = csv_db.delete_booking(b["id"])
assert deleted and deleted["name"] == "Анна"
assert csv_db.slot_is_free(tomorrow.isoformat(), "14:30") is True
assert csv_db.bookings_for_user(111) == []

# 5. прошедшие записи удаляются из файла
now = csv_db.now_local()
past_day = (now - timedelta(days=1)).date().isoformat()
with open("./data/test_bookings.csv", "a", newline="", encoding="utf-8") as f:
    f.write("99,%s,12:00,Услуга 1,30,Прошлая,+7,333,333,0,2026-01-01 10:00\n" % past_day)
rows = csv_db.list_bookings()
assert all(r["id"] != "99" for r in rows), "прошлая запись должна удалиться"
with open("./data/test_bookings.csv", encoding="utf-8") as f:
    assert "99," not in f.read(), "файл должен быть перезаписан без прошедших"

# 6. напоминания: запись через 2 часа попадает в окно, через 10 часов — нет
in2 = (now + timedelta(hours=2)).replace(second=0, microsecond=0)
in10 = (now + timedelta(hours=10)).replace(second=0, microsecond=0)
b1 = csv_db.add_booking(in2.date().isoformat(), in2.strftime("%H:%M"), "Услуга 1", 30, "Вика", "+7", 444, 444)
b2 = csv_db.add_booking(in10.date().isoformat(), in10.strftime("%H:%M"), "Услуга 2", 30, "Гоша", "+7", 555, 555)
due_ids = [r["id"] for r in csv_db.bookings_due_for_reminder()]
assert b1["id"] in due_ids and b2["id"] not in due_ids
csv_db.mark_reminder_sent(b1["id"])
assert b1["id"] not in [r["id"] for r in csv_db.bookings_due_for_reminder()], "повторно не шлём"

os.remove("./data/test_bookings.csv")
print("ALL CSV TESTS PASSED")
