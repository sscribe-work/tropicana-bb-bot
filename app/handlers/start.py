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

SALON_NAME = "Tropicana SPB"

WELCOME = (
    f"👋 Добро пожаловать в салон красоты <b>{SALON_NAME}</b>!\n\n"
    f"Мы работаем ежедневно с {settings.work_start_hour:02d}:00 до {settings.work_end_hour:02d}:00.\n"
    "Записаться можно на любое свободное время с шагом {step} минут, выбранная дата показана кнопками.\n\n"
    "Что вы можете:\n"
    "• 📅 Записаться — выбрать день, тайм-слот и услугу\n"
    "• 📋 Мои записи — посмотреть и отменить визит\n"
    "• ℹ️ О салоне — адреса и услуги\n"
    f"⏰ За {settings.reminder_hours_before} ч до визита пришлём напоминание."
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
        f"3️⃣ Выберите свободный тайм-слот (с {settings.work_start_hour:02d}:00 до {settings.work_end_hour:02d}:00, шаг {settings.slot_minutes} мин)\n"
        "4️⃣ Выберите услугу\n"
        "5️⃣ Укажите имя и телефон\n"
        "6️⃣ Подтвердите запись\n\n"
        "Отменить визит можно в разделе «📋 Мои записи». "
        f"За {settings.reminder_hours_before} ч до визита пришлём напоминание.",
    )


@start_router.callback_query(F.data == "menu:main")
async def cb_main_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(WELCOME.format(step=settings.slot_minutes), reply_markup=main_menu())
    await callback.answer()


@start_router.callback_query(F.data == "menu:about")
async def cb_about(callback: CallbackQuery) -> None:
    services = "\n".join(f"• {name} ({dur} мин)" for name, dur in settings.service_list())
    await callback.message.edit_text(
        f"💇‍♀️ <b>Салон красоты {SALON_NAME}</b>\n\n"
        "📍 г. Санкт-Петербург, Невский проспект, 1\n"
        "📞 +7 (812) 123-45-67\n"
        f"🕐 Ежедневно {settings.work_start_hour:02d}:00–{settings.work_end_hour:02d}:00\n\n"
        f"<b>Услуги:</b>\n{services}",
        reply_markup=main_menu(),
    )
    await callback.answer()
