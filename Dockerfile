# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv/app

# Зависимости отдельным слоем для кэширования
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Непривилегированный пользователь + каталог для SQLite
RUN useradd --create-home --uid 1000 bot && \
    mkdir -p /srv/app/data && chown -R bot:bot /srv/app
USER bot

CMD ["python", "-m", "app.main"]
