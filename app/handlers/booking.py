"""Сценарий записи: день -> тайм-слот -> услуга -> имя -> телефон -> подтверждение.

Данные храним в CSV-файле (app/csv_db.py), напоминания шлёт простой asyncio-цикл.
"""
import asyncio
import logging
import re
from datetime import date, datetime, timedelta

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app import config, csv_db
from app.handlers.start import WELCOME
from app.keyboards import (
    bookings_keyboard,
    confirm_keyboard,
    days_keyboard,
    main_menu,
    phone_keyboard,
    services_keyboard,
    slots_keyboard,
)

booking_router = Router()
logger = logging.getLogger(__name__)

PHONE_RE = re.compile(r"^\+?[\d\s\-()]{7,20}$")


class BookingStates(StatesGroup):
    choosing_day = State()
    choosing_slot = State()
    choosing_service = State()
    entering_name = State()
    entering_phone = State()
    confirming = State()


def upcoming_days(count):
    """Список дат на неделю вперёд (сегодня + следующие дни)."""
    today = csv_db.now_local().date()
    return [today + timedelta(days=i) for i in range(count)]


def day_label(d):
    """Красивая подпись дня: Сегодня / Завтра / 15.05.2026."""
    today = csv_db.now_local().date()
    if d == today:
        return "Сегодня"
    if d == today + timedelta(days=1):
        return "Завтра"
    return d.strftime("%d.%m.%Y")


async def notify_admin(bot, text):
    """Уведомление администратору в личку (если задан ADMIN_CHAT_ID)."""
    if not config.ADMIN_CHAT_ID:
        return
    try:
        await bot.send_message(config.ADMIN_CHAT_ID, text)
    except Exception as exc:
        logger.warning("Не удалось отправить уведомление админу: %s", exc)


async def show_slots(callback, day_str):
    """Присылает сообщение со свободными слотами на выбранный день."""
    slots = csv_db.get_free_slots(day_str)
    day = date.fromisoformat(day_str)
    if not slots:
        await callback.message.edit_text(
            "😔 На %s свободных окон нет — выберите другой день." % day_label(day),
            reply_markup=days_keyboard(upcoming_days(config.BOOKING_HORIZON_DAYS), back_cb="menu:main"),
        )
        return
    await callback.message.edit_text(
        "📅 %s — выберите время (шаг %s мин):" % (day_label(day), config.SLOT_MINUTES),
        reply_markup=slots_keyboard(day_str, slots),
    )


@booking_router.callback_query(F.data == "menu:new_booking")
async def cb_new_booking(callback, state):
    await state.set_state(BookingStates.choosing_day)
    await callback.message.edit_text(
        "Выберите день визита:",
        reply_markup=days_keyboard(upcoming_days(config.BOOKING_HORIZON_DAYS)),
    )
    await callback.answer()


@booking_router.callback_query(F.data.startswith("days:"))
async def cb_days_again(callback, state):
    await state.set_state(BookingStates.choosing_day)
    await callback.message.edit_text(
        "Выберите день визита:",
        reply_markup=days_keyboard(upcoming_days(config.BOOKING_HORIZON_DAYS)),
    )
    await callback.answer()


@booking_router.callback_query(F.data.startswith("day:"), BookingStates.choosing_day)
async def cb_choose_day(callback, state):
    day_str = callback.data.split(":", 1)[1]
    await state.update_data(day=day_str)
    await state.set_state(BookingStates.choosing_slot)
    await show_slots(callback, day_str)


