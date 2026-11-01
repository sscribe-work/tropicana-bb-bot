"""Команды /start, /help и главное меню."""
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app import config
from app.keyboards import main_menu

start_router = Router()

SALON_NAME = "Tropicana SPB"

WELCOME = (
    "👋 Добро пожаловать в салон красоты <b>%s</b>!\n\n"
    "Мы работаем ежедневно с %02d:00 до %02d:00.\n"
    "Записаться можно на любое свободное время с шагом %s минут.\n\n"
    "Что вы можете:\n"
    "• 📅 Записаться — выбрать день, тайм-слот и услугу\n"
    "• 📋 Мои записи — посмотреть и отменить визит\n"
    "• ℹ️ О салоне — адреса и услуги\n"
    "⏰ За %s ч до визита пришлём напоминание."
) % (
    SALON_NAME,
    config.WORK_START_HOUR,
    config.WORK_END_HOUR,
    config.SLOT_MINUTES,
    config.REMINDER_HOURS_BEFORE,
)


@start_router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(WELCOME, reply_markup=main_menu())


@start_router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Как записаться:\n"
        "1️⃣ Нажмите «📅 Записаться»\n"
        "2️⃣ Выберите день\n"
        "3️⃣ Выберите свободный тайм-слот (с %02d:00 до %02d:00, шаг %s мин)\n"
        "4️⃣ Выберите услугу\n"
        "5️⃣ Укажите имя и телефон\n"
        "6️⃣ Подтвердите запись\n\n"
        "Отменить визит можно в разделе «📋 Мои записи».\n"
        "За %s ч до визита пришлём напоминание."
        % (config.WORK_START_HOUR, config.WORK_END_HOUR, config.SLOT_MINUTES, config.REMINDER_HOURS_BEFORE)
    )


@start_router.callback_query(F.data == "menu:main")
async def cb_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(WELCOME, reply_markup=main_menu())
    await callback.answer()


@start_router.callback_query(F.data == "menu:about")
async def cb_about(callback: CallbackQuery):
    services = "\n".join("• %s (%s мин)" % (name, dur) for name, dur in config.get_services())
    await callback.message.edit_text(
        "💇‍♀️ <b>Салон красоты %s</b>\n\n"
        "📍 г. Санкт-Петербург, Невский проспект, 1\n"
        "📞 +7 (812) 123-45-67\n"
        "🕐 Ежедневно %02d:00–%02d:00\n\n"
        "<b>Услуги:</b>\n%s" % (SALON_NAME, config.WORK_START_HOUR, config.WORK_END_HOUR, services),
        reply_markup=main_menu(),
    )
    await callback.answer()
