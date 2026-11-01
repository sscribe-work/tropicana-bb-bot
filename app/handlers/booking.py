"""Сценарий записи: день → тайм-слот → услуга → имя → телефон → подтверждение."""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, time, timedelta

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.db.models import Booking, BookingStatus, create_booking, get_free_slots
from app.db.session import SessionMaker
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
settings = get_settings()
tz = ZoneInfo(settings.timezone)
logger = logging.getLogger(__name__)

PHONE_RE = re.compile(r"^\+?[\d\s\-()]{7,20}$")


class BookingStates(StatesGroup):
    choosing_day = State()
    choosing_slot = State()
    choosing_service = State()
    entering_name = State()
    entering_phone = State()
    confirming = State()


def _now_local() -> datetime:
    return datetime.now(tz)


def upcoming_days(count: int) -> list[date]:
    today = _now_local().date()
    return [today + timedelta(days=i) for i in range(count)]


def day_label(d: date) -> str:
    today = _now_local().date()
    if d == today:
        return "Сегодня"
    if d == today + timedelta(days=1):
        return "Завтра"
    return d.strftime("%d.%m.%Y")


async def notify_admin(bot: Bot, text: str) -> None:
    """Уведомление администратору в личку (если задан ADMIN_CHAT_ID)."""
    if not settings.admin_chat_id:
        return
    try:
        await bot.send_message(settings.admin_chat_id, text)
    except Exception as exc:  # пользователь заблокировал бота и т.п.
        logger.warning("Не удалось отправить уведомление админу: %s", exc)