@booking_router.callback_query(F.data.startswith("slot:"), BookingStates.choosing_slot)
async def cb_choose_slot(callback, state):
    day_str, time_str = callback.data.split(":", 1)[1].split("|")

    # Актуальная проверка: вдруг слот только что заняли
    if not csv_db.slot_is_free(day_str, time_str):
        await callback.answer("Это время уже заняли 😔 Выберите другое.", show_alert=True)
        await show_slots(callback, day_str)
        return

    await state.update_data(day=day_str, slot=time_str)
    await state.set_state(BookingStates.choosing_service)
    day = date.fromisoformat(day_str)
    await callback.message.edit_text(
        "🕐 %s, %s\n\n💇‍♀️ Выберите услугу:" % (day_label(day), time_str),
        reply_markup=services_keyboard(config.get_services()),
    )
    await callback.answer()


@booking_router.callback_query(F.data.startswith("svc:"), BookingStates.choosing_service)
async def cb_choose_service(callback, state):
    idx = int(callback.data.split(":", 1)[1])
    services = config.get_services()
    if idx < 0 or idx >= len(services):
        await callback.answer("Услуга недоступна", show_alert=True)
        return
    name, duration = services[idx]
    await state.update_data(service=name, duration=duration)
    await state.set_state(BookingStates.entering_name)
    await callback.message.edit_text(
        "💇‍♀️ %s · %s мин\n✍️ Введите ваше имя:" % (name, duration),
        reply_markup=None,
    )
    await callback.answer()


@booking_router.message(StateFilter(BookingStates.entering_name), ~F.text)
async def msg_enter_name(message, state):
    name = (message.text or "").strip()[:120]
    if not name or len(name) < 2:
        await message.answer("Имя должно содержать минимум 2 символа. Попробуйте ещё раз:")
        return
    await state.update_data(name=name)
    await state.set_state(BookingStates.entering_phone)
    if message.chat.type == "private":
        await message.answer(
            "Отлично, %s! 📱 Отправьте номер телефона кнопкой ниже "
            "(или напишите его сообщением — можно пропустить командой /skip):" % name,
            reply_markup=phone_keyboard(),
        )
    else:
        await message.answer("Отлично, %s! 📱 Напишите номер телефона (или /skip, чтобы пропустить):" % name)


@booking_router.message(StateFilter(BookingStates.entering_phone), F.contact)
async def msg_contact(message, state):
    phone = message.contact.phone_number if message.contact else ""
    await finish_phone(message, state, phone)


@booking_router.message(StateFilter(BookingStates.entering_phone), F.text)
async def msg_phone_text(message, state):
    text = (message.text or "").strip()
    if text.lower() in ("/skip", "skip", "пропустить"):
        await finish_phone(message, state, "не указан")
        return
    if not PHONE_RE.match(text):
        await message.answer("Похоже, это не номер телефона 🤔 Пример: +7 900 123-45-67. Или отправьте /skip.")
        return
    await finish_phone(message, state, text)


async def finish_phone(message, state, phone):
    await state.update_data(phone=phone)
    data = await state.get_data()
    day = date.fromisoformat(data["day"])
    await state.set_state(BookingStates.confirming)
    await message.answer(
        "🗒 Проверьте данные записи:\n\n"
        "👤 Имя: <b>%s</b>\n"
        "📱 Телефон: <b>%s</b>\n"
        "💇‍♀️ Услуга: <b>%s</b>\n"
        "📅 Дата: <b>%s</b>\n"
        "🕐 Время: <b>%s</b>\n"
        "⏱ Длительность: %s минут"
        % (data["name"], phone, data.get("service", "Услуга"),
           day_label(day), data["slot"], data.get("duration", config.SLOT_MINUTES)),
        reply_markup=confirm_keyboard(data["day"], data["slot"]),
    )


