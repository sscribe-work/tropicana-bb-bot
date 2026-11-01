"""Inline-клавиатуры бота (только aiogram, без сторонних библиотек)."""
from datetime import date

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

WEEKDAYS_RU = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]


def main_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Записаться", callback_data="menu:new_booking")
    builder.button(text="📋 Мои записи", callback_data="menu:my_bookings")
    builder.button(text="ℹ️ О салоне", callback_data="menu:about")
    builder.adjust(1)
    return builder.as_markup()


def days_keyboard(days, back_cb="menu:main"):
    """Кнопки с выбором дня (по 3 в ряду). days — список date."""
    builder = InlineKeyboardBuilder()
    for d in days:
        label = "%s %s" % (d.strftime("%d.%m"), WEEKDAYS_RU[d.weekday()])
        builder.button(text=label, callback_data="day:" + d.isoformat())
    builder.button(text="⬅️ Назад", callback_data=back_cb)
    builder.adjust(3)
    return builder.as_markup()


def slots_keyboard(day_str, slots):
    """Кнопки со свободными тайм-слотами (slots — список строк 'ЧЧ:ММ')."""
    builder = InlineKeyboardBuilder()
    for t in slots:
        builder.button(text=t, callback_data="slot:%s|%s" % (day_str, t))
    builder.button(text="⬅️ Другой день", callback_data="days:" + day_str)
    builder.adjust(4)
    return builder.as_markup()


def services_keyboard(services):
    """Кнопки с выбором услуги: [(название, длительность), ...]"""
    builder = InlineKeyboardBuilder()
    for i, (name, duration) in enumerate(services):
        builder.button(text="%s · %s мин" % (name, duration), callback_data="svc:%s" % i)
    builder.button(text="⬅️ Назад", callback_data="cancel_step")
    builder.adjust(1)
    return builder.as_markup()


def phone_keyboard():
    """Кнопка-запрос контакта (телефона) — работает только в личных сообщениях."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📱 Отправить телефон", request_contact=True)
    builder.adjust(1)
    return builder.as_markup()


def confirm_keyboard(day_str, time_str):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить запись", callback_data="confirm:%s|%s" % (day_str, time_str))
    builder.button(text="❌ Отмена", callback_data="cancel_step")
    builder.adjust(1)
    return builder.as_markup()


def bookings_keyboard(bookings):
    """Список записей клиента с кнопками отмены: [(id, подпись), ...]"""
    builder = InlineKeyboardBuilder()
    for booking_id, label in bookings:
        builder.button(text="❌ " + label, callback_data="drop:" + str(booking_id))
    builder.button(text="⬅️ В меню", callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()
