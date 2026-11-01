"""Команды /start, /help и главное меню."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.config import get_settings
from app.keyboards import main_menu

start_router = Router()
settings = get_settings()

WELCOME = (
    "👋 Добро пожаловать в салон красоты <b>Lumière</b>!\n\n"
    f"Мы работаем ежедневно с {settings.work_start_hour:02d}:00 до {settings.work_end_hour:02d}:00.\n"
    "Записаться можно на любое свободное время с шагом {step} минут, выбранная дата показана кнопками.\n\n"
    "Что вы можете:\n"
    "• 📅 Записаться — выбрать день и тайм-слот\n"
    "• 📋 Мои записи — посмотреть и отменить визит\n"
    "• ℹ️ О салоне — адреса и услуги"
)


@start_router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(WELCOME.format(step=settings.slot_minutes), reply_markup=main_menu())


@start_router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Как записаться:\n"
        "1️⃣ Нажмите «📅 Записаться»\n"
        "2️⃣ Выберите день\n"
        "3️⃣ Выберите свободный тайм-слот\n"
        "4️⃣ Укажите имя и подтвердите запись\n\n"
        "Отменить или перенести визит можно в разделе «📋 Мои записи».",
    )


@start_router.callback_query(F.data == "menu:main")
async def cb_main_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(WELCOME.format(step=settings.slot_minutes), reply_markup=main_menu())
    await callback.answer()


@start_router.callback_query(F.data == "menu:about")
async def cb_about(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "💇‍♀️ <b>Салон красоты Lumière</b>\n\n"
        "📍 г. Москва, ул. Тверская, 1\n"
        "📞 +7 (495) 123-45-67\n"
        f"🕐 Ежедневно {settings.work_start_hour:02d}:00–{settings.work_end_hour:02d}:00\n\n"
        "Услуги: стрижка, окрашивание, маникюр, педикюр, уходовые процедуры.",
        reply_markup=main_menu(),
    )
    await callback.answer()
