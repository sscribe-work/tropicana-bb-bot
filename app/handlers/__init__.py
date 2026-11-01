"""Хендлеры бота."""
from app.handlers.admin import admin_router
from app.handlers.booking import booking_router
from app.handlers.start import start_router

routers = (start_router, booking_router, admin_router)
