FROM python:3.15-slim

WORKDIR /app

# Системные зависимости для компиляции пакетов при необходимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# S1: не запускаем приложение от root
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/storage \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && PYTHONPATH=/app python scripts/smoke_check.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