@booking_router.callback_query(F.data.startswith("confirm:"), BookingStates.confirming)
async def cb_confirm(callback, state, bot):
    day_str, time_str = callback.data.split(":", 1)[1].split("|")
    data = await state.get_data()
    name = data.get("name", callback.from_user.full_name)
    phone = data.get("phone", "не указан")
    service = data.get("service", "Услуга")
    duration = data.get("duration", config.SLOT_MINUTES)

    booking = csv_db.add_booking(
        day_str=day_str,
        time_str=time_str,
        service=service,
        duration=duration,
        name=name,
        phone=phone,
        telegram_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
    )

    if booking is None:
        await callback.answer("К сожалению, это время только что заняли 😔", show_alert=True)
        await show_slots(callback, day_str)
        return

    await state.clear()
    day = date.fromisoformat(day_str)
    ends_at = datetime.strptime(time_str, "%H:%M") + timedelta(minutes=int(duration))
    await callback.message.edit_text(
        "✅ <b>Вы записаны!</b>\n\n"
        "👤 %s · 📱 %s\n"
        "💇‍♀️ %s\n"
        "📅 %s, %s–%s\n\n"
        "Ждём вас в салоне Tropicana SPB! Отменить визит можно в «📋 Мои записи».\n"
        "⏰ За %s ч до визита пришлём напоминание."
        % (name, phone, service, day_label(day), time_str,
           ends_at.strftime("%H:%M"), config.REMINDER_HOURS_BEFORE),
        reply_markup=main_menu(),
    )
    await callback.answer()

    # Уведомление администратору
    await notify_admin(
        bot,
        "🆕 <b>Новая запись</b>\n\n"
        "👤 %s\n"
        "📱 %s\n"
        "💇‍♀️ %s\n"
        "📅 %s, %s\n"
        "🆔 Telegram: <code>%s</code>"
        % (name, phone, service, day_label(day), time_str, callback.from_user.id),
    )


@booking_router.callback_query(F.data == "cancel_step", StateFilter("*"))
async def cb_cancel_step(callback, state):
    await state.clear()
    await callback.message.edit_text(WELCOME, reply_markup=main_menu())
    await callback.answer("Действие отменено")


@booking_router.callback_query(F.data == "menu:my_bookings")
async def cb_my_bookings(callback):
    rows = csv_db.bookings_for_user(callback.from_user.id)
    if not rows:
        await callback.message.edit_text(
            "У вас пока нет активных записей.\nНажмите «📅 Записаться», чтобы выбрать время.",
            reply_markup=main_menu(),
        )
        await callback.answer()
        return

    items = []
    for row in rows:
        label = "%s %s · %s" % (day_label(date.fromisoformat(row["date"])), row["time"], row["service"])
        items.append((row["id"], label))
    await callback.message.edit_text(
        "📋 Ваши активные записи (нажмите, чтобы отменить):",
        reply_markup=bookings_keyboard(items),
    )
    await callback.answer()


@booking_router.callback_query(F.data.startswith("drop:"))
async def cb_drop_booking(callback, bot):
    booking_id = callback.data.split(":", 1)[1]
    row = csv_db.find_booking(booking_id)
    if not row or row["telegram_id"] != str(callback.from_user.id):
        await callback.answer("Запись не найдена.", show_alert=True)
        return

    deleted = csv_db.delete_booking(booking_id)
    day = date.fromisoformat(deleted["date"])

    await notify_admin(
        bot,
        "🚫 <b>Отмена записи</b>\n\n"
        "👤 %s · 📱 %s\n"
        "💇‍♀️ %s\n"
        "📅 %s, %s\n"
        "🆔 Telegram: <code>%s</code>"
        % (deleted["name"], deleted["phone"], deleted["service"],
           day_label(day), deleted["time"], callback.from_user.id),
    )

    await callback.answer("Запись отменена ✅")
    rows = csv_db.bookings_for_user(callback.from_user.id)
    if not rows:
        await callback.message.edit_text(
            "Все записи отменены. Создать новую — «📅 Записаться».",
            reply_markup=main_menu(),
        )
        return
    items = [
        (r["id"], "%s %s · %s" % (day_label(date.fromisoformat(r["date"])), r["time"], r["service"]))
        for r in rows
    ]
    await callback.message.edit_text(
        "📋 Ваши активные записи (нажмите, чтобы отменить):",
        reply_markup=bookings_keyboard(items),
    )
