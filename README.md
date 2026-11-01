# Tropicana SPB — Telegram-бот записи в салон красоты

Простой стек: **Python 3.12 + aiogram 3** (Telegram Bot API), данные — **обычный CSV-файл**
(`data/bookings.csv`) вместо базы данных. Хранятся только актуальные записи на неделю
вперёд — прошедшие удаляются автоматически при каждой операции с файлом.

## Как это работает

Сценарий в чате: `/start` → «📅 Записаться» → выбор дня (сегодня + 7 дней) →
**тайм-слоты с 10:00 до 22:00 с шагом 30 минут** → услуга («Услуга 1», «Услуга 2» —
названия меняются в `.env`, новые добавляются по аналогии) → имя → телефон
(кнопка «📱 Отправить телефон» или ввод текстом, пропуск — `/skip`) → подтверждение.

- 📋 «Мои записи» — просмотр и отмена своих записей
- ⏰ Напоминание клиенту за `REMINDER_HOURS_BEFORE` часов до визита (asyncio-цикл раз в 10 минут)
- 🆕 Уведомления админу в личку (`ADMIN_CHAT_ID`) о новой записи и об отмене
- 🔐 `/bookings <ADMIN_SECRET>` — все записи на неделю для администратора

## Структура проекта

```
app/
  main.py          — точка входа (бот + фоновые напоминания)
  config.py        — настройки из переменных окружения (.env)
  csv_db.py        — работа с CSV-файлом (чтение/запись/удаление прошедших)
  keyboards.py     — inline-клавиатуры
  reminders.py     — цикл напоминаний о визите
  handlers/
    start.py       — /start, /help, меню, «О салоне»
    booking.py     — сценарий записи и «Мои записи»
    admin.py       — /bookings для администратора
Dockerfile
docker-compose.yml
requirements.txt   — всего 3 зависимости: aiogram, python-dotenv, pytz
.env.example       — пример настроек
data/bookings.csv  — файл с записями (создаётся автоматически)
```

## Быстрый старт (без Docker)

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # впишите BOT_TOKEN, ADMIN_SECRET, ADMIN_CHAT_ID
python -m app.main
```

## Запуск в Docker

```bash
cp .env.example .env    # впишите BOT_TOKEN, ADMIN_SECRET, ADMIN_CHAT_ID
docker compose up -d --build
```

CSV-файл сохраняется в папке `./data` рядом с `docker-compose.yml`
(или замените на named volume в `docker-compose.yml`).

## Настройки (.env)

| Переменная | Описание | По умолчанию |
|---|---|---|
| `BOT_TOKEN` | токен от @BotFather | — |
| `CSV_FILE` | путь к файлу записей | `./data/bookings.csv` |
| `TIMEZONE` | часовой пояс салона | `Europe/Moscow` |
| `WORK_START_HOUR` / `WORK_END_HOUR` | рабочие часы | `10` / `22` |
| `SLOT_MINUTES` | шаг тайм-слотов | `30` |
| `BOOKING_HORIZON_DAYS` | дней вперёд для записи | `7` |
| `ADMIN_SECRET` | код для /bookings | — |
| `ADMIN_CHAT_ID` | Telegram ID админа для уведомлений (0 — выкл.) | `0` |
| `SERVICES` | услуги: `Название\|минуты;...` | `Услуга 1\|30;Услуга 2\|30` |
| `REMINDER_HOURS_BEFORE` | за сколько часов слать напоминание | `3` |

## Пример файла data/bookings.csv

```csv
id,date,time,service,duration,name,phone,telegram_id,chat_id,reminder_sent,created_at
1,2026-11-05,14:30,Услуга 1,30,Анна,+79001234567,123456789,123456789,0,2026-11-01 12:10
```

Прошедшие записи (дата+время раньше текущего момента) удаляются из файла
автоматически при любом чтении/записи — файл всегда содержит только неделю вперёд.
