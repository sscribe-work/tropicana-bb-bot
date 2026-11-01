# 📅 Telegram-бот записи клиентов в салон красоты

Бот предлагает клиенту выбрать день и **свободный тайм-слот с 10:00 до 22:00 с шагом 30 минут**,
затем имя — и создаёт запись. Клиент может посмотреть и отменить свои записи,
администратор — увидеть все записи командой `/bookings`.

## Стек технологий

| Компонент        | Технология                                   |
|------------------|----------------------------------------------|
| Язык             | Python 3.12                                  |
| Telegram-фреймворк | [aiogram 3](https://docs.aiogram.dev) (async, FSM, inline-клавиатуры) |
| ORM              | SQLAlchemy 2.0 (asyncio)                     |
| База данных      | SQLite (по умолчанию) / PostgreSQL (в compose) |
| Конфигурация     | pydantic-settings (env-переменные)           |
| Контейнеризация  | Docker + docker-compose                      |

## Структура проекта

```
app/
├── main.py            # точка входа (polling)
├── config.py          # настройки из ENV
├── keyboards.py       # inline-клавиатуры (дни, слоты, подтверждение)
├── db/
│   ├── models.py      # модель Booking + репозиторий (частичный unique-индекс на слот)
│   └── session.py     # async engine / sessionmaker
└── handlers/
    ├── start.py       # /start, /help, меню
    ├── booking.py     # сценарий записи и «Мои записи»
    └── admin.py       # /bookings <ADMIN_SECRET> — список записей на неделю
```

## Быстрый старт (локально)

```bash
pip install -r requirements.txt
cp .env.example .env          # впишите BOT_TOKEN от @BotFather
python -m app.main
```

## Запуск в Docker

```bash
cp .env.example .env          # BOT_TOKEN=... ADMIN_SECRET=...
docker compose up -d --build  # бот + PostgreSQL
```

Только бот (SQLite внутри volume):

```bash
docker build -t salon-bot .
docker run -d --name salon-bot --env-file .env -v bot_data:/srv/app/data salon-bot
```

## Как выглядит сценарий клиента

1. `/start` → главное меню: «📅 Записаться», «📋 Мои записи», «ℹ️ О салоне».
2. Выбор дня (сегодня … +7 дней). На «сегодня» прошедшие слоты скрыты.
3. Кнопки свободных слотов: `10:00 10:30 11:00 … 21:30` (по 4 в ряду).
4. Ввод имени → подтверждение → запись сохранена ✅.
5. «Мои записи» — активные визиты, отмена одним нажатием.

Гонка двух клиентов за один слот исключена: проверка при выборе слота +
частичный уникальный индекс `UNIQUE (date, time) WHERE status='ACTIVE'`.

## Переменные окружения

| Переменная             | По умолчанию                          | Описание                     |
|------------------------|---------------------------------------|------------------------------|
| `BOT_TOKEN`            | —                                     | Токен бота (обязательно)     |
| `DATABASE_URL`         | `sqlite+aiosqlite:///./data/salon.db` | Строка подключения к БД      |
| `TIMEZONE`             | `Europe/Moscow`                       | Часовой пояс салона          |
| `WORK_START_HOUR`      | `10`                                  | Начало рабочего дня          |
| `WORK_END_HOUR`        | `22`                                  | Конец рабочего дня           |
| `SLOT_MINUTES`         | `30`                                  | Шаг тайм-слотов              |
| `BOOKING_HORIZON_DAYS` | `7`                                   | Запись на N дней вперёд      |
| `ADMIN_SECRET`         | —                                     | Код доступа к `/bookings`    |

## Тесты

```bash
python tests/test_db.py   # генерация слотов, блокировка дублей, отмена
```
