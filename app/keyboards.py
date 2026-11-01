"""Inline-клавиатуры бота."""
from __future__ import annotations

from datetime import date, time

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

WEEKDAYS_RU = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]


def main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Записаться", callback_data="menu:new_booking")
    builder.button(text="📋 Мои записи", callback_data="menu:my_bookings")
    builder.button(text="ℹ️ О салоне", callback_data="menu:about")
    builder.adjust(1)
    return builder.as_markup()


def days_keyboard(days: list[date], back_cb: str = "menu:main") -> InlineKeyboardMarkup:
    """Кнопки с выбором дня (по 3 в ряду)."""
    builder = InlineKeyboardBuilder()
    for d in days:
        label = f"{d.strftime('%d.%m')} {WEEKDAYS_RU[d.weekday()]}"
        builder.button(text=label, callback_data=f"day:{d.isoformat()}")
    builder.button(text="⬅️ Назад", callback_data=back_cb)
    builder.adjust(3)
    return builder.as_markup()


def slots_keyboard(day: date, slots: list[time]) -> InlineKeyboardMarkup:
    """Кнопки со свободными тайм-слотами."""
    builder = InlineKeyboardBuilder()
    for t in slots:
        builder.button(text=t.strftime("%H:%M"), callback_data=f"slot:{day.isoformat()}|{t.strftime('%H:%M')}")
    builder.button(text="⬅️ Другой день", callback_data=f"days:{day.isoformat()}")
    builder.adjust(4)
    return builder.as_markup()


def confirm_keyboard(day: date, slot: time) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить запись", callback_data=f"confirm:{day.isoformat()}|{slot.strftime('%H:%M')}")
    builder.button(text="❌ Отмена", callback_data="cancel_step")
    builder.adjust(1)
    return builder.as_markup()


def bookings_keyboard(bookings: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    """Список записей клиента с кнопками отмены."""
    builder = InlineKeyboardBuilder()
    for booking_id, label in bookings:
        builder.button(text=f"❌ {label}", callback_data=f"drop:{booking_id}")
    builder.button(text="⬅️ В меню", callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()