async def show_slots(callback: CallbackQuery, day: date) -> None:
    """Присылает/обновляет сообщение со свободными слотами на день."""
    now = _now_local()
    start = time(settings.work_start_hour, 0)
    if day == now.date():
        # округляем «сейчас» вверх до ближайшего слота
        minutes = now.hour * 60 + now.minute + settings.slot_minutes
        start = time((minutes // 60) % 24 or settings.work_start_hour, minutes % 60)
        if (now.hour * 60 + now.minute) >= settings.work_end_hour * 60:
            await callback.message.edit_text(
                f"🕐 На {day_label(day)} свободных окон нет — выберите другой день.",
                reply_markup=days_keyboard(upcoming_days(settings.booking_horizon_days), back_cb="menu:main"),
            )
            return

    async with SessionMaker() as session:
        slots = await get_free_slots(session, day, start, time(settings.work_end_hour, 0), settings.slot_minutes)

    if not slots:
        await callback.message.edit_text(
            f"😔 На {day_label(day)} свободных окон нет — выберите другой день.",
            reply_markup=days_keyboard(upcoming_days(settings.booking_horizon_days), back_cb="menu:main"),
        )
        return

    await callback.message.edit_text(
        f"📅 {day_label(day)} — выберите время (шаг {settings.slot_minutes} мин):",
        reply_markup=slots_keyboard(day, slots),
    )


@booking_router.callback_query(F.data == "menu:new_booking")
async def cb_new_booking(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(BookingStates.choosing_day)
    await callback.message.edit_text(
        "Выберите день визита:",
        reply_markup=days_keyboard(upcoming_days(settings.booking_horizon_days)),
    )
    await callback.answer()


@booking_router.callback_query(F.data.startswith("days:"))
async def cb_days_again(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(BookingStates.choosing_day)
    await callback.message.edit_text(
        "Выберите день визита:",
        reply_markup=days_keyboard(upcoming_days(settings.booking_horizon_days)),
    )
    await callback.answer()


@booking_router.callback_query(F.data.startswith("day:"), BookingStates.choosing_day)
async def cb_choose_day(callback: CallbackQuery, state: FSMContext) -> None:
    day = date.fromisoformat(callback.data.split(":", 1)[1])
    await state.update_data(day=day.isoformat())
    await state.set_state(BookingStates.choosing_slot)
    await show_slots(callback, day)


@booking_router.callback_query(F.data.startswith("slot:"), BookingStates.choosing_slot)
async def cb_choose_slot(callback: CallbackQuery, state: FSMContext) -> None:
    raw_day, raw_time = callback.data.split(":", 1)[1].split("|")
    day = date.fromisoformat(raw_day)
    slot = time.fromisoformat(raw_time)

    # Актуальная проверка: вдруг слот только что заняли
    async with SessionMaker() as session:
        busy = await session.scalar(
            select(Booking.id).where(
                Booking.booking_date == day,
                Booking.booking_time == slot,
                Booking.status == BookingStatus.ACTIVE,
            )
        )
    if busy:
        await callback.answer("Это время уже заняли 😔 Выберите другое.", show_alert=True)
        await show_slots(callback, day)
        return

    await state.update_data(day=day.isoformat(), slot=raw_time)
    await state.set_state(BookingStates.choosing_service)
    services = settings.service_list()
    await callback.message.edit_text(
        f"🕐 {day_label(day)}, {raw_time}\n\n💇‍♀️ Выберите услугу:",
        reply_markup=services_keyboard(services),
    )
    await callback.answer()


@booking_router.callback_query(F.data.startswith("svc:"), BookingStates.choosing_service)
async def cb_choose_service(callback: CallbackQuery, state: FSMContext) -> None:
    idx = int(callback.data.split(":", 1)[1])
    services = settings.service_list()
    if idx < 0 or idx >= len(services):
        await callback.answer("Услуга недоступна", show_alert=True)
        return
    name, duration = services[idx]
    await state.update_data(service=name, duration=duration)
    await state.set_state(BookingStates.entering_name)
    await callback.message.edit_text(
        f"💇‍♀️ {name} · {duration} мин\n✍️ Введите ваше имя:",
        reply_markup=None,
    )
    await callback.answer()


@booking_router.message(StateFilter(BookingStates.entering_name), ~F.text)
async def msg_enter_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()[:120]
    if not name or len(name) < 2:
        await message.answer("Имя должно содержать минимум 2 символа. Попробуйте ещё раз:")
        return
    await state.update_data(name=name)
    await state.set_state(BookingStates.entering_phone)
    if message.chat.type == "private":
        await message.answer(
            f"Отлично, {name}! 📱 Отправьте номер телефона кнопкой ниже "
            "(или напишите его сообщением — можно пропустить командой /skip):",
            reply_markup=phone_keyboard(),
        )
    else:
        await message.answer(
            f"Отлично, {name}! 📱 Напишите номер телефона (или /skip, чтобы пропустить):"
        )


@booking_router.message(StateFilter(BookingStates.entering_phone), F.contact)
async def msg_contact(message: Message, state: FSMContext) -> None:
    phone = message.contact.phone_number if message.contact else ""
    await _finish_phone(message, state, phone)


@booking_router.message(StateFilter(BookingStates.entering_phone), F.text)
async def msg_phone_text(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text.lower() in {"/skip", "skip", "пропустить"}:
        await _finish_phone(message, state, "не указан")
        return
    if not PHONE_RE.match(text):
        await message.answer("Похоже, это не номер телефона 🤔 Пример: +7 900 123-45-67. Или отправьте /skip.")
        return
    await _finish_phone(message, state, text)


async def _finish_phone(message: Message, state: FSMContext, phone: str) -> None:
    await state.update_data(phone=phone)
    data = await state.get_data()
    day = date.fromisoformat(data["day"])
    slot = time.fromisoformat(data["slot"])
    await state.set_state(BookingStates.confirming)
    await message.answer(
        "🗒 Проверьте данные записи:\n\n"
        f"👤 Имя: <b>{data['name']}</b>\n"
        f"📱 Телефон: <b>{phone}</b>\n"
        f"💇‍♀️ Услуга: <b>{data.get('service', 'Услуга')}</b>\n"
        f"📅 Дата: <b>{day_label(day)}</b>\n"
        f"🕐 Время: <b>{slot.strftime('%H:%M')}</b>\n"
        f"⏱ Длительность: {data.get('duration', settings.slot_minutes)} минут",
        reply_markup=confirm_keyboard(day, slot),
    )


@booking_router.callback_query(F.data.startswith("confirm:"), BookingStates.confirming)
async def cb_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    raw_day, raw_time = callback.data.split(":", 1)[1].split("|")
    day = date.fromisoformat(raw_day)
    slot = time.fromisoformat(raw_time)
    data = await state.get_data()
    name = data.get("name", callback.from_user.full_name)
    phone = data.get("phone", "не указан")
    service = data.get("service", "Услуга")
    duration = data.get("duration", settings.slot_minutes)

    async with SessionMaker() as session:
        booking = await create_booking(
            session,
            booking_date=day,
            booking_time=slot,
            telegram_id=callback.from_user.id,
            chat_id=callback.message.chat.id,
            client_name=name,
            client_phone=phone,
            service=service,
        )

    if booking is None:
        await callback.answer("К сожалению, это время только что заняли 😔", show_alert=True)
        await show_slots(callback, day)
        return

    await state.clear()
    ends_at = datetime.combine(day, slot) + timedelta(minutes=duration)
    await callback.message.edit_text(
        "✅ <b>Вы записаны!</b>\n\n"
        f"👤 {name} · 📱 {phone}\n"
        f"💇‍♀️ {service}\n"
        f"📅 {day_label(day)}, {slot.strftime('%H:%M')}–{ends_at.strftime('%H:%M')}\n\n"
        "Ждём вас в салоне Tropicana SPB! Отменить визит можно в «📋 Мои записи».\n"
        f"⏰ За {settings.reminder_hours_before} ч до визита пришлём напоминание.",
        reply_markup=main_menu(),
    )
    await callback.answer()

    # Уведомление администратору
    await notify_admin(
        bot,
        "🆕 <b>Новая запись</b>\n\n"
        f"👤 {name}\n"
        f"📱 {phone}\n"
        f"💇‍♀️ {service}\n"
        f"📅 {day_label(day)}, {slot.strftime('%H:%M')}–{ends_at.strftime('%H:%M')}\n"
        f"🆔 Telegram: <code>{callback.from_user.id}</code>",
    )


@booking_router.callback_query(F.data == "cancel_step", StateFilter("*"))
async def cb_cancel_step(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(WELCOME.format(step=settings.slot_minutes), reply_markup=main_menu())
    await callback.answer("Действие отменено")


@booking_router.callback_query(F.data == "menu:my_bookings")
async def cb_my_bookings(callback: CallbackQuery) -> None:
    async with SessionMaker() as session:
        rows = (
            await session.scalars(
                select(Booking)
                .where(Booking.telegram_id == callback.from_user.id, Booking.status == BookingStatus.ACTIVE)
                .order_by(Booking.booking_date, Booking.booking_time)
            )
        ).all()

    if not rows:
        await callback.message.edit_text(
            "У вас пока нет активных записей.\nНажмите «📅 Записаться», чтобы выбрать время.",
            reply_markup=main_menu(),
        )
        await callback.answer()
        return

    items = [
        (b.id, f"{day_label(b.booking_date)} {b.booking_time.strftime('%H:%M')} · {b.service}")
        for b in rows
    ]
    await callback.message.edit_text("📋 Ваши активные записи (нажмите, чтобы отменить):", reply_markup=bookings_keyboard(items))
    await callback.answer()


@booking_router.callback_query(F.data.startswith("drop:"))
async def cb_drop_booking(callback: CallbackQuery, bot: Bot) -> None:
    booking_id = int(callback.data.split(":", 1)[1])

    async with SessionMaker() as session:
        booking = await session.get(Booking, booking_id)
        if not booking or booking.telegram_id != callback.from_user.id or booking.status != BookingStatus.ACTIVE:
            await callback.answer("Запись не найдена.", show_alert=True)
            return
        booking.status = BookingStatus.CANCELLED
        await session.commit()
        info = (booking.booking_date, booking.booking_time, booking.client_name, booking.service, booking.client_phone)
        rows = (
            await session.scalars(
                select(Booking)
                .where(Booking.telegram_id == callback.from_user.id, Booking.status == BookingStatus.ACTIVE)
                .order_by(Booking.booking_date, Booking.booking_time)
            )
        ).all()

    b_day, b_time, b_name, b_service, b_phone = info
    await notify_admin(
        bot,
        "🚫 <b>Отмена записи</b>\n\n"
        f"👤 {b_name} · 📱 {b_phone}\n"
        f"💇‍♀️ {b_service}\n"
        f"📅 {day_label(b_day)}, {b_time.strftime('%H:%M')}\n"
        f"🆔 Telegram: <code>{callback.from_user.id}</code>",
    )

    await callback.answer("Запись отменена ✅")
    if not rows:
        await callback.message.edit_text(
            "Все записи отменены. Создать новую — «📅 Записаться».",
            reply_markup=main_menu(),
        )
        return
    items = [
        (b.id, f"{day_label(b.booking_date)} {b.booking_time.strftime('%H:%M')} · {b.service}")
        for b in rows
    ]
    await callback.message.edit_text(
        "📋 Ваши активные записи (нажмите, чтобы отменить):",
        reply_markup=bookings_keyboard(items),
    )
